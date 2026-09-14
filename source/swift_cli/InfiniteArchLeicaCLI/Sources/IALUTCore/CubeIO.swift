import Foundation

public enum CubeIO {
    public static func read(url:URL) throws -> LUT3D {
        let text=try String(contentsOf:url,encoding:.utf8)
        var size:Int?, title=url.deletingPathExtension().lastPathComponent
        var dmin=RGB(0,0,0), dmax=RGB(1,1,1), vals=[RGB]()
        for raw in text.split(whereSeparator:\.isNewline) {
            let line=raw.trimmingCharacters(in:.whitespacesAndNewlines)
            if line.isEmpty || line.hasPrefix("#") { continue }
            if line.uppercased().hasPrefix("TITLE") {
                if let a=line.firstIndex(of:"\""), let b=line.lastIndex(of:"\""), a != b { title=String(line[line.index(after:a)..<b]) }
                continue
            }
            let p=line.split(whereSeparator:\.isWhitespace).map(String.init)
            guard !p.isEmpty else { continue }
            switch p[0].uppercased() {
            case "LUT_3D_SIZE": if p.count>1 { size=Int(p[1]) }
            case "DOMAIN_MIN": if p.count>=4 { dmin=RGB(Double(p[1]) ?? 0,Double(p[2]) ?? 0,Double(p[3]) ?? 0) }
            case "DOMAIN_MAX": if p.count>=4 { dmax=RGB(Double(p[1]) ?? 1,Double(p[2]) ?? 1,Double(p[3]) ?? 1) }
            case "LUT_1D_SIZE": throw LUTError.unsupported("1D LUTs are not supported.")
            default:
                if p.count>=3, let r=Double(p[0]), let g=Double(p[1]), let b=Double(p[2]) { vals.append(RGB(r,g,b)) }
            }
        }
        guard let n=size else { throw LUTError.invalid("Missing LUT_3D_SIZE.") }
        guard vals.count == n*n*n else { throw LUTError.invalid("Expected \(n*n*n) RGB rows; found \(vals.count).") }
        var lut=LUT3D(title:title,size:n,values:vals); lut.domainMin=dmin; lut.domainMax=dmax; return lut
    }

    public static func text(_ lut:LUT3D,lookID:Int?=nil,baseStyle:String="Standard") -> String {
        var s="#Created by: Infinite Arch Leica Look Builder\n"
        if let lookID { s += "#Unique Leica Look ID: \(lookID)\n" }
        s += "#Based Filmstyle Mode: \(baseStyle)\n\nTITLE \"\(lut.title.replacingOccurrences(of:"\"",with:""))\"\n\n"
        s += "#LUT size\nLUT_3D_SIZE \(lut.size)\n\n#data domain\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n\n#LUT data points\n"
        for c in lut.values { s += String(format:"%.6f %.6f %.6f\n",c.r,c.g,c.b) }
        return s
    }

    public static func data(_ lut:LUT3D,lookID:Int?=nil,baseStyle:String="Standard") -> Data {
        Data(text(lut,lookID:lookID,baseStyle:baseStyle).utf8)
    }

    public static func write(_ lut:LUT3D,url:URL,lookID:Int?=nil,baseStyle:String="Standard") throws {
        try text(lut,lookID:lookID,baseStyle:baseStyle).write(to:url,atomically:true,encoding:.utf8)
    }
}
