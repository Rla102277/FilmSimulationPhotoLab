# Infinite Arch Q3/Q3 43 complete library

## Delivered library

Eleven unique, red-fast, 17³ Leica Looks:

1. Invitation — soft monochrome
2. Witness — stronger, dramatic monochrome
3. Memory — gentle, faded monochrome
4. Truth — restrained natural color
5. Presence — soft, warm, protected highlights
6. Threshold — firmer, more saturated color
7. Stillness — warm, colorful, soft highlights
8. IA Nostalgic — amber-highlight nostalgic color negative
9. IA Acros — clean fine-gradation monochrome
10. IA HP5 — firmer ISO-400-style monochrome
11. IA Edo 400 — low-saturation, low-contrast, subtly blue-cyan color

Every Look has a correctly labeled 180×90, 1-bit, 2,224-byte BMP icon. The
contact sheet is `Infinite_Arch_Q3_Icon_Preview.png`.

## Why there are two banks

The Q3 43 retains three core Looks and supports six downloaded Looks, producing
nine resident entries. Eleven unique custom recipes cannot fit simultaneously.

- Bank A: Invitation, Witness, Memory, Truth, Presence, Threshold
- Bank B: Stillness, IA Nostalgic, IA Acros, IA HP5, IA Edo 400, Presence

Presence is included in both banks as the continuity Look. Across the banks, all
eleven unique recipes are available.

## Batch installer behavior

Each bank uses six distinct, known Leica downloadable carrier IDs. Before writing,
the installer validates all CUBE and icon hashes, confirms 4,913 bounded red-fast
rows, reads the camera's current table, rejects foreign downloaded Looks, enforces
the nine-entry limit, and determines the next record marker.

After `go`, it uploads one Look, waits for the camera to finish committing, reads
the table back, and verifies the exact ID/name before continuing. A failed or
ambiguous write is never repeated automatically. If the inherited session ends,
the next run safely skips exact bank entries already present and resumes.

The six-Look sequential protocol, payload reconstruction, transaction progression,
commit verification, and final nine-record table were exercised against an offline
PTP/IP camera simulator before packaging.

## Installation

1. Back up camera settings.
2. Remove every downloaded Look in FOTOS, leaving Standard, Monochrome, and Pure.
3. Extract one bank into Pyto without separating its files or `looks` folder.
4. Connect fully in FOTOS, then force-quit FOTOS while staying on Q3 Wi-Fi.
5. Run `upload_all.py` and type `go`.
6. If the script asks for a reconnect, repeat steps 4–5; it resumes safely.
7. Remove all downloaded Looks before switching banks.
