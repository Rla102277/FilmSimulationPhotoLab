---
name: Clerk FastAPI proxy
description: Production requirements for serving Replit-managed Clerk through a Python/FastAPI backend.
---

The production Clerk proxy must forward to `https://frontend-api.clerk.dev`, not to the hostname decoded from the publishable key. Every forwarded request must include `Clerk-Proxy-Url` based on the public request host and `Clerk-Secret-Key`. When the proxy reads and relays the response body rather than streaming raw bytes, request identity encoding upstream instead of forwarding the browser's `Accept-Encoding`.

**Why:** Replit-managed production Clerk traffic is intentionally routed through the app’s `/api/__clerk` proxy. The decoded custom Clerk hostname can fail TLS/network access. Forwarding browser compression while dropping `Content-Encoding` can also make valid 200 responses unparsable, leaving Clerk permanently unloaded.

**How to apply:** Keep the frontend’s canonical unconditional `VITE_CLERK_PROXY_URL` wiring. Preserve the fixed upstream, forwarded public host, secret header, redirects, and response lengths. For buffered FastAPI/httpx relays, force `Accept-Encoding: identity`.