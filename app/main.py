"""PiNotes Lite — FastAPI backend."""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import auth, config, database


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup ── load + validate config (sys.exit on error)
    config.load()
    database.init_db()
    auth.bootstrap_admin()
    yield
    # Shutdown ── nothing to clean up yet


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="PiNotes Lite", lifespan=lifespan)


# ── Auth dependency ──────────────────────────────────────────────────────────


def require_auth(session: str | None = Cookie(default=None)) -> int:
    """Validate session cookie and return user_id. Raises 401 if invalid."""
    user_id = auth.validate_session(session) if session else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


# ── Auth routes ──────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
async def api_login(body: LoginRequest, response: Response):
    """Authenticate and set session cookie."""
    result = auth.login(body.username, body.password)
    if result.locked_until:
        return JSONResponse(
            {"locked_until": datetime.fromtimestamp(result.locked_until).isoformat()},
            status_code=429,
        )
    token = result.token
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"authenticated": True}


@app.post("/api/auth/logout")
async def api_logout(
    response: Response, session: str | None = Cookie(default=None)
) -> dict:
    """Clear session cookie and delete session."""
    if session:
        auth.logout(session)
    response.delete_cookie(key="session", path="/")
    return {}


@app.get("/api/auth/me")
async def api_me(session: str | None = Cookie(default=None)) -> dict:
    """Check if current session is authenticated."""
    user_id = auth.validate_session(session) if session else None
    return {"authenticated": user_id is not None}


# ── API routes ───────────────────────────────────────────────────────────────


@app.get("/api/healthz")
async def healthz(_user_id: int = Depends(require_auth)) -> dict:
    """Liveness / health check (requires auth)."""
    return {"status": "ok"}


# ── Notes API ────────────────────────────────────────────────────────────────


@app.get("/api/notes/tree")
async def api_tree(_user_id: int = Depends(require_auth)) -> dict:
    """Return the full vault file tree (filtered, cached)."""
    from app.tree import get_tree

    return get_tree()


@app.get("/api/notes/{path:path}")
async def api_read_note(path: str, _user_id: int = Depends(require_auth)) -> dict:
    """Read a single note — returns parsed frontmatter + raw Markdown body."""
    from app.notes import read_note

    return read_note(path)


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
