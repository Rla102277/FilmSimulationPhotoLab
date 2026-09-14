# Q3 43 deeper `.lcs` Leica Look test

## Objective

Test whether the camera's privileged settings importer can create or resurrect an official Leica Look entry without FOTOS and without sending PTP operation `0x9035`.

The camera currently has seven registry entries:

Standard (15), Monochrome (16), Pure (26), Silver (24), Brass (7), Chrome (8), and Greg Williams (21).

The next registry pair, `DA0F/DA10`, is empty. The test changes only that pair from ID 0 to official Leica Bleach ID 22 (`0x16`).

## Files and hashes

- Untouched original: `rla1022_original.lcs`
  - SHA-256: `7351ec05b6704aba45bfa6df64b6d4bdf3b63deb3d22ed9b8c5a9dc749da2b22`
- Test: `q3_43_test_resurrect_bleach.lcs`
  - SHA-256: `1cc0c783b77aed83acf35f20ba9298e8d8f49ac5ed82e00e0ebc53db2ff6b514`

## Exact semantic change

Only `DA0F` and `DA10` change. Across all seven profile values:

`00000000641111100000000000000000`

becomes:

`00000016641111100000000000000000`

No active-Look selector, existing Look, user setting, CUBE, icon, firmware region, network state, or unknown ID is modified.

## Interpretation

- **Bleach appears with correct name/icon and renders:** major result. The camera can resolve or retain Look content from an `.lcs` registry reference, bypassing the normal FOTOS upload path for at least known Look IDs.
- **Bleach appears but has a blank/wrong name or icon:** registry reference accepted, payload missing. Do not select it; export the resulting settings file and restore the original.
- **No new Look appears:** the importer normalized or ignored the record. Export the resulting settings file so normalization can be measured.
- **Import rejected or camera behaves abnormally:** stop and restore the untouched original. Do not repeat the test.

## Evidence to collect

1. Photograph the Leica Looks menu immediately after import.
2. If Bleach appears with its correct name and icon, select it and make one `DNG + JPG` test photograph.
3. Export profiles again before restoring the original; preserve that file as `after-bleach-test.lcs`.
4. Restore the untouched original settings file through the normal Import Profiles menu.

