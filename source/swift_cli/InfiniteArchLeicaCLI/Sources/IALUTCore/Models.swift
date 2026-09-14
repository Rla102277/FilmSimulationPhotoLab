
import Foundation

public struct RGB: Equatable, Codable, Sendable {
    public var r: Double
    public var g: Double
    public var b: Double
    public init(_ r: Double, _ g: Double, _ b: Double) { self.r = r; self.g = g; self.b = b }
    public func clamped() -> RGB { RGB(min(max(r,0),1), min(max(g,0),1), min(max(b,0),1)) }
    public static func +(lhs: RGB, rhs: RGB) -> RGB { RGB(lhs.r+rhs.r, lhs.g+rhs.g, lhs.b+rhs.b) }
    public static func -(lhs: RGB, rhs: RGB) -> RGB { RGB(lhs.r-rhs.r, lhs.g-rhs.g, lhs.b-rhs.b) }
    public static func *(lhs: RGB, rhs: Double) -> RGB { RGB(lhs.r*rhs, lhs.g*rhs, lhs.b*rhs) }
}

public struct LUT3D: Sendable {
    public var title: String
    public var size: Int
    public var values: [RGB]
    public var domainMin = RGB(0,0,0)
    public var domainMax = RGB(1,1,1)

    public init(title: String, size: Int, values: [RGB]) {
        self.title = title; self.size = size; self.values = values
    }

    @inline(__always) private func idx(_ r:Int,_ g:Int,_ b:Int) -> Int { r + g*size + b*size*size }

    public func sample(_ input: RGB) -> RGB {
        let rr = (input.r-domainMin.r)/max(domainMax.r-domainMin.r,1e-12)
        let gg = (input.g-domainMin.g)/max(domainMax.g-domainMin.g,1e-12)
        let bb = (input.b-domainMin.b)/max(domainMax.b-domainMin.b,1e-12)

        let x=min(max(rr,0),1)*Double(size-1), y=min(max(gg,0),1)*Double(size-1), z=min(max(bb,0),1)*Double(size-1)
        let x0=Int(floor(x)), x1=min(x0+1,size-1)
        let y0=Int(floor(y)), y1=min(y0+1,size-1)
        let z0=Int(floor(z)), z1=min(z0+1,size-1)
        let tx=x-Double(x0), ty=y-Double(y0), tz=z-Double(z0)
        func mix(_ a:RGB,_ b:RGB,_ t:Double)->RGB { a*(1-t)+b*t }

        let c00=mix(values[idx(x0,y0,z0)],values[idx(x1,y0,z0)],tx)
        let c10=mix(values[idx(x0,y1,z0)],values[idx(x1,y1,z0)],tx)
        let c01=mix(values[idx(x0,y0,z1)],values[idx(x1,y0,z1)],tx)
        let c11=mix(values[idx(x0,y1,z1)],values[idx(x1,y1,z1)],tx)
        return mix(mix(c00,c10,ty),mix(c01,c11,ty),tz)
    }

    public func resampled(to newSize:Int, title:String?=nil) -> LUT3D {
        var out=[RGB](); out.reserveCapacity(newSize*newSize*newSize)
        for b in 0..<newSize {
            for g in 0..<newSize {
                for r in 0..<newSize {
                    out.append(sample(RGB(Double(r)/Double(newSize-1),Double(g)/Double(newSize-1),Double(b)/Double(newSize-1))).clamped())
                }
            }
        }
        return LUT3D(title:title ?? self.title,size:newSize,values:out)
    }
}

public enum LUTError: Error, LocalizedError {
    case invalid(String), unsupported(String), imageLoadFailed
    public var errorDescription:String? {
        switch self {
        case .invalid(let s): return "Invalid LUT: \(s)"
        case .unsupported(let s): return "Unsupported LUT: \(s)"
        case .imageLoadFailed: return "Could not load HALD image."
        }
    }
}

public struct InfiniteArchRecipe: Identifiable, Hashable, Codable, Sendable {
    public var id: String { name }
    public var name:String
    public var monochrome:Bool
    public var strength:Double
    public var contrast:Double
    public var saturation:Double
    public var warmth:Double
    public var highlights:Double
    public var shadows:Double

    public init(name:String, monochrome:Bool=false, strength:Double=1, contrast:Double=0, saturation:Double=0, warmth:Double=0, highlights:Double=0, shadows:Double=0) {
        self.name=name; self.monochrome=monochrome; self.strength=strength; self.contrast=contrast
        self.saturation=saturation; self.warmth=warmth; self.highlights=highlights; self.shadows=shadows
    }

    // Starting translations of Randy's Fuji-side intent. These are deliberately editable.
    public static let defaults:[InfiniteArchRecipe] = [
        .init(name:"Invitation", monochrome:true, contrast:-0.08, highlights:-0.08, shadows:-0.05),
        .init(name:"Witness", monochrome:true, contrast:0.16, highlights:0.06, shadows:0.12),
        .init(name:"Memory", monochrome:true, contrast:-0.12, warmth:0.02, highlights:-0.14, shadows:-0.08),
        .init(name:"Truth", contrast:-0.06, saturation:-0.05, highlights:-0.08, shadows:-0.05),
        .init(name:"Presence", contrast:-0.08, saturation:-0.10, warmth:0.04, highlights:-0.14, shadows:-0.05),
        .init(name:"Threshold", contrast:0.05, saturation:0.12, warmth:0.02, highlights:-0.03, shadows:0.05),
        .init(name:"Stillness", contrast:-0.04, saturation:0.10, warmth:0.03, highlights:-0.14)
    ]
}

public struct LookSlot: Identifiable, Codable, Hashable, Sendable {
    public var id:Int { slot }
    public var slot:Int
    public var name:String
    public var sourcePath:String
    public var recipe:InfiniteArchRecipe
    public var baseStyle:String
    public init(slot:Int,name:String,sourcePath:String,recipe:InfiniteArchRecipe,baseStyle:String="Standard") {
        self.slot=slot; self.name=name; self.sourcePath=sourcePath; self.recipe=recipe; self.baseStyle=baseStyle
    }
}

public struct LookSetManifest: Codable, Sendable {
    public var formatVersion:Int = 1
    public var name:String
    public var target:String = "Leica Q3 research"
    public var slots:[LookSlot]

    public init(name: String, slots: [LookSlot], formatVersion: Int = 1, target: String = "Leica Q3 research") {
        self.formatVersion = formatVersion
        self.name = name
        self.target = target
        self.slots = slots
    }
}
