"""PiNotes Lite — FastAPI backend."""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import mimetypes

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import auth, config, database, search


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup ── load + validate config (sys.exit on error)
    config.load()
    database.init_db()
    auth.bootstrap_admin()
    search.search_manager.start()
    try:
        yield
    finally:
        await search.search_manager.stop()


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


@app.get("/api/notes/search")
async def api_search(q: str | None = None, _user_id: int = Depends(require_auth)) -> list[dict]:
    """Search the vault notes using the FTS index."""
    return search.search_notes(q or "")


# ── Wikilinks API (must be before /api/notes/{path:path}) ────────────────────


@app.get("/api/notes/index")
async def api_notes_index(_user_id: int = Depends(require_auth)) -> dict:
    """Return filename -> paths mapping for wikilink resolution."""
    from app.wikilinks import get_wikilink_index

    index = get_wikilink_index().get_index()
    return {"index": index}


@app.get("/api/notes/backlinks")
async def api_notes_backlinks(
    filename: str = Query(..., description="Filename to find backlinks for"),
    _user_id: int = Depends(require_auth)
) -> list[dict]:
    """Return notes that link to the given filename."""
    from app.wikilinks import get_backlink_finder

    finder = get_backlink_finder()
    return finder.find_backlinks(filename)


# ── Note read (catch-all - must be after specific routes) ────────────────────


@app.get("/api/notes/{path:path}")
async def api_read_note(path: str, _user_id: int = Depends(require_auth)) -> dict:
    """Read a single note — returns parsed frontmatter + raw Markdown body."""
    from app.notes import read_note

    return read_note(path)


@app.get("/api/attachments/{path:path}")
async def api_attachment(path: str, _user_id: int = Depends(require_auth)) -> Response:
    """Serve any file from the vault with auto-detected Content-Type."""
    from app.pathguard import resolve_attachment

    resolved = resolve_attachment(path)
    media_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
    return FileResponse(str(resolved), media_type=media_type)


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
