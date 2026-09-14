# Leica Q3 43 Wi-Fi authorization capture

Capture: `q3_43_auth_wifi.pcap`  
SHA-256: `5ee5570ace0de41e5dd40b07805ec8fe934c06cb4683ecabe3679844f2adb32e`

## Result

This is the first capture in this investigation containing the complete transition from the paired iPhone to the Q3 43 Wi-Fi network and a successful PTP/IP session.

There is **no HTTP `/cam.cgi?mode=accctrl...` authorization request** in the successful session. The old Q3 capture's HTTP `req_acc` mechanism is therefore not the active authorization path used by this paired Q3 43/FOTOS session.

The observed sequence is:

1. The already-paired iPhone activates/joins the camera network.
2. The camera DHCP server (`192.168.54.1`) leases `192.168.54.10` to the iPhone.
3. FOTOS immediately connects to TCP port `15740`.
4. FOTOS sends PTP/IP `InitCommandRequest` using a zero GUID and UTF-16LE name `OLS`.
5. The camera returns `InitCommandAck`.
6. FOTOS opens PTP session `0x412`, enables the Leica vendor session with `0x9005 [0xFF55]`, and receives success (`0x2001`) for both.
7. FOTOS repeatedly reads the Leica Look table with `0x9033 [0xFFFF, 0xFFFFFFFF]`; every decoded table is 833 bytes.

## Network identities observed

- Camera: `192.168.54.1`, Ethernet/Wi-Fi MAC `50:26:ef:fd:d6:91`
- Paired iPhone: `192.168.54.10`, private Wi-Fi MAC `1e:4e:95:7f:0c:d1`
- FOTOS PTP command connection: phone port `56778` to camera port `15740`
- FOTOS PTP event connection: phone port `56779` to camera port `15740`

Bonjour also exposes rotating Apple remote-pairing identifiers and authentication tags. Those announcements are made by iOS and are not present inside the PTP/IP initialization packet.

## Confirmed current Look table

| Slot | Look | ID | Stable record marker |
|---:|---|---:|---|
| 0 | Standard | 15 | `0x2000000F` |
| 1 | Monochrome | 16 | `0x20000010` |
| 2 | Pure | 26 | `0x20000011` |
| 3 | Silver | 24 | `0x20000012` |
| 4 | Brass | 7 | `0x20000014` |
| 5 | Chrome | 8 | `0x20000015` |
| 6 | Greg Williams | 21 | `0x20000013` |

This confirms the prior conclusion that the `0x200000xx` value is a stable record identity, not the display slot.

## Working authorization model

The evidence now points to two separate gates:

- The paired Bluetooth/FOTOS flow puts the Q3 43 into remote mode and permits the paired phone onto the camera network.
- The PTP/IP server accepts only one active FOTOS command session. A second Mac connection is refused while FOTOS owns it.

The initially proposed Mac/iPhone connection handoff is not applicable to Randy's setup: the Q3 camera network cannot keep FOTOS on the iPhone and the Mac connected simultaneously. The next path is the camera's SD-card `settings.lcs` import mechanism, whose Look registry records are documented in `TRADING_CHAT_LOOKS_BREAKTHROUGH.md`.
