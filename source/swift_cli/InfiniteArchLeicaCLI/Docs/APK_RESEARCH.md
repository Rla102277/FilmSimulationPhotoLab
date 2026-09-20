# Leica FOTOS / Q3 Look research notes

## Static analysis verified from Leica FOTOS 6.1.1

- bundled Looks are AES/GCM encrypted `.CUBE.enc` assets
- decrypted assets are normal 17^3 text CUBE LUTs
- Java wrapper exposes `LooksService.uploadLook(int, String, LeicaLooksType, LeicaLooksBaseStyle, byte[], byte[])`
- native SDK exposes `IPPTLooksService::uploadLook` and `IPPTCameraAPI::leSetLookPropList`

## Live Q3 capture verified September 4, 2026

The clean FOTOS -> Q3 Look upload showed:

- iPhone `192.168.54.10`
- Q3 `192.168.54.1`
- TCP port `15740`
- PTP/IP command/data framing
- Leica Look upload operation `0x9035`
- outbound data phase `2`
- StartData type `9`, Data type `10`, EndData type `12`
- response type `7`, code `0x2001` on success

The captured Bleach payload was 135,223 bytes and began with six property records:

- `D861`, type `0006`: Look ID = 22
- `DC44`, type `FFFF`: PTP UTF-16 name = Bleach
- `DC86`, type `4002`: 2,224-byte 180x90 1-bit BMP
- `D860`, type `4002`: 132,912-byte plaintext CUBE
- `D864`, type `0006`: Look type = 2
- `D866`, type `0006`: base style = 0

Each property record in the upload uses marker `0x20000014`. Byte arrays are encoded as UInt32 count + raw bytes. Strings use the PTP one-byte UTF-16 character count including the terminating null.

The same capture independently verified `0x9033` as the Look property-list query operation.

## v0.3 implementation

`DirectQ3Transport` now mirrors the capture:

- InitCommand request using the FOTOS-observed `OLS` client name
- InitEvent connection
- OpenSession `0x1002`
- Leica vendor session enable `0x9005`, parameter `0xFF55`
- upload via `0x9035`
- 1,000-byte PTP/IP data chunks
- success check for `0x2001`

The remaining physical-camera experiments are acceptance of custom Look IDs, original generated BMP icons, and custom Infinite Arch CUBE contents.
