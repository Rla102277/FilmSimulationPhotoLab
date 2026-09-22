# Leica Look Engine: September 2026 repair

The editable graph remains the master. Preview LUTs, desktop CUBEs, Leica payloads and iPhone installers are derived artifacts.

## Corrected behavior

- Source CUBE domains are honored, including during 17³ resampling. Wide indices prevent overflow when sampling 33/65-point tables.
- Floating-point graph values survive between nodes. General CUBE input accepts negative and above-one values within the format's numerical range. Desktop exports use 33³ or 64³ grids without output clipping; camera packages use bounded 17³ output. The preview target is explicit.
- Graph evaluation reports per-channel values below zero, above one and exactly zero before final output mapping. Exact zero is not itself an error. No extrapolation is applied to invent missing source data.
- Disabled and zero-strength components do not block a Look. Active unsupported components block preview/export with a reason instead of silently disappearing. Stale preview responses are discarded.
- Monochrome preview and package agree. Grading uses the chosen hue and continuous tonal masks; grading balance and monochrome filters are evaluated.
- Hald imports work. XMP/LRTemplate point curves are extracted, including channel-specific curves. These are creative operations on rendered RGB, not a reproduction of Adobe's raw processing.
- DCP raw camera-calibration matrices and unevaluated hue/saturation tables are inspection-only. A DCP selected from the catalog contributes its usable tone curve, not an alleged full DCP conversion.
- Saved versions, snapshots, metadata and active workspace survive reload. Versioned records use separate tables and routes from existing saved Looks. Ownership checks protect each account's version history and active workspace. The pending Replit persistence task was adapted rather than applied over newer code.
- Packages contain the editable graph, component provenance and source hashes, validated payloads, documentation and a standalone iPhone Python injector. Selected Looks share one installer; duplicate camera IDs/names are rejected.

## Beta clipping report

A supplied report described 419 clipped channel values in a Kodachrome export (R38/G166/B215). The original exported files and processing graph were not supplied, so those counts and the reported image artifacts have not been reproduced.

Confirmed in code: the old graph clamped after every node and the general CUBE parser rejected extended-range output. The regression `exposure +1 → exposure -1` lost highlights above 0.5. It now reproduces identity, including across a 4,096-step gradient. The legacy procedural film generator also defers clamping until final camera output.

The bundled Kodachrome 64 sources already contain exact zeros: the 36³ standard file has R1208/G2486/B100; the generic variant has R5245/G171/B51. This is not proof of erroneous clipping or evidence that these are the beta tester's files. Higher resolution does not recover information absent from the source.

Adobe's authored [CUBE specification (mirrored PDF)](https://kono.phpage.fr/images/a/a1/Adobe-cube-lut-specification-1.0.pdf), introduction and §5.7, permits output outside 0..1. Desktop-host color management and image bit depth still affect rendering. The JPEG browser preview is not a measurement of 16/32-bit Photoshop output or camera rendering.

## Validation

Run from the repository with its dependencies installed:

```sh
PATH="$PWD/.venv/bin:$PATH" DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q
npm run typecheck
npm run build
```

The suite checks all nine authoritative v1.2 payloads byte-for-byte; the reference archive is unchanged. It also exercises extended-range desktop exports, bounded camera exports, LUT domains and indexing, point curves, supported/unsupported graph paths, standalone and combined installers, version retention and account ownership. Local browser checks cover real catalog selection, chart preview, save-version, favorites/notes, and workspace restoration after reload.

Camera installation and Photoshop profile creation require device/application verification; this repair does not claim either was performed. The FOTOS-assisted transport is retained from v1.2. Camera readback confirms Look table metadata, not a full LUT checksum.
