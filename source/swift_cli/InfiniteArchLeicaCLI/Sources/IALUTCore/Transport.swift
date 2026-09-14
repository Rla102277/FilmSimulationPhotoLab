import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

public enum Q3TransportState:String,Codable,Sendable { case locked, dryRun, experimental, live }

public struct Q3InstallRequest:Codable,Sendable {
    public var slot:Int
    public var lookID:UInt32
    public var name:String
    public var baseStyle:String
    public var cubePath:String
    public init(slot:Int, lookID:UInt32?=nil, name:String, baseStyle:String="Standard", cubePath:String) {
        self.slot=slot
        self.lookID=lookID ?? UInt32(1000 + slot)
        self.name=name
        self.baseStyle=baseStyle
        self.cubePath=cubePath
    }
}

public protocol Q3Transport:Sendable {
    var state:Q3TransportState { get }
    func probe() async throws -> String
    func listLooks() async throws -> [String]
    func install(_ request:Q3InstallRequest) async throws
}

public struct DryRunQ3Transport:Q3Transport {
    public let state:Q3TransportState = .dryRun
    public init() {}
    public func probe() async throws -> String { "Dry run" }
    public func listLooks() async throws -> [String] { [] }
    public func install(_ request:Q3InstallRequest) async throws {
        let log="[DRY RUN] slot=\(request.slot) id=\(request.lookID) name=\(request.name) base=\(request.baseStyle) cube=\(request.cubePath)\n"
        let url=FileManager.default.temporaryDirectory.appendingPathComponent("InfiniteArch-Q3Transport.log")
        if let data=log.data(using:.utf8) {
            if FileManager.default.fileExists(atPath:url.path), let h=try? FileHandle(forWritingTo:url) {
                try h.seekToEnd(); try h.write(contentsOf:data); try h.close()
            } else { try data.write(to:url) }
        }
    }
}

public enum Q3TransportError:Error,LocalizedError,Sendable {
    case socket(String)
    case invalidPacket(String)
    case cameraResponse(UInt16, UInt32)
    case cubeMissing(String)
    case accessControl(String)
    case unsupported(String)

    public var errorDescription:String? {
        switch self {
        case .socket(let s): return "Q3 network error: \(s)"
        case .invalidPacket(let s): return "Q3 protocol error: \(s)"
        case .cameraResponse(let code, let tx): return String(format:"Q3 rejected transaction 0x%08X (response 0x%04X).",tx,code)
        case .cubeMissing(let p): return "CUBE file not found: \(p)"
        case .accessControl(let s): return "Q3 access control: \(s)"
        case .unsupported(let s): return s
        }
    }
}

public struct Q3AccessReport:Sendable,CustomStringConvertible {
    public let firstResponse:String
    public let confirmationResponse:String?

    public var finalResponse:String { confirmationResponse ?? firstResponse }
    public var isOpen:Bool {
        let fields=finalResponse.split(separator:",",omittingEmptySubsequences:false)
        guard let status=fields.first,let state=fields.last else{return false}
        return (status=="ok" || status=="ok_under_research") && state=="open"
    }
    public var description:String {
        if let confirmationResponse {
            return "first=\(firstResponse)\nconfirmation=\(confirmationResponse)\naccess=\(isOpen ? "OPEN" : "NOT OPEN")"
        }
        return "response=\(firstResponse)\naccess=\(isOpen ? "OPEN" : "NOT OPEN")"
    }
}

// MARK: - Leica Look payload verified from a live Leica FOTOS -> Q3 capture

public enum LeicaLookPayload {
    public static let propertyRecordMarker:UInt32 = 0x20000014
    public static let propLookID:UInt16 = 0xD861
    public static let propName:UInt16 = 0xDC44
    public static let propIcon:UInt16 = 0xDC86
    public static let propCube:UInt16 = 0xD860
    public static let propType:UInt16 = 0xD864
    public static let propBaseStyle:UInt16 = 0xD866

    // Captured official downloadable Looks use 2 here. Base style 0 is Standard.
    public static func build(lookID:UInt32,name:String,baseStyle:String,cube:Data,icon:Data?=nil,recordMarker:UInt32=propertyRecordMarker) throws -> Data {
        guard !cube.isEmpty else { throw Q3TransportError.invalidPacket("Empty CUBE data.") }
        guard recordMarker>=0x2000000F,recordMarker<0x21000000 else { throw Q3TransportError.invalidPacket("Invalid Leica Look record marker.") }
        var d=Data()
        d.appendLE(UInt32(6))
        appendUInt32(&d,marker:recordMarker,code:propLookID,value:lookID)
        appendString(&d,marker:recordMarker,code:propName,value:name)
        appendByteArray(&d,marker:recordMarker,code:propIcon,value:icon ?? LeicaLookIcon.make(name:name))
        appendByteArray(&d,marker:recordMarker,code:propCube,value:cube)
        appendUInt32(&d,marker:recordMarker,code:propType,value:2)
        appendUInt32(&d,marker:recordMarker,code:propBaseStyle,value:baseStyle.lowercased().contains("mono") ? 1 : 0)
        return d
    }

    /// The Q3 43 trace proved record markers are stable identities allocated in
    /// sequence, independent of display slot. Derive a new marker from 0x9033.
    public static func nextRecordMarker(from lookTable:Data)throws->UInt32 {
        guard lookTable.count>=4 else{throw Q3TransportError.invalidPacket("Short Leica Look table.")}
        let fieldCount=Int(lookTable.readLE(UInt32.self,at:0)); var offset=4; var maximum:UInt32=0
        for _ in 0..<fieldCount {
            guard offset+8<=lookTable.count else{throw Q3TransportError.invalidPacket("Truncated Leica Look field header.")}
            let marker=lookTable.readLE(UInt32.self,at:offset)
            let type=lookTable.readLE(UInt16.self,at:offset+6); offset+=8
            maximum=max(maximum,marker)
            if let width=scalarWidth(type) {
                guard offset+width<=lookTable.count else{throw Q3TransportError.invalidPacket("Truncated Leica Look scalar.")}; offset+=width
            } else if type==0xFFFF {
                guard offset<lookTable.count else{throw Q3TransportError.invalidPacket("Truncated Leica Look string.")}
                let bytes=Int(lookTable[offset])*2; offset+=1
                guard offset+bytes<=lookTable.count else{throw Q3TransportError.invalidPacket("Truncated Leica Look string data.")}; offset+=bytes
            } else if (type & 0x4000) != 0 {
                guard offset+4<=lookTable.count else{throw Q3TransportError.invalidPacket("Truncated Leica Look array.")}
                let count=Int(lookTable.readLE(UInt32.self,at:offset)); offset+=4
                guard let width=scalarWidth(type & 0x0FFF) else{throw Q3TransportError.invalidPacket(String(format:"Unknown Leica Look array type 0x%04X.",type))}
                guard count<=16*1024*1024/width,offset+count*width<=lookTable.count else{throw Q3TransportError.invalidPacket("Invalid Leica Look array length.")}
                offset+=count*width
            } else { throw Q3TransportError.invalidPacket(String(format:"Unknown Leica Look field type 0x%04X.",type)) }
        }
        guard maximum>=0x2000000F,maximum<0x20FFFFFF else{throw Q3TransportError.invalidPacket("No valid Leica Look record markers.")}
        return maximum+1
    }

    private static func scalarWidth(_ type:UInt16)->Int? {
        switch type { case 1,2:return 1; case 3,4:return 2; case 5,6:return 4; case 7,8:return 8; case 9,10:return 16; default:return nil }
    }
    private static func prefix(_ d:inout Data,marker:UInt32,code:UInt16,type:UInt16) {
        d.appendLE(marker); d.appendLE(code); d.appendLE(type)
    }
    private static func appendUInt32(_ d:inout Data,marker:UInt32,code:UInt16,value:UInt32) {
        prefix(&d,marker:marker,code:code,type:0x0006); d.appendLE(value)
    }
    private static func appendString(_ d:inout Data,marker:UInt32,code:UInt16,value:String) {
        prefix(&d,marker:marker,code:code,type:0xFFFF)
        let units=Array(value.utf16.prefix(253))
        d.append(UInt8(units.count+1))
        for u in units { d.appendLE(u) }
        d.appendLE(UInt16(0))
    }
    private static func appendByteArray(_ d:inout Data,marker:UInt32,code:UInt16,value:Data) {
        prefix(&d,marker:marker,code:code,type:0x4002); d.appendLE(UInt32(value.count)); d.append(value)
    }
}

/// Generates the same icon container dimensions seen in Leica FOTOS uploads:
/// Windows BMP, 180x90, 1-bit. The artwork itself is an original simple IA mark.
public enum LeicaLookIcon {
    public static func make(name:String) -> Data {
        let width=180, height=90, rowBytes=24, pixelBytes=rowBytes*height
        var pixels=[UInt8](repeating:0,count:pixelBytes)

        func set(_ x:Int,_ y:Int) {
            guard x>=0,x<width,y>=0,y<height else{return}
            let by=height-1-y
            let i=by*rowBytes+(x>>3)
            pixels[i] |= UInt8(0x80 >> (x & 7))
        }
        func h(_ x0:Int,_ x1:Int,_ y:Int,_ t:Int=2){ for yy in y..<(y+t){for x in x0...x1{set(x,yy)}} }
        func v(_ x:Int,_ y0:Int,_ y1:Int,_ t:Int=2){ for xx in x..<(x+t){for y in y0...y1{set(xx,y)}} }
        // Border + stylized I / A. No Leica artwork is copied.
        h(10,169,10,2); h(10,169,79,2); v(10,10,80,2); v(168,10,80,2)
        h(42,70,26,3); h(42,70,64,3); v(55,26,66,3)
        for i in 0...38 { for t in 0..<3 { set(105-i/2+t,65-i); set(105+i/2+t,65-i) } }
        h(95,115,50,3)
        // six tiny ticks = six-slot Infinite Arch set
        for i in 0..<6 { h(128+i*5,130+i*5,68,2) }

        var d=Data()
        let fileSize=62+pixelBytes+2 // Leica capture declares 2162 image bytes; preserve that shape.
        d.append(contentsOf:[0x42,0x4D])
        d.appendLE(UInt32(fileSize)); d.appendLE(UInt32(0)); d.appendLE(UInt32(62))
        d.appendLE(UInt32(40)); d.appendLE(Int32(width)); d.appendLE(Int32(height))
        d.appendLE(UInt16(1)); d.appendLE(UInt16(1)); d.appendLE(UInt32(0)); d.appendLE(UInt32(pixelBytes+2))
        d.appendLE(Int32(11811)); d.appendLE(Int32(11811)); d.appendLE(UInt32(0)); d.appendLE(UInt32(0))
        d.append(contentsOf:[0xFF,0xFF,0xFF,0x00, 0x00,0x00,0x00,0x00])
        d.append(contentsOf:pixels); d.append(contentsOf:[0,0])
        return d
    }
}

// MARK: - Direct Q3 PTP/IP transport

public struct DirectQ3Transport:Q3Transport {
    public let state:Q3TransportState = .live
    public var host:String
    public var port:UInt16
    public var accessClientID:String?
    public var accessClientName:String
    public init(host:String="192.168.54.1",port:UInt16=15740,accessClientID:String?=nil,accessClientName:String="iPhone") {
        self.host=host; self.port=port; self.accessClientID=accessClientID; self.accessClientName=accessClientName
    }

    /// Replays only the observed FOTOS access-control request. If the camera reports
    /// an encrypted/unpaired state, no confirmation request is sent.
    public func requestAccess(clientID:String,clientName:String="iPhone") async throws -> Q3AccessReport {
        let h=host
        return try await Task.detached { try Q3AccessControl.request(host:h,clientID:clientID,clientName:clientName) }.value
    }

    /// Safe end-to-end diagnostic: access control followed by the read-only 0x9033 query.
    public func authorizedLookProbe(clientID:String,clientName:String="iPhone") async throws -> String {
        let report=try await requestAccess(clientID:clientID,clientName:clientName)
        guard report.isOpen else { throw Q3TransportError.accessControl("camera did not enter open mode. \(report.finalResponse)") }
        return "\(report.description)\n\(try await readOnlyLookProbe())"
    }

    /// Opens only PTP/IP and runs read-only operation 0x9033. It deliberately does
    /// not touch the fragile HTTP access-control state machine.
    public func readOnlyLookProbe() async throws -> String {
        let h=host,p=port
        let byteCount=try await Task.detached {
            let s=try Q3Session(host:h,port:p); defer{s.close()}
            try s.open()
            return try s.readLookPropertyList().count
        }.value
        return "0x9033=OK (\(byteCount) bytes)"
    }

    public func probe() async throws -> String {
        let h=host,p=port
        return try await Task.detached {
            let s=try Q3Session(host:h,port:p)
            defer{s.close()}
            try s.open()
            return "Connected to Leica Q3 at \(h):\(p)"
        }.value
    }

    public func listLooks() async throws -> [String] {
        let h=host,p=port
        let count=try await Task.detached {
            let s=try Q3Session(host:h,port:p); defer{s.close()}
            try s.open()
            return try s.readLookPropertyList().count
        }.value
        return ["Leica Look property list: \(count) bytes"]
    }

    public func install(_ request:Q3InstallRequest) async throws {
        guard let clientID=accessClientID else {
            throw Q3TransportError.accessControl("upload is locked until a paired FOTOS client ID is supplied and the camera reports open mode.")
        }
        let report=try await requestAccess(clientID:clientID,clientName:accessClientName)
        guard report.isOpen else { throw Q3TransportError.accessControl("upload blocked; camera returned \(report.finalResponse)") }
        let h=host,p=port,r=request
        try await Task.detached {
            guard FileManager.default.fileExists(atPath:r.cubePath) else { throw Q3TransportError.cubeMissing(r.cubePath) }
            let cube=try Data(contentsOf:URL(fileURLWithPath:r.cubePath))
            let s=try Q3Session(host:h,port:p)
            defer{s.close()}
            try s.open()
            let lookTable=try s.readLookPropertyList()
            let marker=try LeicaLookPayload.nextRecordMarker(from:lookTable)
            let payload=try LeicaLookPayload.build(lookID:r.lookID,name:r.name,baseStyle:r.baseStyle,cube:cube,recordMarker:marker)
            try s.uploadLook(payload)
        }.value
    }
}

private final class Q3Session:@unchecked Sendable {
    let host:String; let port:UInt16
    var command:TCPConnection?; var event:TCPConnection?
    var connectionNumber:UInt32=0; var transaction:UInt32=0
    init(host:String,port:UInt16)throws{self.host=host;self.port=port}

    func open() throws {
        let c=try TCPConnection(host:host,port:port); command=c
        var initBody=Data(repeating:0,count:16) // FOTOS 6.1.1 sends a zero GUID on this Q3 path.
        for u in "OLS".utf16 { initBody.appendLE(u) }
        initBody.appendLE(UInt16(0)); initBody.appendLE(UInt16(1))
        try c.sendPacket(type:1,body:initBody)
        let ack=try c.readPacket()
        guard ack.type==2,ack.body.count>=4 else { throw Q3TransportError.invalidPacket("Expected InitCommandAck (type 2).") }
        connectionNumber=ack.body.readLE(UInt32.self,at:0)

        let e=try TCPConnection(host:host,port:port); event=e
        var eb=Data(); eb.appendLE(connectionNumber)
        try e.sendPacket(type:3,body:eb)
        let ea=try e.readPacket()
        guard ea.type==4 else { throw Q3TransportError.invalidPacket("Expected InitEventAck (type 4).") }

        // Mirror the minimum FOTOS session setup seen in the live capture.
        transaction=0
        try sendCommand(op:0x1002,phase:1,params:[UInt32.random(in:1...0xFFFF)]) // OpenSession
        try expectOK(tx:0)
        transaction=1
        try sendCommand(op:0x9005,phase:1,params:[0x0000FF55]) // Leica vendor session enable
        try expectOK(tx:1)
        transaction=2
    }

    func uploadLook(_ payload:Data)throws {
        let tx=transaction
        try sendCommand(op:0x9035,phase:2,params:[])
        var start=Data(); start.appendLE(tx); start.appendLE(UInt64(payload.count))
        try command!.sendPacket(type:9,body:start)
        let chunk=1000
        var off=0
        while payload.count-off > chunk {
            var b=Data(); b.appendLE(tx); b.append(payload.subdata(in:off..<(off+chunk)))
            try command!.sendPacket(type:10,body:b); off+=chunk
        }
        var end=Data(); end.appendLE(tx); if off<payload.count { end.append(payload.subdata(in:off..<payload.count)) }
        try command!.sendPacket(type:12,body:end)
        try expectOK(tx:tx)
        transaction &+= 1
    }

    func readLookPropertyList()throws->Data {
        let tx=transaction
        try sendCommand(op:0x9033,phase:1,params:[0x0000FFFF,0xFFFFFFFF])
        var result=Data(), expectedLength:UInt64?, sawEnd=false
        while true {
            let p=try command!.readPacket()
            switch p.type {
            case 9: // StartData
                guard p.body.count>=12,p.body.readLE(UInt32.self,at:0)==tx else{continue}
                expectedLength=p.body.readLE(UInt64.self,at:4)
                guard expectedLength!<=16*1024*1024 else { throw Q3TransportError.invalidPacket("Look table is implausibly large.") }
            case 10,12: // Data / EndData
                guard p.body.count>=4,p.body.readLE(UInt32.self,at:0)==tx else{continue}
                result.append(p.body.dropFirst(4)); if p.type==12{sawEnd=true}
            case 7:
                guard p.body.count>=6 else { throw Q3TransportError.invalidPacket("Short response packet.") }
                let code=p.body.readLE(UInt16.self,at:0),rtx=p.body.readLE(UInt32.self,at:2)
                guard rtx==tx else{continue}
                guard code==0x2001 else{throw Q3TransportError.cameraResponse(code,tx)}
                guard sawEnd else{throw Q3TransportError.invalidPacket("0x9033 completed without EndData.")}
                if let expectedLength,expectedLength != UInt64(result.count) {
                    throw Q3TransportError.invalidPacket("0x9033 declared \(expectedLength) bytes but sent \(result.count).")
                }
                transaction &+= 1
                return result
            default: continue
            }
        }
    }

    func close(){ command?.close(); event?.close(); command=nil; event=nil }

    private func sendCommand(op:UInt16,phase:UInt32,params:[UInt32])throws {
        var b=Data(); b.appendLE(phase); b.appendLE(op); b.appendLE(transaction); for p in params{b.appendLE(p)}
        try command!.sendPacket(type:6,body:b)
    }

    private func expectOK(tx:UInt32)throws {
        while true {
            let p=try command!.readPacket()
            if p.type==7 {
                guard p.body.count>=6 else { throw Q3TransportError.invalidPacket("Short response packet.") }
                let code=p.body.readLE(UInt16.self,at:0), rtx=p.body.readLE(UInt32.self,at:2)
                if rtx != tx { continue }
                guard code==0x2001 else { throw Q3TransportError.cameraResponse(code,tx) }
                return
            }
            // Ignore asynchronous/data packets that are unrelated to the transaction being awaited.
        }
    }
}

private enum Q3AccessControl {
    static func request(host:String,clientID:String,clientName:String)throws->Q3AccessReport {
        guard isSafeToken(clientID),isSafeToken(clientName) else {
            throw Q3TransportError.accessControl("client ID/name contains characters unsafe for the captured request format.")
        }
        let c=try TCPConnection(host:host,port:80); defer{c.close()}
        let path="/cam.cgi?mode=accctrl&type=req_acc&value=\(clientID)&value2=\(clientName)"
        let request="GET \(path) HTTP/1.1\r\nHost: \(host)\r\nCache-Control: no-cache\r\nAccept: */*\r\nUser-Agent: Leica%20FOTOS/1022 CFNetwork/3896.100.1.2.1 Darwin/27.0.0\r\nAccept-Language: en-US,en;q=0.9\r\nAccept-Encoding: gzip, deflate\r\nConnection: keep-alive\r\n\r\n"
        guard let bytes=request.data(using:.utf8) else{throw Q3TransportError.invalidPacket("Could not encode access request.")}
        try c.writeRaw(bytes)
        let first=try readHTTPResponse(c)
        let firstStatus=first.split(separator:",",omittingEmptySubsequences:false).first.map(String.init) ?? ""
        let firstState=first.split(separator:",",omittingEmptySubsequences:false).last.map(String.init) ?? ""

        // The successful FOTOS trace confirms an under-research/open response once.
        // Never repeat on encrypted/no-message states: an earlier live test showed
        // that doing so turns the response into err_critical.
        guard firstStatus=="ok_under_research",firstState=="open" else {
            return Q3AccessReport(firstResponse:first,confirmationResponse:nil)
        }
        try c.writeRaw(bytes)
        return Q3AccessReport(firstResponse:first,confirmationResponse:try readHTTPResponse(c))
    }

    private static func isSafeToken(_ s:String)->Bool {
        !s.isEmpty && s.utf8.allSatisfy { b in
            (b>=48 && b<=57) || (b>=65 && b<=90) || (b>=97 && b<=122) || b==45 || b==95
        }
    }

    private static func readHTTPResponse(_ c:TCPConnection)throws->String {
        var header=Data(),tail=[UInt8]()
        while tail != [13,10,13,10] {
            let byte=try c.readExactly(1); header.append(byte)
            tail.append(byte[byte.startIndex]); if tail.count>4{tail.removeFirst()}
            guard header.count<=64*1024 else{throw Q3TransportError.invalidPacket("Oversized HTTP access response header.")}
        }
        guard let text=String(data:header,encoding:.utf8) else{throw Q3TransportError.invalidPacket("Invalid HTTP access response header.")}
        let lines=text.components(separatedBy:"\r\n")
        guard lines.first?.contains(" 200 ")==true else{throw Q3TransportError.accessControl(lines.first ?? "missing HTTP status")}
        guard let lengthLine=lines.first(where:{$0.lowercased().hasPrefix("content-length:")}),
              let length=Int(lengthLine.split(separator:":",maxSplits:1)[1].trimmingCharacters(in:.whitespaces)),length>=0,length<=64*1024
        else{throw Q3TransportError.invalidPacket("HTTP access response has no valid Content-Length.")}
        let body=try c.readExactly(length)
        guard let value=String(data:body,encoding:.utf8) else{throw Q3TransportError.invalidPacket("Invalid access response body.")}
        return value.trimmingCharacters(in:.whitespacesAndNewlines)
    }
}

private struct PTPIPPacket { var type:UInt32; var body:Data }

private final class TCPConnection {
    private var fd:Int32 = -1
    init(host:String,port:UInt16)throws {
        #if canImport(Darwin)
        fd=socket(AF_INET,SOCK_STREAM,0)
        #else
        fd=socket(AF_INET,Int32(SOCK_STREAM.rawValue),0)
        #endif
        guard fd>=0 else { throw Q3TransportError.socket(String(cString:strerror(errno))) }
        var tv=timeval(tv_sec:10,tv_usec:0)
        _=withUnsafePointer(to:&tv){ setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,$0,UInt32(MemoryLayout<timeval>.size)) }
        var addr=sockaddr_in(); addr.sin_family=sa_family_t(AF_INET); addr.sin_port=port.bigEndian
        let ok=host.withCString{ inet_pton(AF_INET,$0,&addr.sin_addr) }
        guard ok==1 else { close(); throw Q3TransportError.socket("Invalid IPv4 address \(host).") }
        let rc=withUnsafePointer(to:&addr){ p in p.withMemoryRebound(to:sockaddr.self,capacity:1){ connect(fd,$0,socklen_t(MemoryLayout<sockaddr_in>.size)) } }
        guard rc==0 else { let s=String(cString:strerror(errno)); close(); throw Q3TransportError.socket("\(host):\(port): \(s)") }
    }
    func close(){ if fd>=0 { _=DarwinOrGlibcClose(fd); fd = -1 } }
    deinit{close()}
    func sendPacket(type:UInt32,body:Data)throws {
        var d=Data(); d.appendLE(UInt32(8+body.count)); d.appendLE(type); d.append(body); try writeAll(d)
    }
    func readPacket()throws->PTPIPPacket {
        let h=try readExactly(8); let n=h.readLE(UInt32.self,at:0), t=h.readLE(UInt32.self,at:4)
        guard n>=8,n<=16*1024*1024 else { throw Q3TransportError.invalidPacket("Invalid packet length \(n).") }
        return PTPIPPacket(type:t,body:try readExactly(Int(n)-8))
    }
    func writeRaw(_ d:Data)throws { try writeAll(d) }
    private func writeAll(_ d:Data)throws {
        try d.withUnsafeBytes { raw in
            guard let base=raw.baseAddress else{return}; var off=0
            while off<d.count {
                let n=send(fd,base.advanced(by:off),d.count-off,0)
                if n<=0 { throw Q3TransportError.socket(String(cString:strerror(errno))) }; off+=n
            }
        }
    }
    func readExactly(_ count:Int)throws->Data {
        if count==0{return Data()}; var out=Data(count:count); var off=0
        try out.withUnsafeMutableBytes { raw in
            guard let base=raw.baseAddress else{return}
            while off<count {
                let n=recv(fd,base.advanced(by:off),count-off,0)
                if n==0 { throw Q3TransportError.socket("Camera closed the connection.") }
                if n<0 { throw Q3TransportError.socket(String(cString:strerror(errno))) }; off+=n
            }
        }; return out
    }
}

@inline(__always) private func DarwinOrGlibcClose(_ fd:Int32)->Int32 {
    #if canImport(Darwin)
    return Darwin.close(fd)
    #else
    return Glibc.close(fd)
    #endif
}

extension Data {
    mutating func appendLE<T:FixedWidthInteger>(_ v:T) { var x=v.littleEndian; Swift.withUnsafeBytes(of:&x){append(contentsOf:$0)} }
    func readLE<T:FixedWidthInteger>(_ t:T.Type,at i:Int)->T {
        precondition(i+MemoryLayout<T>.size<=count)
        return withUnsafeBytes { raw in
            let p=raw.baseAddress!.advanced(by:i)
            var v:T=0; memcpy(&v,p,MemoryLayout<T>.size); return T(littleEndian:v)
        }
    }
}
