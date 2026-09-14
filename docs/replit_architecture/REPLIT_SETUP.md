# Replit Setup

## Import

Upload/import the whole starter ZIP into a new Replit App. Keep the root file structure intact.

## Agent

Paste `AGENT_BOOTSTRAP_PROMPT.md` first. Then have Agent verify the Leica archive before editing.

## Secrets / environment

Create secrets for:

- APP_SECRET_KEY
- ASSET_SIGNING_SECRET
- DATABASE_URL (when Replit PostgreSQL is enabled)
- ADMIN_EMAIL if authentication is added

No camera LAN addresses, pairing credentials, or transport secrets are used by
the active product.

## Runtime

`.replit` calls `scripts/run.sh`. During the initial skeleton this starts FastAPI. After the React app is built, FastAPI can serve `apps/web/dist` or a deployment can use a build step followed by a single API/static process.

## Persistent data

Treat repository files as source/reference content. Runtime uploads/renders should use a storage abstraction backed by durable storage in production.

## Database

Use PostgreSQL for Look versions, target implementations, source metadata,
recipes, previews, and export records. There are no bridge/job/session tables.
