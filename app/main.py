"""PiNotes Lite — FastAPI backend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="PiNotes Lite")

# ─── Paths ───────────────────────────────────────────────────────────────────
# Works identically in dev (project root) and in the Docker image.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR   = PROJECT_ROOT / "frontend" / "dist"
INDEX_HTML   = STATIC_DIR / "index.html"

# ─── API routes ──────────────────────────────────────────────────────────────


@app.get("/api/healthz")
async def healthz() -> dict:
    """Liveness / health check."""
    return {"status": "ok"}


# ─── Static assets (CSS / JS / images produced by Vite) ─────────────────────
# Mounted at /assets — matches Vite's default output layout.
if (STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

# ─── SPA catch-all (registered LAST) ────────────────────────────────────────
# Any path that didn't match an API route or /assets/* file falls through here.
# Return index.html so the React router can handle client-side routing.


@app.get("/{full_path:path}")
async def spa_fallback() -> FileResponse:
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return JSONResponse(
        {"error": "Frontend not built. Run `cd frontend && npm run build`"},
        status_code=503,
    )
