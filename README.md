# Source-aware engine revision

Read [ENGINE_REVISION.md](ENGINE_REVISION.md) first for the repairs, supported inputs, Replit setup, and limitations. This revision preserves the interface and Leica transport while replacing the broken source-to-color path.

# Film Look Studio

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

## DCP → Leica 17³ CUBE

Creative DCP HueSat/Look tables bake into a compliant Leica CUBE (not camera ColorMatrix):

```bash
python scripts/dcp_to_leica_cube.py path/to/profile.dcp -o out.CUBE --look-id 1200 --name "My Look"
```

API (authenticated): `POST /api/studio/dcp/cube` with multipart `dcp` file.

In Look Builder, import a DCP and use the **CreativeInterpretation** component (not ColorMatrix).

## Run

`bash scripts/run.sh`

The React UI is served at `/`; FastAPI documentation is at `/docs`.

## Authority

`reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip` is immutable ground
truth with SHA-256
`1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f`.