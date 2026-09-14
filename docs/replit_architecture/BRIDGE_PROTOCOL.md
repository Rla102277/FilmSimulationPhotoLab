# IA Camera Bridge Protocol

## Principle

The bridge creates the outbound connection. The server never attempts to connect directly into the user's LAN/camera network.

## Initial message types

- BRIDGE_HELLO
- BRIDGE_HEARTBEAT
- CAMERA_STATUS
- CAMERA_INFO
- LEICA_READ_LOOKS
- LEICA_INSTALL_LOOK
- LEICA_VERIFY_LOOK
- LEICA_INSTALL_PACK
- FUJI_STATUS
- FUJI_PROCESS_RAW
- JOB_LOG
- JOB_COMPLETE
- JOB_FAILED

## Example job

```json
{
  "id": "uuid",
  "type": "LEICA_INSTALL_LOOK",
  "payload": {
    "implementation_id": "uuid",
    "look_id": 1004,
    "artifact_sha256": "...",
    "target_camera": "LEICA_Q3_43"
  }
}
```

## Validation before camera writes

- expected camera/model
- Look ID
- Look name
- artifact checksum
- payload parser validation
- current camera state/readability

## Validation after Leica write

Re-read the camera Look table and compare expected identity/state. Never report success from write response alone when verification is available.
