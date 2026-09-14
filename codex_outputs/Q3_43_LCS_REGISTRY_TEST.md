# Q3 43 Leica Look registry test

## Verified source backup

- Camera identifier: `LEICA Q3 43`
- Settings keys: 587
- Original file: `rla1022_original.lcs`
- Original SHA-256: `7351ec05b6704aba45bfa6df64b6d4bdf3b63deb3d22ed9b8c5a9dc749da2b22`

The settings export and captured `0x9033` Look table agree exactly:

| Registry pair | Look ID | Look | Captured display slot |
|---|---:|---|---:|
| `DA01/DA02` | 15 | Standard | 0 |
| `DA03/DA04` | 16 | Monochrome | 1 |
| `DA05/DA06` | 26 | Pure | 2 |
| `DA07/DA08` | 24 | Silver | 3 |
| `DA09/DA0A` | 7 | Brass | 4 |
| `DA0B/DA0C` | 8 | Chrome | 5 |
| `DA0D/DA0E` | 21 | Greg Williams | 6 |
| `DA0F/DA10` onward | 0 | Empty | — |

This proves the `DAxx` property pairs encode the ordered Leica Look registry. The records are 16 bytes represented by 32 hexadecimal characters. The first four bytes encode the Look ID. Byte five is `0x64` (decimal 100) in the current records and is consistent with Look intensity.

## Test file

`q3_43_test_swap_chrome_greg.lcs` changes only four properties:

- `DA0B` and `DA0C`: ID 8 (Chrome) → ID 21 (Greg Williams)
- `DA0D` and `DA0E`: ID 21 (Greg Williams) → ID 8 (Chrome)

Every other JSON setting remains semantically identical to the camera's original export. The test uses only two already-installed, known-good Look IDs. It does not add unknown IDs or alter CUBE/icon data.

Test SHA-256: `a139794f5aa677a974b429145fe0178ed3d015062fcd1b125349d88637cf393e`

## Expected outcomes

1. **Chrome and Greg Williams swap menu positions:** the `.lcs` importer controls the Look registry. This is the desired proof.
2. **Import succeeds but order remains unchanged:** the importer ignores or regenerates these registry fields.
3. **Import is rejected:** the file has an integrity/validation rule not visible in the JSON. Stop; do not retry repeatedly.

After a successful import, photograph the Leica Looks menu and immediately export a new settings backup before restoring the original. That post-import file will reveal whether the camera preserved, normalized, or discarded the four edits.

