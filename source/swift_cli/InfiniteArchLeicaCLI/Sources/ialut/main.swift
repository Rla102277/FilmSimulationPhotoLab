
import Foundation
import IALUTCore

func die(_ s:String)->Never { fputs(s+"\n",stderr); exit(2) }
let a=CommandLine.arguments
guard a.count>=3 else { die("Usage: ialut input.cube output.CUBE [Invitation|Witness|Memory|Truth|Presence|Threshold|Stillness]") }
let src=URL(fileURLWithPath:a[1]), dst=URL(fileURLWithPath:a[2]), rn=a.count>3 ? a[3]:"Presence"
guard let recipe=InfiniteArchRecipe.defaults.first(where:{$0.name.lowercased()==rn.lowercased()}) else { die("Unknown recipe \(rn)") }
do {
    let lut=try CubeIO.read(url:src)
    let out=LUTTransforms.apply(recipe,to:lut,outputSize:17,title:recipe.name)
    try CubeIO.write(out,url:dst,lookID:1,baseStyle:recipe.monochrome ? "Monochrome":"Standard")
    print("Wrote \(dst.path) — \(out.size)^3 / \(out.values.count) points")
} catch { die(error.localizedDescription) }
