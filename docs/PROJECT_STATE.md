# Project state — 2026-09-14

## Confirmed on the Leica Q3/Q3 43

1. FOTOS pairs/authenticates with the camera.
2. After FOTOS releases its sockets, its camera-side PTP/IP session can survive.
3. The independent Python client received `SessionAlreadyOpen` and successfully
   reused that session with transactions beginning at 65536 (`0x10000`).
4. DeviceInfo (`0x1001`) returned `0x2001` and 413 bytes.
5. Leica Look-table read (`0x9033`) returned `0x2001` and 833 bytes.
6. An unmodified official Bleach payload written with `0x9035` returned
   `0x2001`. Bleach appeared on camera and successfully processed a photograph.
7. A custom constant-magenta 17-cube made the entire rendered image magenta,
   proving that the Q3 executed custom plaintext D860 LUT data.
8. The first neutral-looking custom test was explained by LUT row order. The Q3
   uses the red-fast indexing used by the corrected generator.
9. Corrected IA Presence visibly worked on camera.

## Payload model

The decoded six-field Look upload contains these Leica properties:

- `D861`: Look ID
- `DC44`: UTF-16 Look name
- `DC86`: 180x90 1-bit BMP icon
- `D860`: plaintext 17-cube data
- `D864`: type (2 in working payloads)
- `D866`: base style (0 Standard, 1 Monochrome)

Writes are sent with `0x9035`. Look tables are read with `0x9033` using
parameters `0xFFFF, 0xFFFFFFFF`.

## Safety behavior retained in the working uploaders

- Asset hashes and LUT shape/range are checked before writing.
- A live DeviceInfo and Look-table read are required.
- A newly opened unauthenticated session is rejected by controlled writers.
- The write path is single-attempt; an ambiguous network failure is not retried.
- Post-write verification is attempted, with reconnect/reread required when the
  camera invalidates the inherited connection after committing a Look.

## Final authority

The user designated `Infinite_Arch_Leica_Looks_v1.2.zip` as the authoritative
final. It uses custom IDs 1001–1009. Its manifest, assets, self-contained Pyto
installer, folder uploader, source map, analysis and Kin comparison material are
preserved byte-for-byte in `reference/leica/v1.2/`.

The v1.2 archive's own notes state that IA Kin replaced IA 400H at ID 1007 and
that its offline installers generated identical payloads. Preserve those notes
and do not overstate camera testing beyond the confirmed chain above.

## Superseded material

The older ID-27 carrier packages were essential experiments but are not the
final library. The two six-Look bank installers used reserved IDs and a
hard-coded nine-Look assumption; they must not be run as production installers.
They remain under `source/experimental_legacy_banks/` and `codex_outputs/` for
forensic comparison only.

## Historical transport findings

The findings above explain how the six-property format was discovered. They are
preserved as research and are not active product behavior.

## Replit product

The long-term product is **Infinite Arch Photo Lab**:

- React/FastAPI web application
- Look/version library and immutable asset provenance
- Leica six-property parser, compiler, inspector, preview, validation, and downloads
- Fuji capability-aware recipe translation and export
- CUBE/DCP/LRTemplate/XMP source work and cross-camera matching

There is no active bridge, camera connection, camera read/write, or install path.

