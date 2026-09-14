# Architecture

## Topology

```text
Browser
   |
   | HTTPS
   v
Replit: Infinite Arch Photo Lab
   |-- React UI
   |-- FastAPI API
   |-- PostgreSQL
   |-- Look/version registry
   |-- color engine
   |-- Leica/Fuji compilers
   |-- bridge job queue
   |
   | outbound/persistent authenticated bridge channel
   v
IA Camera Bridge on local Mac
   |-- Leica PTP/IP
   |-- Fuji USB/network protocol
   v
Camera
```

## Why the bridge exists

A cloud server cannot route to the camera's private Wi-Fi address. Browser JavaScript is also the wrong layer for raw camera TCP/USB transport. The bridge solves only the hardware boundary; Replit remains the product brain.

## Look model

```text
LookFamily
  -> LookVersion
      -> CameraImplementation (Leica Q3 43)
      -> CameraImplementation (Fuji X-E5)
      -> CameraImplementation (Fuji GFX50R)
      -> CameraImplementation (Software)
```

## Color source types

- CUBE
- DCP
- LRTemplate
- XMP
- reference image / calibration pair
- Leica payload
- Fuji recipe

All imported source assets should be immutable by checksum.
