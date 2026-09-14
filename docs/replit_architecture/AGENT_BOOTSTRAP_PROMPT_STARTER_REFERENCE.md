# Replit Agent Bootstrap Prompt

We are continuing an existing reverse-engineering and color-science project called **Infinite Arch Photo Lab**. Do not treat it as a new Leica research project.

## 1. Immutable Leica authority

The completed Leica implementation is:

`reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip`

Expected SHA-256:

`1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f`

This archive is immutable ground truth. Never modify, overwrite, normalize, regenerate, optimize, rename, or delete it. Earlier chat-derived Leica packs are non-authoritative.

Before any Leica refactor:

1. run `python scripts/verify_authoritative.py`;
2. inspect the ZIP itself;
3. inventory every file;
4. identify source vs generated vs executable vs documentation assets;
5. preserve known-good artifacts as fixtures;
6. create regression tests;
7. only then wrap/refactor existing implementation.

## 2. Exact authoritative Leica v1.2 manifest

- 1001 — IA Invitation — key `invitation` — base `Monochrome` — mono=true — cube SHA `9452ebfd550ce32ffce02077c45900842f42d6ba95e679afc39d0b615c631172`
- 1002 — IA Witness — key `witness` — base `Monochrome` — mono=true — cube SHA `8e26b914ab9e264185b7a27e72bb331e06d831c14d74159ff96bb1b404aaa0b8`
- 1003 — IA Zone — key `zone` — base `Monochrome` — mono=true — cube SHA `c7a24b78eaf058a39b420de71f1ac19a07ecc3e57b7dee3acc539a2170adc4d9`
- 1004 — IA Presence — key `presence` — base `Standard` — mono=false — cube SHA `06dae2aad0db2c84d4f842f6ce08a4bacacc914ea5a94c49060316f60e8c223a`
- 1005 — IA Threshold — key `threshold` — base `Standard` — mono=false — cube SHA `d704bcca8b24edb7ab1305bae01419e175d38015ffedd337a2ffc966cb4a50c0`
- 1006 — IA American Negative — key `americannegative` — base `Standard` — mono=false — cube SHA `d2c7aa4e5ae346cc8db8ed4fa2567273f33f5e65e2ab5e3e8708154cce4ecbb1`
- 1007 — IA Kin — key `400h` — base `Standard` — mono=false — cube SHA `d47bff06bc2130ae7c84f54a1803212830bdf9314b17ca5c94352c582f7d6bce`
- 1008 — IA Natura — key `natura` — base `Standard` — mono=false — cube SHA `180e125946c2ccca9513f6b5598a62709a93a0430d6902b0d69fa128c49eeae0`
- 1009 — IA Ember — key `ember` — base `Standard` — mono=false — cube SHA `78c2fb13ff052d8f022a0eff1cada13d6434b4a4cf15ac253857930508d1de5a`

Do not change these identities unless the user explicitly creates a later authoritative release.

## 3. Known solved Leica transport state

Do not restart the basic transport/authentication investigation. Existing project history established a working Leica Q3-family PTP/IP flow in which Leica FOTOS first establishes an authorized relationship and the independent Python client can reuse the surviving authorized camera state/session after FOTOS releases its sockets.

Historically confirmed protocol facts to preserve and regression-test where present in the authoritative code/traces:

- camera endpoint used: `192.168.54.1:15740`
- standard DeviceInfo opcode: `0x1001`
- Leica Look-table read: `0x9033`
- Leica Look upload/write: `0x9035`
- PTP success: `0x2001`
- `0x201E` may indicate an already-open surviving session rather than fatal failure
- session `0x412` was observed in successful traces
- custom Look IDs avoid Leica-reserved IDs

The authoritative v1.2 code wins if details differ.

## 4. Product goal

Build one web application: **Infinite Arch Photo Lab**.

A photographic Look is a master concept with camera-specific implementations.

Example:

IA Presence
- Leica Q3/Q3 43 implementation
- Fuji X-E5 implementation
- Fuji GFX50R implementation
- software LUT implementation
- DCP/XMP/Lightroom representation

The Look is the parent. Camera payloads/recipes are implementations.

## 5. Architecture

Use a monorepo with:

- React + TypeScript + Vite frontend
- Python FastAPI backend
- Python color/look core
- PostgreSQL
- persistent asset-storage abstraction
- local IA Camera Bridge

Do not attempt direct camera access from the Replit cloud service. Private addresses like `192.168.54.1` are reachable only by the local bridge while attached to the camera network.

### Replit/cloud responsibilities

- Look library and versioning
- source asset metadata/provenance
- CUBE/DCP/LRTemplate/XMP ingestion
- software preview rendering
- camera capability database
- Leica payload compilation/inspection
- Fuji recipe compilation/matching
- cross-camera comparison
- bridge pairing/job queue/logs
- user UI
- export

### IA Camera Bridge responsibilities

- local camera discovery
- Leica PTP/IP transport
- Fuji transport/protocol work
- read camera information
- read Leica Look table
- install/verify Leica payloads
- Fuji native processing jobs
- retrieve camera-generated outputs
- stream logs/results back to Replit

Keep the bridge small. Do not duplicate color logic in it.

## 6. Internal data model

Create these concepts separately:

- LookFamily
- LookVersion
- CameraImplementation
- SourceAsset
- CameraProfile
- ImageAsset
- Render
- Bridge
- BridgeJob
- BridgeLog
- LeicaPayload
- FujiRecipe

Look-family versions and camera-implementation versions are distinct.

## 7. IA Color Graph

Represent master Look intent as a graph/pipeline such as:

Input -> camera normalization -> WB intent -> tone -> matrix -> LUT -> shadow shaping -> highlight shaping -> chroma -> optional monochrome/filter behavior -> grain -> output

Target compilers use only capabilities available on that target.

## 8. Fuji Phase A — recipe engine

Initial targets:

- Fujifilm X-E5
- Fujifilm GFX50R

Model controls per body rather than assuming identical capabilities. Recipe fields may include film simulation, DR, highlights, shadows, color, sharpness, NR, clarity, grain, Color Chrome, Color Chrome Blue, WB mode, WB red shift, WB blue shift.

Do not invent final Fuji recipe values. Store and expose them, then populate them from the project's authoritative matching work.

## 9. Fuji Phase B — native camera processing

Long-term goal:

RAF -> selected IA Look -> target Fuji parameters -> local bridge -> connected Fuji camera native processing -> rendered output returned to Photo Lab.

Do not claim a generic cloud RAW renderer is identical to Fuji native X-Processor output.

Create a developer-only protocol lab for controlled X RAW Studio experiments and parameter diffs.

## 10. Safety / regression rules

Never:

- mutate the authoritative ZIP;
- rewrite fixtures to make a broken refactor pass;
- silently change Look IDs or names;
- use arbitrary camera bytes without checksum/metadata validation;
- expose local camera transport directly to the public Internet;
- mutate original RAW files;
- store durable runtime assets only on ephemeral deployed disk;
- begin massive Fuji reverse engineering before Leica regression coverage exists.

## 11. First milestone

Make Leica v1.2 reproducible in the web architecture without losing behavior:

1. verify package integrity;
2. read authoritative manifest;
3. expose Looks through API;
4. render Looks in web UI;
5. build bridge pairing/status;
6. support read-only camera Look-table job;
7. parse/display result;
8. add upload only after read/verification works;
9. verify after write;
10. add full-pack install with failure-safe validation.

## 12. Second milestone

Software Photo Lab preview:

- ingest JPEG/DNG/RAF metadata
- extract embedded preview when available
- apply CUBE preview
- A/B, split, blink, side-by-side
- JPEG/TIFF export

## 13. Third milestone

Fuji recipes and cross-camera matching.

## 14. Fourth milestone

Fuji native camera-side processing research/bridge implementation.

## 15. Work style

Work incrementally. Preserve proven behavior. Create a checkpoint after each green milestone. If a refactor differs from known-good Leica output, stop and diagnose instead of updating fixtures.

### First action now

Run `python scripts/verify_authoritative.py`, inspect the archive, and produce an inventory. Do not refactor Leica code yet.
