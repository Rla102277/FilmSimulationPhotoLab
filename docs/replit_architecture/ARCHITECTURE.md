# Architecture

## Topology

```text
Browser
   |
   | HTTPS
   v
Replit: Infinite Arch Photo Lab
   |-- React UI
   |-- FastAPI API
   |-- PostgreSQL
   |-- Look/version registry
   |-- color engine
    |-- Leica/Fuji/software compilers
    |-- validation and preview
    `-- downloadable artifacts
```

## Product boundary

Photo Lab creates, inspects, translates, previews, validates, and downloads Look
artifacts. The web service never discovers or connects to a camera. Generated
packages may include a self-contained local Python injector derived from the
proven v1.2 uploader; networking occurs only when the user runs that script
locally.

Historical PTP/IP, FOTOS-session, camera Wi-Fi, Fuji USB/network, packet-capture,
and installer work is research rather than active architecture.

## Look model

```text
LookFamily
  -> LookVersion
      -> CameraImplementation (Leica Q3 43)
      -> CameraImplementation (Fuji X-E5)
      -> CameraImplementation (Fuji GFX50R)
      -> CameraImplementation (Software)
```

## Color source types

- CUBE
- DCP
- LRTemplate
- XMP
- reference image / calibration pair
- Leica payload
- Fuji recipe

All imported source assets should be immutable by checksum.

## Leica compile boundary

The v1.2 writer proves a six-property binary record:

1. `D861` Look ID
2. `DC44` UTF-16LE name
3. `DC86` BMP icon bytes
4. `D860` plaintext 17-cube bytes
5. `D864` authoritative type value
6. `D866` authoritative base value

The compiler preserves property order, data types, lengths, encoding, and raw
assets. Every build is parsed again and compared with the requested inputs before
download. No official SD-card container or filename convention is claimed where
v1.2 does not prove one.
