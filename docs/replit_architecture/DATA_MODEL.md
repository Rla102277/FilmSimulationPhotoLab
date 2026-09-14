# Data Model

## look_families
Canonical photographic concepts such as IA Presence.

Fields: id, slug, name, description, status, created_at.

## look_versions
Versioned master intent. Fields: family_id, version, color_graph_json, notes, status.

## camera_implementations
A LookVersion translated for one camera/software target. Fields: look_version_id, camera_profile_id, implementation_type, version, settings_json, artifact_asset_id, verification_status.

## source_assets
Immutable imported assets. Fields: sha256, filename, media_type, asset_type, size, provenance, storage_key, imported_at.

## camera_profiles
Capabilities per exact model/firmware family.

## image_assets
Original photo metadata and immutable storage reference.

## renders
Derived outputs with engine, Look implementation, parameters, checksum.

## bridges
Paired local bridge identity, last_seen, capabilities, version.

## bridge_jobs
Queued hardware tasks with status state machine.

Suggested statuses: QUEUED, BRIDGE_RECEIVED, CAMERA_CONNECTED, VALIDATING, RUNNING, VERIFYING, SUCCESS, FAILED, CANCELLED.

## bridge_logs
Structured logs tied to job and bridge.

## leica_payloads
Compiled Leica artifact metadata/checksum/validation.

## fuji_recipes
Camera-specific Fuji recipe settings and provenance.
