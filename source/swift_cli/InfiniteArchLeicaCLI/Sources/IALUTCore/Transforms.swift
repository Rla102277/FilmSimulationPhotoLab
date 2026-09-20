
import Foundation

public enum LUTTransforms {
    @inline(__always) private static func lum(_ c:RGB)->Double { 0.2126*c.r+0.7152*c.g+0.0722*c.b }
    @inline(__always) private static func tone(_ x:Double,_ c:Double,_ h:Double,_ s:Double)->Double {
        var y=(x-0.5)*(1+c)+0.5
        y += h*pow(max(y,0),2.4)*0.22
        y += s*pow(max(1-y,0),2.4)*0.22
        return min(max(y,0),1)
    }

    public static func apply(_ recipe:InfiniteArchRecipe,to source:LUT3D,outputSize:Int=17,title:String?=nil)->LUT3D {
        let base=source.resampled(to:outputSize)
        var out=[RGB](); out.reserveCapacity(base.values.count)
        for original in base.values {
            var c=original
            if recipe.monochrome {
                let y=lum(c); c=RGB(y,y,y)
            } else {
                let y=lum(c), sat=1+recipe.saturation
                c=RGB(y+(c.r-y)*sat,y+(c.g-y)*sat,y+(c.b-y)*sat)
                c.r += recipe.warmth*0.08; c.b -= recipe.warmth*0.08
            }
            c=RGB(tone(c.r,recipe.contrast,recipe.highlights,recipe.shadows),
                  tone(c.g,recipe.contrast,recipe.highlights,recipe.shadows),
                  tone(c.b,recipe.contrast,recipe.highlights,recipe.shadows))
            out.append((original*(1-recipe.strength)+c*recipe.strength).clamped())
        }
        return LUT3D(title:title ?? recipe.name,size:outputSize,values:out)
    }
}

public enum LookSetExporter {
    public static func export(manifest:LookSetManifest,sourceLoader:(String)throws->LUT3D,to folder:URL) throws -> URL {
        let root=folder.appendingPathComponent(manifest.name.replacingOccurrences(of:"/",with:"-"))
        try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        for slot in manifest.slots {
            let source=try sourceLoader(slot.sourcePath)
            let lut=LUTTransforms.apply(slot.recipe,to:source,outputSize:17,title:slot.name)
            let fn=String(format:"%02d_%@.CUBE",slot.slot,slot.name.replacingOccurrences(of:" ",with:"_"))
            try CubeIO.write(lut,url:root.appendingPathComponent(fn),lookID:slot.slot,baseStyle:slot.baseStyle)
        }
        let data=try JSONEncoder.pretty.encode(manifest)
        try data.write(to:root.appendingPathComponent("lookset.json"))
        return root
    }
}

extension JSONEncoder {
    static var pretty:JSONEncoder { let e=JSONEncoder(); e.outputFormatting=[.prettyPrinted,.sortedKeys]; return e }
}
