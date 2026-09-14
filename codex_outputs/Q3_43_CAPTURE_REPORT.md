# Q3 43 Leica FOTOS capture report

Capture: `q3_43_fresh_session.pcap`  
SHA-256: `b09498b64305944849d828081301f453ea33a7110c87fd91f6ea976ead918b08`

## Confirmed behavior

The capture began after the FOTOS PTP/IP session was already established. Its first visible camera transaction is `41`; therefore it does not contain the HTTP authorization request, the PTP/IP InitCommand request, OpenSession, or Leica `0x9005` session-enable operation.

It does contain two complete, successful Leica Look uploads:

| Transaction | Operation | Look | ID | Record marker | Payload | Result |
|---:|---|---|---:|---|---:|---|
| 62 | `0x9035` | Brass | 7 | `0x20000014` | 154,827 bytes | `0x2001` |
| 75 | `0x9035` | Chrome | 8 | `0x20000015` | 140,092 bytes | `0x2001` |

Both uploads contain six properties: Look ID (`D861`), name (`DC44`), 2,224-byte icon (`DC86`), plaintext CUBE LUT (`D860`), type (`D864`), and base style (`D866`).

## Look-table transition

Before Brass, `0x9033` returned five Looks:

1. Standard — ID 15 — marker `0x2000000F`
2. Monochrome — ID 16 — marker `0x20000010`
3. Pure — ID 26 — marker `0x20000011`
4. Silver — ID 24 — marker `0x20000012`
5. Greg Williams — ID 21 — marker `0x20000013`

After Brass, `0x9033` returned six Looks. Brass had marker `0x20000014`, while Greg Williams moved from slot 4 to slot 5 but retained marker `0x20000013`.

This proves the marker is a stable Look-record identity, not a slot number. Chrome then used the next marker, `0x20000015`. A custom uploader must read the current table and allocate a safe next record marker instead of always using `0x20000014`.

## Remaining authorization capture

A second capture must start while FOTOS is fully disconnected and the camera is outside its active FOTOS session. The current capture began mid-session, so it cannot reveal the Q3 43's current HTTP client UUID or the event that opens TCP port 15740.
