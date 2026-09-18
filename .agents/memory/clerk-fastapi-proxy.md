---
name: Clerk FastAPI proxy
description: Production requirements for serving Replit-managed Clerk through a Python/FastAPI backend.
---

The production Clerk proxy must forward to `https://frontend-api.clerk.dev`, not to the hostname decoded from the publishable key. Every forwarded request must include `Clerk-Proxy-Url` based on the public request host and `Clerk-Secret-Key`.

**Why:** Replit-managed production Clerk traffic is intentionally routed through the app’s `/api/__clerk` proxy. The decoded custom Clerk hostname can fail TLS/network access and leaves the published app blank because `clerk.browser.js` returns 500.

**How to apply:** Keep the frontend’s canonical unconditional `VITE_CLERK_PROXY_URL` wiring. When maintaining the FastAPI proxy, preserve the fixed upstream, forwarded public host, secret header, redirect responses, and explicit response lengths.