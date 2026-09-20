import Foundation
import ImageCaptureCore
import IALUTCore

@MainActor
final class USBQ3Bridge: NSObject, ICDeviceBrowserDelegate, ICDeviceDelegate {
    static let shared = USBQ3Bridge()

    private let browser = ICDeviceBrowser()
    private weak var q3: ICCameraDevice?
    private var nextTransaction: UInt32 = 1

    override private init() {
        super.init()
        browser.delegate = self
        browser.browsedDeviceTypeMask = .camera
    }

    func probe() async throws -> String {
        let camera = try await cameraReady()
        let result = try await send(camera: camera, operation: 0x1001, parameters: [], outData: nil) // GetDeviceInfo
        try requireOK(result.response, operation: 0x1001)

        let operations = PTPUSB.decodeDeviceInfoOperations(result.inData)
        let hasEnable = operations.contains(0x9005)
        let hasUpload = operations.contains(0x9035)
        let serial = camera.serialNumberString ?? "unknown"
        let supported = operations.isEmpty
            ? "DeviceInfo returned, but operation list was not decoded"
            : String(format: "0x9005 %@ · 0x9035 %@", hasEnable ? "YES" : "NO", hasUpload ? "YES" : "NO")

        return "USB PTP OK — \(camera.name ?? "LEICA Q3") — serial \(serial) — \(supported)"
    }

    func readLookPropertyList() async throws -> String {
        let camera = try await cameraReady()

        // FOTOS enables Leica's vendor session before Look operations.
        let enable = try await send(camera: camera, operation: 0x9005, parameters: [0x0000FF55], outData: nil)
        try requireOK(enable.response, operation: 0x9005)

        // These are the two exact 0x9033 parameter values observed in the FOTOS/Q3 capture.
        // This is read-only: no data-out payload is supplied.
        var reports: [String] = []
        for parameter: UInt32 in [0x0000FFFF, 0xFFFFFFFF] {
            let result = try await send(camera: camera, operation: 0x9033, parameters: [parameter], outData: nil)
            guard let parsed = PTPUSB.responseCode(result.response) else {
                throw USBQ3Error.invalidResponse(operation: 0x9033, hex: result.response.hexPrefix(48))
            }
            if parsed.code == 0x2001 && !result.inData.isEmpty {
                let decoded = LeicaLookListDecoder.decode(result.inData)
                reports.append(String(format: "param 0x%08X → 0x%04X · %d bytes · %@", parameter, parsed.code, result.inData.count, decoded))
            } else {
                reports.append(String(format: "param 0x%08X → 0x%04X · %d bytes", parameter, parsed.code, result.inData.count))
            }
        }
        return "Q3 Look List READ — " + reports.joined(separator: " | ")
    }


    /// MVP control write: exact official Silver CUBE + official 180x90 Leica icon,
    /// sent with the known downloadable Leica Look ID 24.
    func installMVPOfficialSilver() async throws -> String {
        guard let cubeURL = Bundle.module.url(forResource: "Silver", withExtension: "CUBE", subdirectory: "Resources"),
              let iconURL = Bundle.module.url(forResource: "Silver", withExtension: "bmp", subdirectory: "Resources") else {
            throw Q3TransportError.invalidPacket("Bundled Silver MVP resources are missing.")
        }
        let cube = try Data(contentsOf: cubeURL)
        let icon = try Data(contentsOf: iconURL)
        try await installRaw(lookID: 24, name: "Silver", baseStyle: "Standard", cube: cube, icon: icon)
        return "MVP WRITE OK — official Silver (ID 24) accepted with 0x2001."
    }

    /// MVP custom-data test: neutral/identity LUT carried under an otherwise valid
    /// downloadable Leica Look identity (Cine, ID 27). If this succeeds, the Q3
    /// accepts arbitrary LUT data through the native Look uploader.
    func installMVPCustomIdentity() async throws -> String {
        guard let cubeURL = Bundle.module.url(forResource: "IAIdentityAsCine", withExtension: "CUBE", subdirectory: "Resources"),
              let iconURL = Bundle.module.url(forResource: "CineTest", withExtension: "bmp", subdirectory: "Resources") else {
            throw Q3TransportError.invalidPacket("Bundled custom-data MVP resources are missing.")
        }
        let cube = try Data(contentsOf: cubeURL)
        let icon = try Data(contentsOf: iconURL)
        try await installRaw(lookID: 27, name: "Cine", baseStyle: "Standard", cube: cube, icon: icon)
        return "MVP CUSTOM LUT OK — identity LUT accepted as downloadable Look ID 27 (0x2001)."
    }

    private func installRaw(lookID: UInt32, name: String, baseStyle: String, cube: Data, icon: Data) async throws {
        let camera = try await cameraReady()
        let payload = try LeicaLookPayload.build(
            lookID: lookID,
            name: name,
            baseStyle: baseStyle,
            cube: cube,
            icon: icon
        )

        let enable = try await send(
            camera: camera,
            operation: 0x9005,
            parameters: [0x0000FF55],
            outData: nil
        )
        try requireOK(enable.response, operation: 0x9005)

        let upload = try await send(
            camera: camera,
            operation: 0x9035,
            parameters: [],
            outData: payload
        )
        try requireOK(upload.response, operation: 0x9035)
    }

    func install(_ request: Q3InstallRequest) async throws {
        guard FileManager.default.fileExists(atPath: request.cubePath) else {
            throw Q3TransportError.cubeMissing(request.cubePath)
        }

        let camera = try await cameraReady()
        let cube = try Data(contentsOf: URL(fileURLWithPath: request.cubePath))
        let payload = try LeicaLookPayload.build(
            lookID: request.lookID,
            name: request.name,
            baseStyle: request.baseStyle,
            cube: cube
        )

        // FOTOS sends this Leica vendor-session enable before Look operations.
        let enable = try await send(camera: camera, operation: 0x9005, parameters: [0x0000FF55], outData: nil)
        try requireOK(enable.response, operation: 0x9005)

        // Same Leica Look operation recovered from FOTOS. ImageCaptureCore handles the
        // USB PTP data phase; `payload` is the exact property-list blob sent as data-out.
        let upload = try await send(camera: camera, operation: 0x9035, parameters: [], outData: payload)
        try requireOK(upload.response, operation: 0x9035)
    }

    // MARK: Device discovery/session

    private func cameraReady() async throws -> ICCameraDevice {
        // On macOS, ICDeviceBrowser does not use requestControlAuthorization; that API is unavailable.
        // Starting the browser is sufficient for USB camera discovery.
        if !browser.isBrowsing { browser.start() }

        for _ in 0..<60 {
            if let camera = findQ3() {
                q3 = camera
                camera.delegate = self
                if !camera.hasOpenSession {
                    try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                        camera.requestOpenSession(options: nil) { error in
                            if let error { continuation.resume(throwing: error) }
                            else { continuation.resume() }
                        }
                    }
                }
                return camera
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        throw USBQ3Error.notFound
    }

    private func findQ3() -> ICCameraDevice? {
        if let q3 { return q3 }
        for device in browser.devices ?? [] {
            guard let camera = device as? ICCameraDevice else { continue }
            let name = camera.name ?? ""
            if camera.usbVendorID == 6808 && camera.usbProductID == 9078 { return camera }
            if name.localizedCaseInsensitiveContains("LEICA Q3") { return camera }
        }
        return nil
    }

    func deviceBrowser(_ browser: ICDeviceBrowser, didAdd device: ICDevice, moreComing: Bool) {
        guard let camera = device as? ICCameraDevice else { return }
        let name = camera.name ?? ""
        if (camera.usbVendorID == 6808 && camera.usbProductID == 9078) || name.localizedCaseInsensitiveContains("LEICA Q3") {
            q3 = camera
        }
    }

    func deviceBrowser(_ browser: ICDeviceBrowser, didRemove device: ICDevice, moreGoing: Bool) {
        if let current = q3, current === device { q3 = nil }
    }

    func device(_ device: ICDevice, didOpenSessionWithError error: (any Error)?) { }
    func device(_ device: ICDevice, didCloseSessionWithError error: (any Error)?) { }
    func didRemove(_ device: ICDevice) {
        if let current = q3, current === device { q3 = nil }
    }

    // MARK: PTP

    private func send(camera: ICCameraDevice, operation: UInt16, parameters: [UInt32], outData: Data?) async throws -> (response: Data, inData: Data) {
        let tx = nextTransaction
        nextTransaction &+= 1
        let command = PTPUSB.command(operation: operation, transaction: tx, parameters: parameters)

        return try await withCheckedThrowingContinuation { continuation in
            // ImageCaptureCore's Swift completion arguments are the PTP data-in payload
            // first and the PTP response container second (matching the legacy selector's
            // inData:response: ordering). GetDeviceInfo proved this on the Q3: the first
            // Data begins with PTP DeviceInfo StandardVersion 0x006E, while the second
            // contains the 0x2001 response container.
            camera.requestSendPTPCommand(command, outData: outData) { inData, response, error in
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume(returning: (response, inData)) }
            }
        }
    }

    private func requireOK(_ response: Data, operation: UInt16) throws {
        guard let parsed = PTPUSB.responseCode(response) else {
            throw USBQ3Error.invalidResponse(operation: operation, hex: response.hexPrefix(48))
        }
        guard parsed.code == 0x2001 else {
            throw USBQ3Error.cameraResponse(operation: operation, code: parsed.code, transaction: parsed.transaction)
        }
    }
}

enum USBQ3Error: LocalizedError {
    case notFound
    case invalidResponse(operation: UInt16, hex: String)
    case cameraResponse(operation: UInt16, code: UInt16, transaction: UInt32)

    var errorDescription: String? {
        switch self {
        case .notFound:
            return "LEICA Q3 not found over USB. Quit Image Capture, connect USB-C directly, and set the Q3 USB mode to PTP."
        case .invalidResponse(let operation, let hex):
            return String(format: "USB PTP 0x%04X returned an unreadable response: %@", operation, hex)
        case .cameraResponse(let operation, let code, let transaction):
            return String(format: "Q3 rejected USB PTP operation 0x%04X with response 0x%04X (transaction %u).", operation, code, transaction)
        }
    }
}

private enum PTPUSB {
    static func command(operation: UInt16, transaction: UInt32, parameters: [UInt32]) -> Data {
        var data = Data()
        data.appendLEUSB(UInt32(12 + parameters.count * 4))
        data.appendLEUSB(UInt16(1)) // PTP USB command container
        data.appendLEUSB(operation)
        data.appendLEUSB(transaction)
        for p in parameters { data.appendLEUSB(p) }
        return data
    }

    static func responseCode(_ data: Data) -> (code: UInt16, transaction: UInt32)? {
        // ImageCaptureCore returns the standard 12-byte-or-larger PTP response container.
        guard data.count >= 12 else { return nil }
        let length: UInt32 = data.readLEUSB(at: 0)
        let type: UInt16 = data.readLEUSB(at: 4)
        guard length >= 12, type == 3 else { return nil }
        let code: UInt16 = data.readLEUSB(at: 6)
        let tx: UInt32 = data.readLEUSB(at: 8)
        return (code, tx)
    }

    static func decodeDeviceInfoOperations(_ data: Data) -> [UInt16] {
        var payload = data
        if data.count >= 12 {
            let type: UInt16 = data.readLEUSB(at: 4)
            if type == 2 { payload = data.subdata(in: 12..<data.count) }
        }

        // PTP DeviceInfo dataset:
        // StandardVersion u16, VendorExtensionID u32, VendorExtensionVersion u16,
        // VendorExtensionDesc PTP string, FunctionalMode u16, OperationsSupported AUINT16.
        var offset = 0
        guard payload.count >= 8 else { return [] }
        offset += 2 + 4 + 2
        guard skipPTPString(payload, offset: &offset), offset + 2 + 4 <= payload.count else { return [] }
        offset += 2
        let count: UInt32 = payload.readLEUSB(at: offset); offset += 4
        guard count <= 4096, offset + Int(count) * 2 <= payload.count else { return [] }
        var out: [UInt16] = []
        out.reserveCapacity(Int(count))
        for _ in 0..<count {
            let op: UInt16 = payload.readLEUSB(at: offset); offset += 2
            out.append(op)
        }
        return out
    }

    private static func skipPTPString(_ data: Data, offset: inout Int) -> Bool {
        guard offset < data.count else { return false }
        let count = Int(data[offset]); offset += 1
        let bytes = count * 2
        guard offset + bytes <= data.count else { return false }
        offset += bytes
        return true
    }
}

private extension Data {
    mutating func appendLEUSB<T: FixedWidthInteger>(_ value: T) {
        var v = value.littleEndian
        Swift.withUnsafeBytes(of: &v) { append(contentsOf: $0) }
    }

    func readLEUSB<T: FixedWidthInteger>(at offset: Int) -> T {
        precondition(offset + MemoryLayout<T>.size <= count)
        return withUnsafeBytes { raw in
            var value: T = 0
            memcpy(&value, raw.baseAddress!.advanced(by: offset), MemoryLayout<T>.size)
            return T(littleEndian: value)
        }
    }

    func hexPrefix(_ maxBytes: Int) -> String {
        prefix(maxBytes).map { String(format: "%02X", $0) }.joined(separator: " ")
    }
}


private enum LeicaLookListDecoder {
    private struct LookRecord {
        var id: UInt32?
        var slot: UInt32?
        var name: String?
        var type: UInt32?
        var base: UInt32?
    }

    static func decode(_ data: Data) -> String {
        let b = [UInt8](data)
        guard b.count >= 4 else { return "short data" }

        func u16(_ p: Int) -> UInt16 {
            UInt16(b[p]) | (UInt16(b[p + 1]) << 8)
        }

        func u32(_ p: Int) -> UInt32 {
            UInt32(b[p]) |
            (UInt32(b[p + 1]) << 8) |
            (UInt32(b[p + 2]) << 16) |
            (UInt32(b[p + 3]) << 24)
        }

        func u64(_ p: Int) -> UInt64 {
            UInt64(u32(p)) | (UInt64(u32(p + 4)) << 32)
        }

        func scalarWidth(_ type: UInt16) -> Int? {
            switch type {
            case 0x0001, 0x0002: return 1
            case 0x0003, 0x0004: return 2
            case 0x0005, 0x0006: return 4
            case 0x0007, 0x0008: return 8
            case 0x0009, 0x000A: return 16
            default: return nil
            }
        }

        let fieldCount = Int(u32(0))
        var o = 4
        var records: [LookRecord] = []
        var current = LookRecord()

        func finishCurrent() {
            if current.id != nil || current.slot != nil || current.name != nil {
                records.append(current)
                current = LookRecord()
            }
        }

        for index in 0..<fieldCount {
            guard o + 8 <= b.count else {
                return "\(fieldCount) fields; truncated at field \(index), byte \(o)/\(b.count)"
            }

            _ = u32(o)
            let prop = u16(o + 4)
            let type = u16(o + 6)
            o += 8

            var scalar: UInt64?
            var stringValue: String?

            if let width = scalarWidth(type) {
                guard o + width <= b.count else {
                    return String(format: "%d fields; truncated scalar prop 0x%04X", fieldCount, prop)
                }

                switch width {
                case 1: scalar = UInt64(b[o])
                case 2: scalar = UInt64(u16(o))
                case 4: scalar = UInt64(u32(o))
                case 8: scalar = u64(o)
                default: scalar = nil
                }
                o += width

            } else if type == 0xFFFF {
                guard o < b.count else { return "truncated string" }
                let n = Int(b[o])
                o += 1
                let bytesNeeded = n * 2
                guard o + bytesNeeded <= b.count else {
                    return String(format: "%d fields; truncated string prop 0x%04X", fieldCount, prop)
                }

                if n == 0 {
                    stringValue = ""
                } else {
                    let contentBytes = max(0, bytesNeeded - 2)
                    let raw = Data(b[o..<(o + contentBytes)])
                    stringValue = String(data: raw, encoding: .utf16LittleEndian) ?? "<string>"
                }
                o += bytesNeeded

            } else if (type & 0x4000) != 0 && type != 0x4002 {
                let elementType = type & 0x0FFF
                guard let width = scalarWidth(elementType), o + 4 <= b.count else {
                    return String(format: "%d fields; unknown array prop 0x%04X type 0x%04X", fieldCount, prop, type)
                }
                let n = Int(u32(o))
                o += 4
                let bytesNeeded = n * width
                guard o + bytesNeeded <= b.count else {
                    return String(format: "%d fields; truncated array prop 0x%04X", fieldCount, prop)
                }
                o += bytesNeeded

            } else if type == 0x4002 {
                guard o + 4 <= b.count else { return "truncated blob length" }
                let n = Int(u32(o))
                o += 4
                guard o + n <= b.count else {
                    return String(format: "%d fields; truncated blob prop 0x%04X len %d", fieldCount, prop, n)
                }
                o += n

            } else {
                return String(format: "%d fields; parsed %d; unknown prop 0x%04X type 0x%04X at byte %d",
                              fieldCount, index, prop, type, o - 8)
            }

            if prop == 0xD861 {
                finishCurrent()
                current.id = scalar.map { UInt32($0) }
            } else if prop == 0xD862 {
                current.slot = scalar.map { UInt32($0) }
            } else if prop == 0xDC44 {
                current.name = stringValue
            } else if prop == 0xD864 {
                current.type = scalar.map { UInt32($0) }
            } else if prop == 0xD866 {
                current.base = scalar.map { UInt32($0) }
            }
        }

        finishCurrent()

        let rows = records.enumerated().map { idx, r -> String in
            let slot = r.slot.map(String.init) ?? "?"
            let id = r.id.map(String.init) ?? "?"
            let name = r.name ?? "?"
            let type = r.type.map(String.init) ?? "?"
            let base = r.base.map(String.init) ?? "?"
            return "[\(idx)] slot \(slot) · ID \(id) · \(name) · type \(type) · base \(base)"
        }

        return "\(fieldCount) fields parsed OK · \(records.count) Look records\n" + rows.joined(separator: "\n")
    }
}

