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

## leica_payloads
Compiled Leica artifact metadata/checksum/validation.

## fuji_recipes
Camera-specific Fuji recipe settings and provenance.

## export_artifacts
Generated payload, pack, LUT, XMP, or recipe output with source references,
compiler version, checksum, and validation report.

There are no active Bridge, CameraConnection, CameraHeartbeat, CameraSession, or
hardware-job models. Camera transport is not part of the product.
