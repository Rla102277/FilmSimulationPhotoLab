from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from server.api.leica import router as leica_router
from server.api.leica_lab import router as leica_lab_router
from server.api.lab import router as lab_router
from server.api.studio import router as studio_router
from server.api.workspaces import router as workspaces_router
from server.api.ai_review import router as ai_review_router
from server.auth import proxy_router
from server.pages import install_guide_page, look_building_page

app = FastAPI(title="Film Look Studio", version="1.0.0")
app.include_router(proxy_router)
app.include_router(leica_router, prefix="/api")
app.include_router(leica_lab_router, prefix="/api")
app.include_router(lab_router, prefix="/api")
app.include_router(studio_router, prefix="/api")
app.include_router(workspaces_router, prefix="/api")
app.include_router(ai_review_router, prefix="/api")

@app.get("/api/health")
def health():
    return {"ok": True, "service": "film-look-studio"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/look-building", response_class=HTMLResponse)
def look_building():
    return look_building_page()


@app.get("/install-guide", response_class=HTMLResponse)
def install_guide():
    return install_guide_page()


WEB_DIST = Path(__file__).resolve().parents[1] / "apps" / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
else:
    @app.get("/", response_class=HTMLResponse)
    def status_page():
        return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Film Look Studio</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: #11110f; color: #f2efe8; }
    main { width: min(900px, calc(100% - 32px)); margin: 0 auto; padding: 72px 0; }
    .eyebrow { color: #c7a76c; letter-spacing: .16em; text-transform: uppercase; font-size: .75rem; }
    h1 { margin: 12px 0 8px; font: 500 clamp(2.4rem, 7vw, 5rem)/.95 Georgia, serif; }
    .lede { max-width: 650px; color: #b8b3aa; font-size: 1.08rem; line-height: 1.65; }
    .status { display: inline-flex; align-items: center; gap: 8px; margin: 20px 0 36px; padding: 8px 12px; border: 1px solid #34312c; border-radius: 999px; color: #d8d3c9; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: #d0ad66; box-shadow: 0 0 12px #d0ad66; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
    .card { padding: 22px; border: 1px solid #2f2d29; border-radius: 14px; background: #191816; }
    .card h2 { margin: 0 0 8px; font-size: 1rem; font-weight: 600; }
    .card p { margin: 0; color: #99958d; line-height: 1.5; font-size: .92rem; }
    a { color: #d8ba7e; text-decoration: none; }
    a:hover { text-decoration: underline; }
    code { color: #d9d4ca; }
    #looks { margin-top: 28px; color: #aaa59b; font-size: .9rem; }
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">Server scaffolding</div>
    <h1>Film Look<br>Studio</h1>
    <p class="lede">A web-based Look development and compilation system. Create, inspect, preview, validate, and download target-specific color files without connecting to a camera.</p>
    <div class="status"><span class="dot"></span><span id="health">Checking service…</span></div>
    <section class="grid">
      <article class="card">
        <h2>API documentation</h2>
        <p>Explore the FastAPI routes through the <a href="/docs">interactive API docs</a>.</p>
      </article>
      <article class="card">
        <h2>Archive integrity</h2>
        <p>Verify the immutable Leica v1.2 release at <a href="/api/leica/v1.2/verify"><code>/api/leica/v1.2/verify</code></a>.</p>
      </article>
      <article class="card">
        <h2>Authoritative Looks</h2>
        <p>Read the nine-Look manifest at <a href="/api/leica/v1.2/looks"><code>/api/leica/v1.2/looks</code></a>.</p>
      </article>
      <article class="card">
        <h2>How a Look is built</h2>
        <p>Read the documented workflow from visual intent to verified Leica payload on the <a href="/look-building">Look building guide</a>.</p>
      </article>
    </section>
    <div id="looks">Loading authoritative manifest…</div>
  </main>
  <script>
    Promise.all([
      fetch("/api/health").then(r => r.json()),
      fetch("/api/leica/v1.2/looks").then(r => r.json())
    ]).then(([health, looks]) => {
      document.querySelector("#health").textContent = health.ok ? "Service online" : "Service unavailable";
      document.querySelector("#looks").textContent = `${looks.length} authoritative Leica Looks loaded · v1.2 archive verified on access`;
    }).catch(() => {
      document.querySelector("#health").textContent = "Service check failed";
      document.querySelector("#looks").textContent = "The API did not return the authoritative manifest.";
    });
  </script>
</body>
</html>
"""
