# Natura source map

Target: 36 user-provided Natura Classica / Natura 1600 JPEG scans. Main references: 0002/0013/0017–0023 for cyan-green ambient and warm signs; 0004/0032 for people; 0006/0007 for restrained daylight; 0030/0031 for blue hour; 0035/0036 for foliage and orange gates.

DCP ingredients: M9 Fuji Superia 1600 (65%), Fuji 800Z (25%), Fuji Superia 800 (10%). These weights describe relative HueSat table ingredients, not complete profile emulations. Both illuminant tables averaged and their common median across five candidates subtracted for hue and divided for saturation/value. Residuals capped and attenuated. T64 and Portra 100T were comparison candidates only, not weighted ingredients. No literal Natura 1600 profile was available in this set.

No M9 color/forward matrices, white balance, exposure or absolute profile tone curve were copied. DCP table encoding is linear; the relative deltas are deliberately adapted as bounded artistic HSV changes in display RGB, not evaluated as a DNG raw profile. The shared-table subtraction is an approximation and can remove common creative behavior as well as calibration. These scans are not matched input/output calibration pairs.

Final shaping: dense monotone tone curve, restrained blue saturation, modest green/cyan shaded-mid bias, warm upper-mid bias, neutral dark endpoint and bright white. Removed the prior large blue offset and tungsten/bleach-bypass ingredients. No grain or spatial glow is synthesized.

Other eight Looks are byte-identical to v1.0.
