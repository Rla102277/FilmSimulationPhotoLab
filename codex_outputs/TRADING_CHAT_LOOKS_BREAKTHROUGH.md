# Latest Leica Looks findings imported from “Trading Q2 For XT5 Package”

## Correction to the Wi-Fi plan

The Q3 43 camera network cannot keep FOTOS on the iPhone and the Mac connected at the same time in Randy's setup. The `q3-network-probe-v4 handoff-read` experiment therefore depends on an invalid physical-network assumption and should not be used as the next step.

## The `.lcs` breakthrough

The Q3 settings backup is plain JSON rather than an encrypted or signed-looking binary container. The anomalous Q3 file imported from the other task contains 587 setting keys and seven values for most settings (current state plus user-profile states).

The anomalous file is preserved as `anomalous_q3_settings.lcs` with SHA-256:

`a9ead7961fff92e10fd22ee35b834ac443137d2f8186f12857ae05d77ad032db`

### Leica Look registry inside `.lcs`

Properties `DA01` through `DA16` contain 32-character hex strings representing 16-byte packed records. Their leading four-byte big-endian value matches known Leica Look IDs.

Examples from the anomalous Q3 file:

| Property pair | Leading ID | Known Look |
|---|---:|---|
| `DA01/DA02` | 15 | Standard |
| `DA07/DA08` | 16 | Monochrome |
| `DA0D/DA0E` | 7 | Brass |
| `DA0F/DA10` | 8 | Chrome |
| `DA13/DA14` | 2 | Classic |
| `DA15/DA16` | 21 | Greg Williams |

The fifth byte commonly contains `0x64` (decimal 100), consistent with Look intensity. In `DA13`, the anomalous profile uses `0x50` (decimal 80) while the other profiles use `0x64`, strengthening that interpretation.

The normal public Q3 43 file contains valid built-in records in the early `DAxx` pairs and zero IDs in later unused records. This establishes that `.lcs` persists the camera's Look-menu/slot references and per-profile Look parameters.

### `D69C` and `D69D`

These are also persisted per profile. Their low values correspond to the low portion of the `0x200000xx` Look record identities observed over PTP. They are therefore much more likely active photo/video Look selectors than remote-authorization flags.

This corrects the earlier interpretation of `D69C/D69D` as possible authorization state.

## What this does and does not solve

Confirmed:

- `.lcs` import is a second, camera-internal path for changing Look references and parameters.
- The file is directly editable JSON.
- Installed Look IDs and intensity-related values are represented in `DA01–DA16`.
- The settings file can persist firmware-known states that are not normally reachable through the camera UI, as demonstrated by the anomalous profile.

Not yet confirmed:

- The `.lcs` contains no `D860` CUBE data, `DC86` icon data, `D861` upload ID, `D864` type, or `D866` base-style upload envelope.
- It therefore cannot yet be claimed that `.lcs` alone installs an arbitrary custom LUT.
- Pointing a registry record at an ID without corresponding LUT data may be ignored or may create a broken reference; this should not be tried first.

## Safest next experiment

Export the current Q3 43 `settings.lcs` from Randy's camera after the recently installed Brass and Chrome Looks. Compare its `DA01–DA16`, `D69C`, and `D69D` records with the captured `0x9033` table.

This will give an exact mapping from:

`DAxx property pair → installed Look ID → display slot → intensity bytes → active selector`

Only after that mapping is verified should one copied settings file be changed: duplicate a reference to an already-installed, known-good Look into an unused registry record. That test changes no LUT bytes and determines whether SD-card import can manipulate the Look registry internally.

