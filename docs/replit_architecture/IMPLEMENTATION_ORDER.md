# Implementation Order

## Phase 0 — protect the proven Leica state

- Verify authoritative archive SHA-256.
- Inventory archive contents.
- Read `looks_manifest.json` from the archive directly.
- Preserve installers and known-good assets.
- Add regression tests before code cleanup.

## Phase 1 — Leica web migration

- API endpoint for authoritative manifest.
- Leica Looks UI.
- payload/source provenance view.
- bridge registration and heartbeat.
- bridge job model.
- read-only Leica camera Look-table job.
- parser and UI result.
- only then write/install.
- verify after install.
- pack installation with explicit failure states.

## Phase 2 — Photo Lab renderer

- asset upload metadata.
- JPEG/DNG/RAF identification.
- embedded JPEG extraction.
- CUBE renderer.
- before/after, split, blink, side-by-side.
- JPEG/TIFF derivative export.

## Phase 3 — Fuji recipe engine

- camera profiles for X-E5 and GFX50R.
- recipe schema/editor.
- IA Look-to-Fuji implementation mapping.
- Presence as the first high-value cross-camera match.
- comparison scoring.

## Phase 4 — Fuji native processing

- developer-only protocol lab.
- controlled single-variable X RAW Studio capture/diff experiments.
- native RAF processing job protocol.
- camera-generated output retrieval.

## Phase 5 — automated matching

- target image/reference matching.
- numerical color/tone metrics.
- perceptual similarity metrics.
- parameter optimization constrained by target camera capabilities.
