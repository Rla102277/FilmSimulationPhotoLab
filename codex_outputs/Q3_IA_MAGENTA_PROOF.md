# Q3 IA Magenta Proof

Infinite Arch Test 1 installed successfully but produced no visible color change.
The first test enumerated LUT coordinates blue-fast and also swapped red and blue.
If the Q3 indexes rows red-fast, those operations cancel and the resulting mapping
is identity. That is a concrete explanation consistent with the observed result.

The second diagnostic is independent of row ordering: every one of the 4,913 LUT
entries is `(1.0, 0.0, 1.0)`. If `D860` is parsed and applied, the selected Look's
JPEG must be overwhelmingly magenta regardless of coordinate convention.

The package retains the proven carrier ID 27, type 2, Standard base, valid 180×90
1-bit BMP, live marker allocation, inherited FOTOS session, one-write limit, and
post-write read-only verification.

- CUBE SHA-256: `aafc6111aa7170bd763317d4456b2f8b70d2d6befb5b2a130684c41b5def2cea`
- Payload size with marker `0x20000016`: 135,175 bytes
- Payload SHA-256 with that marker:
  `97060d791ad15883c8cd733e22b2ca61b732ea62b63912dc570173a50bb09aa3`
