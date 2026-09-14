import XCTest
@testable import IALUTCore

final class IALUTCoreTests:XCTestCase {
    func testIdentityResampleCount() throws {
        var v=[RGB](); for b in 0..<2 { for g in 0..<2 { for r in 0..<2 { v.append(RGB(Double(r),Double(g),Double(b))) } } }
        let a=LUT3D(title:"id",size:2,values:v).resampled(to:17)
        XCTAssertEqual(a.values.count,4913)
        XCTAssertEqual(a.values.first,RGB(0,0,0)); XCTAssertEqual(a.values.last,RGB(1,1,1))
    }

    func testLeicaIconShapeMatchesCapturedContainer() {
        let d=LeicaLookIcon.make(name:"Presence")
        XCTAssertEqual(d.count,2224)
        XCTAssertEqual(Array(d.prefix(2)),[0x42,0x4D])
        XCTAssertEqual(d.withUnsafeBytes{$0.load(fromByteOffset:18,as:UInt32.self)},180)
        XCTAssertEqual(d.withUnsafeBytes{$0.load(fromByteOffset:22,as:UInt32.self)},90)
    }

    func testLeicaUploadPayloadSchema() throws {
        let cube=Data("#Created by: test\nTITLE \"Presence\"\nLUT_3D_SIZE 17\n".utf8)
        let d=try LeicaLookPayload.build(lookID:1001,name:"Presence",baseStyle:"Standard",cube:cube)
        XCTAssertEqual(d.prefix(4),Data([6,0,0,0]))
        // First captured property: marker 0x20000014, D861, uint32 0x0006, then Look ID.
        XCTAssertEqual(Array(d[4..<16]),[0x14,0x00,0x00,0x20,0x61,0xD8,0x06,0x00,0xE9,0x03,0x00,0x00])
        XCTAssertNotNil(d.range(of:Data([0x44,0xDC,0xFF,0xFF])))
        XCTAssertNotNil(d.range(of:Data([0x86,0xDC,0x02,0x40])))
        XCTAssertNotNil(d.range(of:Data([0x60,0xD8,0x02,0x40])))
        XCTAssertNotNil(d.range(of:cube))
    }

    func testLeicaRecordMarkerAllocation() throws {
        let cube=Data("LUT_3D_SIZE 17\n".utf8)
        let existing=try LeicaLookPayload.build(lookID:7,name:"Brass",cube:cube,recordMarker:0x20000014)
        XCTAssertEqual(try LeicaLookPayload.nextRecordMarker(from:existing),0x20000015)
        let next=try LeicaLookPayload.build(lookID:8,name:"Chrome",cube:cube,recordMarker:0x20000015)
        XCTAssertEqual(Array(next[4..<8]),[0x15,0x00,0x00,0x20])
    }
}
