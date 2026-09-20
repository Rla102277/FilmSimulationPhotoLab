# Infinite Arch Leica MVP

This is the persistent Xcode package for the Leica Q3 USB/PTP uploader.

## What is already proven
- Q3 enumerates over USB as Leica VID 0x1A98 / PID 0x2376.
- macOS ImageCaptureCore opens a native PTP session.
- Q3 advertises Leica vendor operations 0x9005 and 0x9035.
- Leica Look list read via 0x9033 works.
- Current Q3 list seen during development: Standard ID 15, Monochrome ID 16, Pure ID 26, Brass ID 7, Classic ID 2, Bleach ID 22.
- FOTOS upload payload is a 6-property Leica object property list.

## MVP test
1. Quit Image Capture. Q3 USB mode = PTP.
2. Build and run the `InfiniteArchLeicaLookBuilder` executable scheme.
3. Click `Test USB PTP`.
4. Click `Read Q3 Look List`.
5. Click `Step 1 — Install Official Silver` once.
   - This uses Leica Silver ID 24, the official decrypted Silver CUBE, and the official 2224-byte icon from the supplied Leica FOTOS APK.
6. If Step 1 returns 0x2001, verify Silver appears on the Q3.
7. Only then click `Step 2 — Install Identity LUT Test` once.
   - This uses valid downloadable Leica ID 27 (Cine) but a neutral 17^3 LUT.
   - If this returns 0x2001, arbitrary LUT content is accepted and the MVP is proven.

Do not repeatedly click a failed write. Read the status line first.
