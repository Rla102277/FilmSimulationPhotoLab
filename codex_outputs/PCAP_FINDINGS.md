# Leica Q3 Leica Looks capture findings

## Confirmed successful upload

- Phone: `192.168.54.10`
- Q3: `192.168.54.1`
- PTP/IP service: TCP port `15740`
- Upload operation: `0x9035`
- Upload transaction: `0x0000001D`
- Payload: `135,223` bytes
- Q3 response: `0x2001` (success)

The payload contains six Leica property records:

| Property | Meaning | Captured value |
|---|---|---|
| `D861` | Look ID | `22` |
| `DC44` | Name | `Bleach` |
| `DC86` | Icon | `2,224` bytes |
| `D860` | CUBE LUT | `132,912` bytes |
| `D864` | Look type | `2` |
| `D866` | Base style | `0` (Standard) |

The initially observed `0x20000014` record marker is not a global constant. The Q3 43 capture proved markers are stable per-Look record and allocated sequentially: existing records used `0x2000000F` through `0x20000013`, Brass used `0x20000014`, and Chrome used `0x20000015`. Future custom uploads must derive the next safe marker from the current `0x9033` table.

## Authorization sequence

Before opening PTP/IP, FOTOS sent this access request to the Q3 HTTP service:

```http
GET /cam.cgi?mode=accctrl&type=req_acc&value=89440BC7-DFC6-4929-A68D-8BD1C3C47BDF&value2=iPhone HTTP/1.1
Host: 192.168.54.1
Cache-Control: no-cache
Accept: */*
User-Agent: Leica%20FOTOS/1022 CFNetwork/3896.100.1.2.1 Darwin/27.0.0
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate
Connection: keep-alive
```

The two captured responses were:

```text
ok_under_research,Leica Q3-6246453,remote,open
ok,Leica Q3-6246453,remote,open
```

The PTP/IP initialization immediately afterward used:

- 16-byte zero GUID
- UTF-16LE client name `OLS`
- protocol version `1`
- `0x1002` OpenSession
- `0x9005 [0xFF55]` Leica session enable

There was no `0x9030` or `0x902D` authorization call before the successful upload. This makes the network access-control exchange the key difference from the rejected USB attempts.

## Safety conclusion

The next test should prove the authorized network path with read-only operation `0x9033`. Upload operation `0x9035` remains deliberately excluded from the standalone probe until that read succeeds.
