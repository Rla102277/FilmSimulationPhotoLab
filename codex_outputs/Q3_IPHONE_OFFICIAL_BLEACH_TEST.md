# Leica Q3/Q3 43 official Bleach write test

## Confirmed camera result — 2026-09-09

- `0x9035` returned `0x2001 OK`.
- Bleach appeared in the Leica Looks menu on the Q3 43.
- The camera successfully captured a photograph with Bleach applied.
- The post-write table read did not return a recognized response, consistent with
  the camera changing or invalidating the inherited session after committing the
  new Look. This does not negate the independently verified installed Look.

**Conclusion:** an independent PTP/IP client can inherit the authenticated Leica
FOTOS session and install a Leica Look. The network authorization barrier is solved.

This package performs one controlled Leica Look upload through the independently
inherited, already-authenticated FOTOS PTP/IP session.

## Payload validation

- Official `Bleach.CUBE`: 132,912 bytes; SHA-256
  `c2a58164e543704189ef84d8c9b28f4deaac226bde94a3134f69a72a583f50f6`
- Official `Bleach.bmp`: 2,224 bytes; SHA-256
  `1d8b2d6c9e66506cf02c81f7a28f77fa5a2cf9b108128a9a279e963bea4e0288`
- Six-field upload payload: 135,223 bytes
- Rebuilding the payload with the captured marker `0x20000014` produces an exact,
  byte-for-byte match to the payload captured from Leica FOTOS; SHA-256
  `de587aac4e5b471cb9bd30cc0ec4e41ab403c79555d0bad01f7ee5ff442f6533`.
- The test payload uses the next marker calculated from the camera's live table.
  For the captured seven-Look table, that is `0x20000016`.

## Guardrails

- The script requires `OpenSession` to return `0x201E SessionAlreadyOpen`.
- A normal newly opened session is rejected before any write.
- Standard DeviceInfo and Leica `0x9033` must both succeed first.
- The upload is rejected if Bleach ID 22 already exists or eight Looks are present.
- Asset hashes and embedded CUBE metadata must match Leica's originals.
- There is at most one `0x9035` call. Network failure after write start is treated
  as ambiguous and is never retried.
- A post-write `0x9033` read verifies the result independently.

## Run procedure

1. Put all three extracted ZIP files together in the same Pyto folder.
2. Back up camera settings and confirm Bleach is absent with a free Look slot.
3. Connect the Q3 in Leica FOTOS and wait for full camera control.
4. Force-quit FOTOS, keeping the iPhone joined to the Q3 Wi-Fi.
5. Run `q3_iphone_official_bleach_upload.py` in Pyto.
6. Type `UPLOAD` when prompted and let the single run finish.
7. Save the complete output and inspect the camera's Leica Looks menu.

`0x2001 OK` followed by `Bleach installed=True` proves that an independent client
can write through the surviving authenticated FOTOS session. `0x200F AccessDenied`
means a separate per-operation authorization gate remains.
