# Infinite Arch Photo Lab

A browser-based Look development and compilation tool.

## Active workflow

Source material (`CUBE`, `DCP`, `LRTemplate`, `XMP`, existing Leica payload,
reference image, or Fuji recipe) is translated by the Look engine into a target
implementation, validated, and downloaded.

The Replit application does not connect to cameras. There are no server-side
camera pairing, bridge, transport, read/write, or heartbeat features. A generated
download package may include a self-contained local Python injector derived from
the proven v1.2 FOTOS-assisted uploader; only that downloaded script communicates
with the camera when the user runs it locally.

## Leica Look Lab

The Leica compiler uses the authoritative v1.2 six-property record:
`D861`, `DC44`, `DC86`, `D860`, `D864`, and `D866`. It preserves property order,
data types, UTF-16LE encoding, binary lengths, icon bytes, CUBE structure, and
checksums. Generated payloads are parsed and compared to their requested inputs
before download.

The proven outputs are the Leica payload binary and a local injector package.
The project does not claim an official desktop or SD-card import container that
the v1.2 evidence does not establish.

## Run

`bash scripts/run.sh`

The React UI is served at `/`; FastAPI documentation is at `/docs`.

## Authority

`reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip` is immutable ground
truth with SHA-256
`1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f`.