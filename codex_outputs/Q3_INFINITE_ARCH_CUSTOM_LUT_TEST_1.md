# Q3 Infinite Arch custom LUT test 1

This is the first controlled arbitrary-content test after the Q3 43 accepted the
official Bleach payload from our independent Python PTP/IP client.

## Controlled variables

The test retains the proven six-property Leica object:

- `D861`: carrier ID 27 (Cine)
- `DC44`: `Infinite Arch Test`
- `DC86`: valid 180×90, 1-bit, 2,224-byte BMP
- `D860`: plaintext custom 17³ CUBE
- `D864`: 2
- `D866`: 0 (Standard base)

The LUT contains exactly 4,913 bounded RGB rows and mirrors Leica's six-decimal
text formatting. Its deliberate transform swaps red and blue while compressing
green toward the midpoint. This should be immediately visible in a JPEG.

## Safety behavior

The uploader requires the surviving FOTOS session, completes DeviceInfo and
`0x9033` pre-reads, validates capacity and ID availability, constructs the next
record marker from the live table, and makes at most one `0x9035` call. If the
camera returns `0x2019 DeviceBusy` after accepting the write, only the read is
retried; the upload is never repeated.

## Interpretation

- `0x2001 OK` plus the transformed camera JPEG proves arbitrary CUBE content works.
- `0x200F AccessDenied` would imply content-sensitive authorization or validation.
- Another response may indicate payload validation; preserve the complete output.
