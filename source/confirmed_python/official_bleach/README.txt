LEICA Q3 / Q3 43 — CONTROLLED OFFICIAL BLEACH WRITE TEST

CONTENTS
  q3_iphone_official_bleach_upload.py
  Bleach.CUBE  (official, unmodified Leica asset)
  Bleach.bmp   (official, unmodified Leica icon)

Keep all three files together in the same Pyto folder.

BEFORE STARTING
  1. Back up the camera settings to the SD card.
  2. Confirm Bleach is NOT already shown in the Leica Looks menu.
  3. Make sure there is an open downloadable-Look slot.
  4. Disable iPhone Auto-Lock temporarily.

ONE-RUN PROCEDURE
  1. Connect the iPhone to the Q3 through Leica FOTOS.
  2. Wait until FOTOS fully controls/sees the camera.
  3. Force-quit FOTOS without turning off the camera or leaving Q3 Wi-Fi.
  4. Open q3_iphone_official_bleach_upload.py in Pyto and tap Run.
  5. Type exactly: UPLOAD
  6. Leave Pyto in the foreground until TEST COMPLETE appears.
  7. Save or screenshot the complete output.

WHAT THE SCRIPT DOES
  - Cryptographically verifies both official Leica assets.
  - Requires the surviving authenticated FOTOS session.
  - Reads DeviceInfo and the complete Look table before writing.
  - Refuses to write if Bleach ID 22 exists or all eight slots are occupied.
  - Creates the next valid Leica record marker from the live table.
  - Sends exactly one 0x9035 upload attempt; an ambiguous write is never retried.
  - Reads the Look table again and prints a final installed=True/False verdict.

INTERPRETING THE RESULT
  WRITE RESULT: 0x2001 OK plus Bleach installed=True
    The authenticated-session write succeeded.

  WRITE RESULT: 0x200F AccessDenied
    Session inheritance permits reads, but write authorization has another gate.

  AMBIGUOUS WRITE STATE
    Do not run the script again. Inspect the Leica Looks menu first and preserve
    the entire Pyto output.

After a successful test, confirm Bleach appears in the camera menu and shoot one
JPEG+DNG test frame. The installed official Look can later be removed normally.
