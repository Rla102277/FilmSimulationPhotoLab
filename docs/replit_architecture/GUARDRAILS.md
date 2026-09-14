# Guardrails

1. The v1.2 ZIP is immutable.
2. The archive manifest beats old chat summaries.
3. Never update regression fixtures merely because new output differs.
4. Never modify original RAWs.
5. Use explicit camera capability profiles.
6. Keep local transport out of the cloud server.
7. Never expose a bridge listener publicly; bridge initiates outbound authenticated connections.
8. Validate payload hash, Look ID, name, and target before writing to a camera.
9. Re-read/verify after Leica write.
10. Generic RAW software rendering and native Fuji camera rendering are distinct output engines.
11. Do not guess authoritative Fuji recipe values.
12. Large/durable runtime assets need persistent/object storage, not deployed ephemeral filesystem assumptions.
