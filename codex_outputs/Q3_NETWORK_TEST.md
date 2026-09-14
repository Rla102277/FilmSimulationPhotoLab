# Leica Q3 Wi-Fi authorization test

This is the next safe test. It does **not** install a Look or change camera settings.

## What the packet captures proved

The accepted Leica FOTOS upload did not use a hidden PTP authorization opcode. Its sequence was:

1. FOTOS requested camera access over HTTP.
2. The Q3 answered `ok_under_research,...,remote,open`.
3. FOTOS repeated the request and the Q3 answered `ok,...,remote,open`.
4. FOTOS opened PTP/IP on port 15740 with client name `OLS` and a zero GUID.
5. FOTOS opened a PTP session, sent Leica operation `0x9005 [0xFF55]`, read the Look table with `0x9033`, and uploaded with `0x9035`.
6. The Q3 accepted the upload with response `0x2001`.

The earlier USB attempts failed because they never passed through the Q3's network/FOTOS access gate.

## Camera setup

1. Turn on the Q3 and enable its Leica FOTOS/Wi-Fi connection mode.
2. Connect the Mac directly to the Q3's Wi-Fi network.
3. Fully quit Leica FOTOS on the iPhone so it cannot compete for the camera connection.
4. In Terminal, run the access-only check:

   `/Users/randy/Documents/Codex/2026-09-09/go/outputs/q3-network-probe access`

5. If it reports `access=OPEN`, run the PTP/IP read check. Version 2 of the probe does not issue another HTTP request here:

   `/Users/randy/Documents/Codex/2026-09-09/go/outputs/q3-network-probe read`

## How to interpret the result

- `access=OPEN`: the Mac inherited or can replay the paired FOTOS identity. The read command should then prove the full authorized PTP/IP route.
- A response ending in `encrypted`: the camera recognizes that access is paired/encrypted but is binding it to something beyond the UUID, likely the paired phone or Wi-Fi client identity. The tool stops safely and does not repeat the request.
- Connection refused on port 80 or 15740: the Q3 is not currently exposing the FOTOS network service; re-enter its Wi-Fi/FOTOS connection mode.
- `0x9033=OK (750 bytes)` is the target result. It means the Mac reached the same authorized Leica Look service used in the successful capture.

## Q3 43 live result — September 9, 2026

The Q3 43 returned these states during controlled tests:

```text
ok_under_research_no_msg,...,remote,encrypted
err_others_requesting,...,remote,encrypted
<camrply><result>err_critical</result></camrply>
```

This confirms the HTTP endpoint is a single-request state machine. A new request was held as the active requester; trying a different UUID while it was pending produced `err_others_requesting`, and continuing produced `err_critical`. Exit the camera's FOTOS/Wi-Fi connection mode before any further access test. Do not stack new UUID attempts.

The successful packet capture came from Q3 `6246453`, while this test camera identifies itself as Q3 43 `5976155`. The captured UUID is therefore not sufficient to transfer authorization to another camera. The missing state is consistent with a camera-specific encrypted FOTOS pairing.

Do not run an upload until the read-only test reaches that target.
