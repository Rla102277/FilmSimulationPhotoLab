# Q3 43 authorization capture check

Capture: `q3_43_auth_start.pcap`  
SHA-256: `f379d84111ac75688631bdf6b348fe8fbb16405869a4b428a059227d20865d31`

The capture is valid and contains about 32 seconds of iPhone traffic. During that period, the iPhone remained on the home network as `10.10.65.111`.

Observed Leica FOTOS activity includes DNS and TLS connections to `fotos.api.leica-camera.com` and other cloud services. The capture contains no TCP port 15740 connection, no request to `/cam.cgi?mode=accctrl`, and no traffic on the Q3 hotspot subnet `192.168.54.0/24`.

Conclusion: FOTOS recognized the Q3 over Bluetooth, but did not enter the camera's Wi-Fi/PTP remote session. The next capture must continue until Remote Control live view or camera image browsing is visibly active on the iPhone.
