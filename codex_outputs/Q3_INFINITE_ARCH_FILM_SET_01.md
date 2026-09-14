# Infinite Arch Q3 Film Set 01

Four film-inspired Leica Q3/Q3 43 Looks, built after custom LUT execution was
proven with IA Magenta Proof. All CUBEs contain exactly 4,913 bounded rows in the
camera's empirically verified red-fast order.

## IA Nostalgic

Amber-biased highlights, richer shadow color, and soft midtone/highlight tonality,
following Fujifilm's description of Nostalgic Negative as an old-album rendering
with rich shadow color and soft mids/highlights.

## IA Acros

Monochrome with clean gradation, open shadow detail, and crisp tonal separation.
This follows Fujifilm's description of ACROS as fine-grained, sharp, and rich in
shadow detail. A 3D LUT cannot synthesize physical or ISO-dependent grain.

## IA HP5

Monochrome with a firmer toe, stronger midtone contrast, and a controlled shoulder,
based on ILFORD's description of HP5 PLUS as an ISO-400 all-purpose film with
medium contrast, fine grain, sharpness, and broad exposure flexibility. Grain is
not included because it cannot be represented by a 3D color LUT.

## IA Edo 400

Low saturation, low contrast, muted warm colors, and a subtle blue-cyan cast.
ESCURA describes its Edo film as ISO 400 with a slight blue tint intended to evoke
Ukiyo-e; related official ESCURA material identifies low saturation and contrast
as central to its retro rendering.

## Installation model

Each package uses the proven ID-27/Standard carrier. Install one at a time: remove
the current ID-27 custom Look, connect through FOTOS, force-quit FOTOS while staying
on Q3 Wi-Fi, run `upload.py` in Pyto, and type only `go`.

The uploaders hash-check every asset, validate row count/range/color mode, require
the inherited authenticated session and live pre-read, calculate the next marker,
and allow exactly one `0x9035` write.
