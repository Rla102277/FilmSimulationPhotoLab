LEICA Q3 / Q3 43 — INFINITE ARCH CUSTOM LUT TEST 1

PURPOSE
  Prove that the Q3 accepts arbitrary 17-cube LUT values through the surviving
  authenticated FOTOS session. This is not intended as a finished artistic Look.

THE TEST LOOK
  Name: Infinite Arch Test
  Carrier ID: 27 (Cine)
  Base style: Standard
  Transform: red/blue channel swap with green compressed toward midtone
  Expected appearance: blue subjects/skies turn red; warm red subjects turn blue.

BEFORE STARTING
  1. Back up camera settings.
  2. Remove the earlier Bleach test Look normally so a slot is free.
  3. Confirm no Look with ID 27 / Cine is installed.
  4. Keep these three files together in the same Pyto folder:
       q3_iphone_infinite_arch_test_upload.py
       InfiniteArchTest.CUBE
       InfiniteArchTest.bmp

ONE-RUN PROCEDURE
  1. Connect the iPhone to the Q3 through Leica FOTOS.
  2. Wait until FOTOS fully sees and controls the camera.
  3. Force-quit FOTOS without turning off the camera or leaving Q3 Wi-Fi.
  4. Open q3_iphone_infinite_arch_test_upload.py in Pyto and tap Run.
  5. Type exactly: CUSTOM
  6. Leave Pyto in the foreground until TEST COMPLETE appears.
  7. Do not run it again. Inspect the Leica Looks menu.
  8. If installed, select Infinite Arch Test and photograph something containing
     obvious red and blue areas, saving JPEG+DNG.

GUARDRAILS
  - Both assets are hash-checked before connecting.
  - The CUBE is checked for 4,913 bounded RGB rows and known transform samples.
  - A surviving authenticated FOTOS session and successful live table read are required.
  - The script refuses if ID 27 exists or all eight slots are occupied.
  - Exactly one 0x9035 write is possible. It never retries an ambiguous write.
  - A busy post-write table read may be retried; the write itself never is.

SUCCESS
  WRITE RESULT: 0x2001 OK
  and the camera shows Infinite Arch Test with the obvious color transformation.

If the camera remains busy during post-read, inspect the menu manually. Do not rerun.
