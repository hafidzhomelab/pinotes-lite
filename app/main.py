"""PiNotes Lite — FastAPI backend."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup ── load + validate config (sys.exit on error)
    config.load()
    yield
    # Shutdown ── nothing to clean up yet


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="PiNotes Lite", lifespan=lifespan)


# ── API routes ───────────────────────────────────────────────────────────────


@app.get("/api/healthz")
async def healthz() -> dict:
    """Liveness / health check."""
    return {"status": "ok"}


# ── Static files + SPA fallback ──────────────────────────────────────────────
# Vite build output: <project-root>/frontend/dist/
# Layout is identical inside the Docker image.

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "frontend" / "dist"
INDEX_HTML = STATIC_DIR / "index.html"

# Serve Vite-generated assets (/assets/*)
if (STATIC_DIR / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(STATIC_DIR / "assets")),
        name="assets",
    )


# Catch-all — return index.html so React Router handles client-side routes.
@app.get("/{full_path:path}")
async def spa_fallback() -> FileResponse:
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return JSONResponse(
        {"error": "Frontend not built. Run `cd frontend && npm run build`"},
        status_code=503,
    )
