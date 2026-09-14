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

## Cloud/local split

Replit: UI, API, DB, asset metadata, color engine, Look versioning, compilers, job queue.
Local IA Camera Bridge: direct camera transport only.
