LEICA Q3 / Q3 43 — IA MAGENTA PROOF

WHY THIS TEST EXISTS
  Infinite Arch Test 1 installed without errors but appeared neutral. Its file
  order and red/blue swap can mathematically cancel if the Q3 indexes CUBE rows
  in the opposite order. This test removes that ambiguity: all 4,913 LUT entries
  are magenta, so row order cannot change the result.

BEFORE STARTING
  1. Remove Infinite Arch Test from FOTOS so one Look slot is free.
  2. Confirm no ID 27 / Cine carrier Look remains installed.
  3. Back up camera settings.
  4. Keep these files together in the same Pyto folder:
       q3_iphone_ia_magenta_proof_upload.py
       IAMagentaProof.CUBE
       IAMagentaProof.bmp

ONE-RUN PROCEDURE
  1. Connect completely to the Q3 through Leica FOTOS.
  2. Force-quit FOTOS while remaining on the Q3 Wi-Fi.
  3. Run q3_iphone_ia_magenta_proof_upload.py in Pyto.
  4. Type exactly: MAGENTA
  5. Wait for TEST COMPLETE. Never run this upload twice.
  6. Select IA Magenta Proof in the camera's Leica Looks menu.
  7. Capture a JPEG+DNG pair. Judge the JPEG; DNG data is expected to remain raw.

EXPECTED RESULT
  If the Q3 executes our D860 LUT, the JPEG should be overwhelmingly magenta.
  If the JPEG remains normal, the Q3 stored the custom object/name but did not use
  the supplied LUT data. Preserve the complete Pyto output and both image files.

The script validates all 4,913 rows, performs live pre-reads, allows exactly one
0x9035 write, and never retries a write after transmission begins.
