# Q3 43 Bleach registry-injection result

## Result: rejected and normalized

The Q3 43 accepted/imported the modified settings file, but Bleach did not appear. The post-test export proves the camera rewrote both injected registry properties back to their canonical empty values:

| Property | Injected | Exported afterward |
|---|---|---|
| `DA0F` | Look ID 22 (`0x16`) | Look ID 0 |
| `DA10` | Look ID 22 (`0x16`) | Look ID 0 |

The legitimate `DA01–DA0E` registry entries remained aligned with the installed-Look database. The only Look-adjacent difference from the pre-test export was `D69C` changing its current value from 15 to 21, consistent with the active Look changing during camera/menu use; it is not evidence that Bleach was installed.

## Conclusion

The `.lcs` importer cannot create a Leica Look merely from a registry reference. The camera validates or regenerates the `DAxx` registry from a separate installed-Look object database containing the Look's metadata, icon, and CUBE payload.

This closes the SD-card registry-only bypass. An actual custom Look still requires creation of that underlying object, for which the observed operation is `0x9035` in an authorized FOTOS/PTP-IP session.

## Next route

Because the Q3 network accepts the paired iPhone but not a simultaneous Mac client, the next read-only authorization test must run on the iPhone itself after FOTOS activates the Q3 network and releases its PTP connection.

`q3_iphone_read_probe.py` implements only:

- PTP/IP initialization with the captured zero GUID and `OLS` name
- OpenSession (`0x1002`)
- Leica session enable (`0x9005 [0xFF55]`)
- read-only Look-table query (`0x9033`)

It contains no `0x9035` upload operation. Its decoder has been verified against the captured 833-byte Q3 43 Look table and reproduces all seven known entries correctly.

