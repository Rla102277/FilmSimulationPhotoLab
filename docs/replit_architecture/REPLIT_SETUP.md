# Replit Setup

## Import

Upload/import the whole starter ZIP into a new Replit App. Keep the root file structure intact.

## Agent

Paste `AGENT_BOOTSTRAP_PROMPT.md` first. Then have Agent verify the Leica archive before editing.

## Secrets / environment

Create secrets for:

- APP_SECRET_KEY
- BRIDGE_SIGNING_SECRET
- ASSET_SIGNING_SECRET
- DATABASE_URL (when Replit PostgreSQL is enabled)
- ADMIN_EMAIL if authentication is added

Do not put camera LAN IPs or credentials in the cloud secrets. Those belong to the local bridge configuration.

## Runtime

`.replit` calls `scripts/run.sh`. During the initial skeleton this starts FastAPI. After the React app is built, FastAPI can serve `apps/web/dist` or a deployment can use a build step followed by a single API/static process.

## Persistent data

Treat repository files as source/reference content. Runtime uploads/renders should use a storage abstraction backed by durable storage in production.

## Database

Use PostgreSQL early for Look versions, implementations, bridges/jobs, and metadata. Avoid storing multi-megabyte image blobs directly in relational rows; store durable object references/checksums.
