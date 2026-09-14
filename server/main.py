from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from server.api.leica import router as leica_router

app = FastAPI(title="Infinite Arch Photo Lab", version="0.1.0")
app.include_router(leica_router, prefix="/api")

@app.get("/api/health")
def health():
    return {"ok": True, "service": "infinite-arch-photo-lab"}

WEB_DIST = Path(__file__).resolve().parents[1] / "apps" / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
