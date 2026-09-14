# Leica Q3 project — recovered artifacts

Recovered on September 9, 2026 from the user-provided files in `/Users/randy/Downloads`.

| Artifact | Size | SHA-256 | Purpose |
|---|---:|---|---|
| `InfiniteArchLeicaCLI_pairing.zip` | 183,928 bytes | `13e067475f009d5b1f0f286a65f5f0df1860cb62b945973b0bdcd5241676c4ad` | Latest Swift pairing/remote/Look test harness |
| `q3_look_capture.pcap` | 17 MB | `9218273f60ab71039eefc9cefffdca7f3d013670eb4d9bdbcdd55ae9db9e0ecb` | Initial Leica FOTOS/Q3 discovery and Look-query capture |
| `q3_look_upload_only.pcap` | 460 KB | `559ff5d0b8e8bca49664d33e4d2bc8a8e0fce5a4bd7baa964f11ac293e4042e9` | Focused successful Bleach Look upload capture |

The original files in Downloads were not modified. Copies are now stored with this task's outputs, and the source ZIP is also unpacked under the task's private `work/leica_q3_recovered/source` directory for continued development.

## Verification

- The focused upload capture contains the plaintext Leica CUBE markers `#Created by: Leica Camera AG`, `TITLE "Bleach"`, and `LUT_3D_SIZE 17`.
- The source ZIP contains the SwiftUI app, `q3test` command-line harness, core LUT conversion code, official Silver control assets, identity/Cine test assets, tests, and protocol research notes.
- Source references confirm the recovered build includes `0x9005`, `0x9033`, `0x9035`, `0x9030`, `0x902D`, `0xD69C`, and `0xD69D` experiments.
- A local build could not be completed in this Codex environment because the full Xcode developer directory is unavailable here. The source itself is preserved unchanged.
