# Leica Q3 / Q3 43: custom Leica Looks research

**Research date:** September 9, 2026  
**Scope:** Leica Q3 and Q3 43 still-photo Leica Looks, Leica FOTOS transfer path, and official firmware 4.1.1.  
**Bottom line:** We found and inspected the correct Leica firmware. The update package is easy to inventory, but it does **not** contain editable Leica Look files. After this report was first written, the earlier task **“Trading Q2 For XT5 Package”** was recovered. That task proves a legitimate Leica FOTOS → Q3 Look transfer was already captured and decoded. The remaining problem is the privileged FOTOS session state required to make USB `0x9035` writes succeed.

> **Continuity correction:** Do not repeat the packet-capture or Look-format work proposed in the first version of this report. The recovered project had already cracked the APK encryption, the 17³ CUBE representation, the six-property upload envelope, and read-only Q3 Look enumeration. Resume at the authorization/session boundary described below.

## Executive result

1. Leica publishes separate, current 4.1.1 firmware files for the Q3 and Q3 43. Both were downloaded from Leica and preserved for static inspection.[^1]
2. The `.lfu` package uses a simple byte inversion at its outer layer. Reversing that reveals a `UPD` header, Q3-family model identifiers, and a 67-entry component map.
3. The Q3 identifies as `DC1231`; the Q3 43 identifies as `DC1232`. Both expose component entries named `lut_data` and `lut2_data`.
4. Those LUT-named entries are a false lead for this particular update: both are zero-filled reserved regions, byte-for-byte identical in the Q3 and Q3 43 packages. Their recorded SHA-256 values exactly match the corresponding zero-filled data.
5. No public Q3 Leica Looks uploader, Look-file specification, or Q3 `.lfu` unpacker was found. An older `LeicaHacks` repository targets older Leica M firmware, not the Q3 architecture.[^2]
6. The recovered project independently confirmed the community leads: FOTOS contains encrypted Look assets, `0x9033` reads the Q3 Look-property list, and a successful FOTOS upload uses `0x9035` over PTP/IP.
7. Leica officially says FOTOS transfers Looks into the Q3. The recovered capture shows exactly how the app sends a Look after its privileged connection is established.[^4]

## Where the earlier work actually stands

The first workspace audit did not find the older project because its detailed development history lived inside the ChatGPT task **“Trading Q2 For XT5 Package.”** That history has now been read.

The original local repository was named `InfiniteArchLeicaCLI` and was reported at `/Users/randyarchambault/Downloads/InfiniteArchLeicaCLI`. It is not present in the filesystem accessible to this Codex task, and the historical ZIP/PCAP/APK attachments are not currently exposed as reusable local files. The technical state is recoverable from the conversation, but the actual latest source repository still needs to be copied or attached here before code work continues.

### Recovered verified state

- Leica FOTOS 6.1.1 APK assets were decrypted successfully. The app uses `AES/GCM/NoPadding` with a 128-bit tag and an embedded 32-byte key supplied by `NativeKeyProvider.getKey()`.
- Decrypted Looks are ordinary plaintext `LUT_3D_SIZE 17` CUBE files (4,913 RGB points) with Leica comment metadata. Chrome was recovered as Leica Look ID 8; Bleach is ID 22.
- FOTOS calls `LooksService.uploadLook()` and native `IPPTCameraAPI::leSetLookPropList(...)` with ID, name, Look type, base style, icon bytes, and CUBE bytes.
- A successful Bleach transfer was captured from iPhone `192.168.54.10` to Q3 `192.168.54.1:15740`.
- That upload used Leica vendor operation `0x9035`, a 135,223-byte outbound payload, transaction `0x1d`, followed by camera response `0x2001 OK`.
- The six decoded upload properties were: `0xD861` ID 22, `0xDC44` name “Bleach,” `0xDC86` 2,224-byte icon, `0xD860` 132,912-byte plaintext CUBE, `0xD864` type 2, and `0xD866` base style 0.
- PTP/IP framing was decoded as command packet type 6, StartData type 9, Data type 10, EndData type 12, and response type 7.
- The Swift macOS harness uses ImageCaptureCore over USB. Q3 USB `VID:PID` is `1a98:2376`; standard device information works; the camera advertises `0x9005` and `0x9035`.
- USB `0x9033` with parameter `0x0000ffff` returns `0x2001` and a 750-byte, 56-field Look table.
- The camera reported: slot 0 Standard/ID 15/type 1/base 0; slot 1 Monochrome/ID 16/type 1/base 1; slot 2 Pure/ID 26/type 2/base 0; slot 3 Brass/ID 7/type 2/base 0; slot 4 Classic/ID 2/type 2/base 0; slot 5 Bleach/ID 22/type 2/base 0.
- An upload made from the USB harness with Leica's actual Silver LUT, actual 2,224-byte icon, and official ID 24 reached `0x9035` but returned `0x200f Access Denied`. This eliminates LUT data, icon, ID, and basic serialization as the primary problem.
- `0x9005 [0xff55]` succeeds. Leica remote enable `0x9030 [0,1]` also succeeds, including when performed in the same PTP session, but `0x9035` remains `0x200f`.
- `0x902d [2,1]`, derived from native `enablePairing()`, returns `0x2002 General Error` over USB.
- Properties `0xD69C` and `0xD69D` are read-only INT32 status values, both currently `0x2000000f`, and do not change after remote enable.
- The OSS bundle was already exhausted for this question; it contains the surrounding Linux/FreeRTOS stack, not Leica's proprietary authorization implementation.

## What Leica officially supports

Leica distinguishes three still-photo Look groups:

- **Core Looks:** Standard, Natural, Vivid, Monochrom Natural, and Monochrom High Contrast.
- **Essential Looks:** the current catalog includes Silver, Bleach, Teal, Brass, Chrome, Classic, Contemporary, Sepia, Blue, Selenium, and Eternal.
- **Artist/Partner Looks:** for example, the Greg Williams Look.

The official catalog identifies the Q3 and Q3 43 as compatible and says the selected effect is visible in Live View.[^5] Leica FOTOS is the supported installation channel; Leica says a connected compatible camera can hold up to six downloaded Looks.[^4]

The current Q3-family instructions impose different adjustment limits:

| Look class | In-camera customization |
|---|---|
| Core | Contrast, highlights, shadows, sharpness, saturation; some Core Looks also expose intensity |
| Essential | Intensity only |
| Artist/Partner | Not customizable |

The regular adjustment scale is `-2` through `+2`; intensity is percentage-based where offered.[^6] This matters because the existing user-facing controls are not a route to a truly custom color transform.

Leica Looks are also not the same thing as the downloadable **Leica Pure / Leica Cine LUTs** on the Q3 download page. Those LUT downloads and imported `.cub` files belong to the camera's video/L-Log workflow. The Q3 43 manual allows a custom video LUT from an SD card, with an eight-character filename and the unusual `.cub` extension, but this does not create a still-photo Leica Look.[^7]

For safe experimentation, shoot `DNG + JPG`. Leica describes DNG as the raw sensor data and JPG as the in-camera processed result; Leica's Q3 43 material says Look effects can be used while preserving the original DNG.[^8]

## Firmware acquired and verified

Official source page: [Leica Q3 downloads](https://leica-camera.com/en-US/photography/cameras/q/q3-black/downloads).[^1]

| Camera | Official firmware | Size | SHA-256 |
|---|---:|---:|---|
| Leica Q3 | [`Q3___411.lfu`](https://leica-camera.com/sites/default/files/Q3___411.lfu) | 201,162,752 bytes | `c6eb3eab11b4388e26f2b9e8662393f696accf2436f44b55a159a7038b6e07a7` |
| Leica Q3 43 | [`Q343_411.lfu`](https://leica-camera.com/sites/default/files/Q343_411.lfu) | 201,162,752 bytes | `8cf62346cd4f81c9af34278cdee9fafd96fd39cb1e98de8d27094dd7e633b185` |
| Leica Q3 OSS source bundle | [`pm-19562-OSS_codes.zip`](https://leica-camera.com/sites/default/files/pm-19562-OSS_codes.zip) | 277,144,657 bytes | `ab6531df4770a0dd0e67d090f470321bc294078e020b2f21286f1dc8d0e7bb18` |

The hashes above are local calculations over the exact downloaded files. Keep them as immutable reference samples; never test a modified firmware on the camera.

### Outer package format

The raw LFU begins with bytes such as `aa af bb ff`. XORing every byte with `0xff` reveals:

```text
55 50 44 00 ... 44 43 31 32 33 31 ...   UPD...DC1231   (Q3)
55 50 44 00 ... 44 43 31 32 33 32 ...   UPD...DC1232   (Q3 43)
```

The component table starts at `0x2e0`; records are `0x5c` bytes each. Each record includes a short component name, package offset, length, target address, flags, a 32-byte digest, and an additional 16-byte field. The packages expose 67 records, including:

- boot and application regions: `boot`, `loader1`, `program`, `compress_pr`, `postboot*_r`
- settings/calibration regions: `eep_*`, `menu_save`, `kizu_data`, `vkizu_data`, `lens_hist`
- connectivity regions: `wifi_info`, `bt_info`
- image/lens processing candidates: `pzm_data`, `lns_micon`, `dsp_kizu_*`, `raw_kizu_*`
- LUT-named regions: `lut_data`, `lut2_data`

Most substantive package regions remain high-entropy after the outer inversion. Their stored digests do not directly equal the SHA-256 of the inverted package slice, which is consistent with another encryption, compression, or installation-time transformation. The outer inversion is therefore an inventory layer, not a complete firmware decryption.

### Why `lut_data` and `lut2_data` are not our Look payload

Both 4.1.1 packages contain these identical records:

| Entry | Package offset | Length | Target address | Content | Recorded SHA-256 |
|---|---:|---:|---:|---|---|
| `lut_data` | `0x09e97e00` | `0x00220000` (2.125 MiB) | `0x09fa0000` | all zeros | `7b15c3f99be0c5f9ae0a0ecdc21d3a8c4dc8006aed712338a0ad06aa35382793` |
| `lut2_data` | `0x0a0b7e00` | `0x00860000` (8.375 MiB) | `0x0a1c0000` | all zeros | `6217bc4155fa384f23c6e11e7823877d36d13419e7941b5bcd25ed8e9d4644ee` |

Those digests are exactly the SHA-256 values of zero buffers of the listed lengths. The cautious interpretation is that these are reserved or device-resident LUT/calibration partitions that this updater clears, initializes, or leaves as placeholders. The names alone do not establish any link to downloadable Leica Looks.

### What the open-source bundle tells us

Leica's OSS archive contains upstream source packages including Linux 4.19.124, U-Boot, FreeRTOS 202212.00, glibc 2.27, BusyBox 1.27.2, libusb 1.0.26, MTD utilities, and networking components.[^1] That supports a hybrid embedded stack with Linux/networking plus real-time components.

It does **not** include Leica's proprietary image pipeline, FOTOS protocol library, Leica Look assets, encryption keys, or a Look compiler. The OSS bundle is useful architecture evidence, not the missing implementation.

## Connectivity and protocol leads

### USB/PTP baseline

A public gPhoto2 report identifies the Q3 as USB `VID:PID 1a98:2376`. Standard PTP discovery and trigger-capture worked for that reporter, while preview and capture-and-download were incomplete.[^9] This gives us a safe read-only baseline but no public Look-transfer implementation.

### Leica-specific Look operation — promising, not yet verified

One community researcher reports the following after inspecting Leica's app libraries and capturing Leica traffic:

- Leica cameras can expose a larger “admin” PTP surface after a private handshake.
- the Q3 uses a path referred to as `EPPC`, in contrast with an M11 `IPPT` path;
- operation `0x9033` is symbolized as `LEGetLookPropList`;
- Leica Look files that were once plaintext in app assets were later encrypted.[^3]

This is the best current lead, but it is still a forum report—not Leica documentation and not independently reproduced here. We should treat the operation name and code as hypotheses until a capture from our own Q3 confirms them.

No public repository was found containing `LEGetLookPropList`, a Q3 FOTOS handshake, a Look upload operation, or a current Look decoder.

## Recommended build path

The goal is a small, reversible tool that talks to **our own** Q3 and learns the official transfer, not a patched camera.

### Phase 1 — establish a clean baseline

1. Update the Q3 to official 4.1.1 if it is not already there; use Leica's unmodified file and normal update method.
2. Fully charge the battery.
3. Save or photograph every relevant user-profile and Look-slot setting.
4. Set `DNG + JPG` and install a known official Look into an otherwise unused slot.
5. Record camera model, firmware, FOTOS version, phone OS, selected Look, slot number, and timestamps.

### Phase 2 — capture one legitimate transfer

Use an isolated test network containing only the phone and a capture machine. Record:

- discovery traffic before FOTOS connects;
- pairing/session setup;
- a no-change FOTOS session;
- one official Look installation;
- Look listing before and after;
- a second installation of the same Look, if FOTOS permits it.

The most valuable comparison is **idle connected session versus one-Look transfer**. It should reveal whether the payload moves over ordinary HTTP, PTP/IP, a Leica framing layer, or multiple channels. Do not guess write endpoints or replay anything during the first capture.

Artifacts to preserve:

- the complete packet capture;
- decrypted application traffic only where it can be collected from a device and account we control;
- FOTOS application version and binary hash;
- phone diagnostic log around the transfer;
- Q3 state before and after;
- matched DNG/JPG test images made under fixed light with the Look disabled and enabled.

### Phase 3 — implement read-only discovery first

The first client should only:

1. discover the Q3;
2. establish the same authenticated session as FOTOS;
3. query camera identity and firmware;
4. enumerate installed Look slots and metadata;
5. save opaque responses without rewriting them.

Success means reproducing a Look-list response and, ideally, confirming whether `0x9033` really maps to `LEGetLookPropList` on a Q3.

### Phase 4 — decode the asset envelope

From two or more official Look downloads, determine:

- container framing and version;
- asset ID, display name, compatibility list, and slot metadata;
- payload size and whether it resembles a 1D/3D LUT, tone curves, matrices, or a richer processing recipe;
- compression;
- encryption nonce/IV and authentication tag;
- checksum or digital signature;
- whether authorization is tied to camera serial, app session, Leica account, or a global key.

Changing one controlled variable at a time is essential. Two downloads of the same Look can distinguish deterministic data from per-session encryption; the same Look sent to Q3 and Q3 43 can reveal camera binding.

### Phase 5 — decide whether custom upload is actually viable

There are three likely outcomes:

1. **Unsigned/open format:** create a compiler from a neutral transform to Leica's asset representation, then upload only to an unused slot.
2. **Encrypted but app-accessible format:** it may be possible to use the legitimate app session to wrap a custom payload, but only if integrity validation does not require a Leica signature.
3. **Leica-signed assets:** arbitrary in-camera still Looks are blocked without bypassing camera trust. At that point the sensible product is a companion workflow—custom DNG profiles/JPEG recipes that mimic the desired result—not firmware modification.

## Guardrails

- Do not flash a modified LFU. Static inspection is enough for the present phase.
- Do not overwrite factory calibration, EEPROM, lens, defect-map, or LUT partitions.
- Do not send unobserved or guessed Leica admin operations.
- Begin with enumeration and downloads; make the first write only after the official request, response, integrity fields, and recovery behavior are understood.
- Use an empty downloadable-Look slot, never a factory Core Look.
- Keep DNG originals and a reproducible color target series for every test.
- Restrict testing to a camera, phone, Leica account, and network we control.

## Deliverable included

`leica_lfu_inspector.py` is a read-only parser for this outer LFU structure. It:

- recognizes the Q3-family byte inversion;
- reports model code and raw version bytes;
- lists the 67 component records;
- marks zero-filled regions;
- compares each stored digest to its package slice while clearly marking layers that require further transformation.

Example:

```bash
python3 leica_lfu_inspector.py Q3___411.lfu
python3 leica_lfu_inspector.py --json Q343_411.lfu
```

It never writes to the firmware or communicates with a camera.

## Immediate next session

First restore the actual `InfiniteArchLeicaCLI` repository plus the successful FOTOS PCAP and Leica FOTOS 6.1.1 APK into this workspace. Then resume at one narrow target:

> Trace the FOTOS `libleica.so` connection initialization immediately before the successful captured `0x9035` and reproduce the missing authenticated/security session state in the existing Swift harness.

Do not repeat CUBE decoding, payload serialization, `0x9033` parsing, ID experiments, `0x9030`, `0x902d [2,1]`, or the `D69C/D69D` probes. Those paths are already resolved or ruled out.

## Sources

[^1]: Leica Camera, [Leica Q3 downloads: firmware 4.1.1, instructions, video LUTs, and OSS package](https://leica-camera.com/en-US/photography/cameras/q/q3-black/downloads).
[^2]: alexhude, [LeicaHacks](https://github.com/alexhude/LeicaHacks), an older Leica M firmware research repository; it does not claim Q3 support.
[^3]: Community reverse-engineering discussion, [“Leica SL3-S is codenamed Warp…”](https://www.reddit.com/r/Leica/comments/1h9xbw3/leica_sl3s_is_codenamed_warp_and_features_up_to/), especially the discussion of FOTOS, EPPC, encrypted Look assets, and `0x9033`. This is an unverified lead.
[^4]: Leica Camera, [Leica FOTOS](https://leica-camera.com/en-PT/photography/leica-apps/leica-fotos), “Transfer Leica Looks to Your Camera” and the six-Look limit.
[^5]: Leica Camera, [Leica Looks catalog and compatible cameras](https://leica-camera.com/en-int/photography/leica-looks).
[^6]: Leica Camera, [Q3/Q3 43 firmware 4.0.0 release notes](https://leica-camera.com/sites/default/files/EN_-4.0.0--Q-Family-Release-Notes.pdf), Leica Looks customization section; see also the current [Q3-family instructions](https://leica-camera.com/sites/default/files/pm-19546-Leica-Q3_Instructions_en.pdf).
[^7]: Leica Camera, [Leica Q3 43 instructions](https://leica-camera.com/sites/default/files/pm-113588-Leica-Q343_Instructions_en.pdf), “Importing a custom LUT profile.” This is a video LUT feature, not a still Leica Look.
[^8]: Leica Camera, [Leica Q3 43 product material](https://leica-camera.com/en-AU/photography/cameras/q/q3-43-black/discover) and [Q3 43 instructions](https://leica-camera.com/sites/default/files/pm-113588-Leica-Q343_Instructions_en.pdf), file-format description.
[^9]: gPhoto2 issue tracker, [Leica Q3 issue #601](https://github.com/gphoto/gphoto2/issues/601), reporting USB ID and partial PTP behavior.
