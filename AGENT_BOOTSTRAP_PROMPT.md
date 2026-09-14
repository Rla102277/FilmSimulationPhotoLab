# First prompt for Replit Agent

Continue the existing **Infinite Arch Photo Lab** project. Do not restart the
Leica reverse engineering.

The immutable source of truth is:

`reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip`

Its required SHA-256 is:

`1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f`

Before refactoring anything, run `python main.py` and the unit tests. Inventory
the authoritative archive and compare generated payloads byte-for-byte where a
known-good fixture exists. Never rewrite a fixture to make a regression pass.

Established Leica behavior:

- Leica FOTOS creates the authorized PTP/IP relationship.
- An independent client can reuse the surviving authenticated session.
- The observed camera endpoint is `192.168.54.1:15740`.
- Standard DeviceInfo is opcode `0x1001`.
- Leica Look-table read is opcode `0x9033`.
- Leica Look write is opcode `0x9035`.
- `0x2001` is success; `0x201E` can mean the FOTOS session remains open.
- Session ID `0x412` and a transaction base beginning at `0x10000` were
  successful in captured tests.
- Custom Look IDs 1001–1009 avoid Leica-reserved-ID aliasing.
- Leica expects a 17-cube with 4,913 bounded RGB rows in the empirically
  established red-fast order.
- A constant-magenta LUT proved the camera executes custom plaintext D860 LUT
  data. Corrected IA Presence then produced a visible intended result.

The authoritative v1.2 release supersedes all earlier reconstructed libraries,
ID-27 carrier experiments and two-bank installers. Keep those only for history
and regression analysis.

Build a web application with a Python service and a clean frontend. Separate:

1. Look families and versions.
2. Camera-specific implementations.
3. Immutable source assets with SHA-256 and provenance.
4. Leica payload compilation and inspection.
5. Preview rendering.
6. Fuji recipe and native-camera-processing research.
7. A small local **IA Camera Bridge** for hardware access.

The Replit server must never attempt direct access to the camera's private LAN
address. The local bridge performs Leica/Fuji transport and creates outbound,
authenticated jobs to the web service. Do not expose camera transport ports to
the public Internet. Use short-lived pairing tokens and Replit Secrets.

First milestone: preserve and display v1.2, validate all hashes, inspect payload
metadata, and implement regression tests. Only then refactor the compiler and
build bridge jobs. Fuji work follows after Leica regression parity is green.

