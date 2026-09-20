# Infinite Arch Leica CLI

This is the persistent command-line harness for Leica Q3 USB/PTP work.

## One-time setup
1. Unzip this folder somewhere permanent.
2. Q3: USB mode = PTP.
3. Quit Image Capture.
4. In Terminal:
   cd /path/to/InfiniteArchLeicaCLI

## Commands

Read-only:
```bash
swift run q3test probe
swift run q3test list
swift run q3test all-read
```

Write tests:
```bash
swift run q3test silver
swift run q3test identity
```

`silver` uses Leica's official Silver CUBE/icon and known Leica Look ID 24.
`identity` uses a neutral 17^3 LUT under known Leica Cine ID 27.

Current proven state:
- USB PTP works.
- Q3 advertises 0x9005 and 0x9035.
- Leica Look list read via 0x9033 works.
- 0x9035 write over the ordinary USB PTP session currently returns 0x200F Access Denied.

The next reverse-engineering target is the session authorization/privilege step, not the LUT payload.


## Authorization breakthrough
Static disassembly of Leica FOTOS `libleica.so` shows:

`IPPTControlServiceImpl::setRemoteStatus(RemoteFunction, RemoteStatus)`

builds Leica vendor PTP operation **0x9030**. The SDK only accepts RemoteFunction `0`, and RemoteStatus `0` or `1`; the conversion maps status `1 -> 1` and `0 -> 0`.

New commands:
```bash
swift run q3test remote-on
swift run q3test remote-off
```

Run `remote-on` first by itself. It does not upload a Look. If it returns 0x2001, the next test is a Silver upload while that SDK remote state is enabled. `remote-off` restores status 0.


## One-session authorization write test
`remote-on` returned 0x2001 on the Q3. Because authorization may be session-scoped, do not test the write in a separate process. Use:

```bash
swift run q3test authorized-silver
```

This performs, on the same live ImageCaptureCore/PTP session:

1. `0x9005 [0xFF55]`
2. `0x9030 [0,1]`
3. `0x9035` with the official Leica Silver ID 24 / official CUBE / official icon

Run it once and inspect the final response.


## Stateful 0x9030 behavior
The Q3 returned 0x2001 to `remote-on` in one session, then 0x201D to the same `0x9030 [0,1]` inside the combined authorization/write session. The new `authorized-silver` command treats 0x201D as a possible "already enabled / stateful" response and proceeds once to the official Silver upload, reporting both response codes.


## Next read-only authorization probe
The official Silver upload still returns `0x200F Access Denied` even after `0x9030 [0,1]` succeeds. The native Leica SDK also registers control-state properties `0xD69C` and `0xD69D`.

Run:

```bash
swift run q3test state-probe
```

This does not upload a Look. It reads those properties with standard PTP GetDevicePropValue (`0x1015`) before and after the remote-enable sequence and prints the raw bytes.


## Property descriptor probe
The camera returns `0F 00 00 20` for both D69C and D69D before and after `0x9030 [0,1]`, i.e. little-endian `0x2000000F`.

Next read-only command:

```bash
swift run q3test prop-desc
```

This sends standard PTP `GetDevicePropDesc` (`0x1014`) for D69C and D69D to reveal datatype/access/default/current/form metadata.


## Native pairing operation breakthrough

Static disassembly of the x86_64 Leica FOTOS `libleica.so` resolves the
previously opaque pairing path exactly:

- `IPPTControlServiceImpl::enablePairing()` calls
  `sendControlConnectionCommand(command=2, service=1)`.
- `IPPTControlServiceImpl::disablePairing()` calls
  `sendControlConnectionCommand(command=3, service=1)`.
- `sendControlConnectionCommand(...)` constructs Leica vendor PTP operation
  **0x902D** and places `[command, service]` in its parameter vector.

Therefore:
- enable Bluetooth pairing = `0x902D [2,1]`
- disable Bluetooth pairing = `0x902D [3,1]`
- enable Wi-Fi = `0x902D [0,0]`
- disable Wi-Fi = `0x902D [1,0]`

The next concrete test is:

```bash
swift run q3test pairing-silver
```

It uses one uninterrupted PTP session and performs:

1. `0x9005 [0xFF55]`
2. `0x902D [2,1]`
3. `0x9030 [0,1]`
4. `0x9035` with official Leica Silver
5. `0x902D [3,1]` cleanup

The command reports every response code.
