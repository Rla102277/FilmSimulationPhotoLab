# Infinite Arch Photo Lab — Persistent Agent Context

## Authority

`reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip` is immutable ground truth.
SHA-256: `1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f`.

The actual authoritative v1.2 manifest must override older chat summaries, previous experimental packs, and reconstructed assumptions.

## Exact v1.2 Look identities

| ID | Key | Name | Leica Base | Mono |
|---:|---|---|---|---|
| 1001 | invitation | IA Invitation | Monochrome | true |
| 1002 | witness | IA Witness | Monochrome | true |
| 1003 | zone | IA Zone | Monochrome | true |
| 1004 | presence | IA Presence | Standard | false |
| 1005 | threshold | IA Threshold | Standard | false |
| 1006 | americannegative | IA American Negative | Standard | false |
| 1007 | 400h | IA Kin | Standard | false |
| 1008 | natura | IA Natura | Standard | false |
| 1009 | ember | IA Ember | Standard | false |

## Product direction

Build **Infinite Arch Photo Lab** as a web-first camera-independent color system. Leica and Fuji are target implementations of the same Look families.

## Hard rule

Before changing any working Leica implementation, create a regression test proving the existing behavior.

## Product boundary

The product is a web-based Look factory. Keep normal browser-to-FastAPI HTTP.
Do not add server-side camera networking, pairing, discovery, sessions, reads,
writes, heartbeat, bridge jobs, or camera status. A download package may include
a local Python injector derived from the proven v1.2 uploader; it is never
executed or imported by the web application. Historical transport work belongs
only under research/reference/legacy paths.

## Running on Replit

The main web workflow runs `bash scripts/run.sh`, which starts FastAPI on
`0.0.0.0:5000`. It builds the React/TypeScript frontend before starting FastAPI.
The Photo Lab is at `/`, interactive API documentation is at `/docs`, and the
health endpoint is `/api/health`.

Run `python main.py` separately for the offline migration integrity report.

## Implemented application boundaries

- The Leica library, inventory, CUBE parser/renderer, payload compiler/inspector,
  Fuji recipe registry, immutable source assets, and downloads are exposed
  through same-origin `/api` routes.
- Application records use PostgreSQL. Original imported assets are immutable and
  deduplicated by SHA-256.
- Generated Leica payloads must compile, parse, and compare successfully before
  download. v1.2 does not prove an official SD-card import container; do not
  claim one.
- Browser preview rendering supports JPEG and TIFF derivatives. It never changes
  the uploaded original or the authoritative archive.
