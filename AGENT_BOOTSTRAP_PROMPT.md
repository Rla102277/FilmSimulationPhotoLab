# Infinite Arch Photo Lab agent bootstrap

Preserve the immutable Leica v1.2 archive and its recorded SHA-256.

Build a normal React/FastAPI web application for:

- Look creation and versioning
- Leica six-property parsing, editing, compilation, verification, and downloads
- software CUBE preview
- payload inspection and CUBE extraction
- deterministic Look pack export
- Fuji capability-aware recipe translation and export
- DCP/LRTemplate/XMP source work

Do not add camera discovery, direct camera networking, bridge pairing, heartbeat,
camera jobs, camera sessions, reads, writes, installation, or Fuji transport.
Transport findings are historical research, not product architecture.

Every Leica build must use the authoritative v1.2 representation and complete a
compile → parse → compare loop before download.