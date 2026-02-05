"""Search index + API helpers for PiNotes Lite.

Implements an in-DB FTS5 index of the entire vault plus a background task
that refreshes the index on a configurable interval.  We also expose a
simple API to query the index with snippets that wrap matches in `<mark>`.
"""

import asyncio
import logging
import os
import re
import sqlite3
import time
from pathlib import Path

from app import config, database
from app.notes import _parse_frontmatter
from app.pathguard import resolve_note
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ── configuration ──────────────────────────────────────────────────────────────

_REFRESH_MINUTES = int(os.environ.get("SEARCH_REFRESH_MINUTES", "5"))
if _REFRESH_MINUTES <= 0:
    _REFRESH_MINUTES = 5
_REFRESH_INTERVAL_SECONDS = _REFRESH_MINUTES * 60
_SEARCH_LIMIT = 20
_SNIPPET_EARLY = 60
_SNIPPET_LATE = 90
_FALLBACK_SNIPPET = 150
_ELLIPSIS = "…"

# ── search index helpers ───────────────────────────────────────────────────────


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            path UNINDEXED,
            title,
            body
        );

        CREATE TABLE IF NOT EXISTS notes_index_meta (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL
        );
        """
    )


def _gather_notes() -> list[dict]:
    """Walk the vault and return metadata for every Markdown note."""
    vault = config.get().vault_dir
    notes: list[dict] = []

    for path in vault.rglob("*.md"):
        rel = path.relative_to(vault)
        rel_str = rel.as_posix()

        try:
            resolved = resolve_note(rel_str)
        except HTTPException:
            continue

        content = resolved.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(content)
        mtime = resolved.stat().st_mtime
        title = _derive_title(resolved.name, body, frontmatter)

        notes.append({
            "path": rel_str,
            "title": title,
            "body": body,
            "mtime": mtime,
        })

    return notes


def _build_snippet(body: str, query: str) -> str:
    """Return a snippet around the first match with <mark> tags."""
    normalized = query.strip().lower()
    if not normalized:
        return body[:_FALLBACK_SNIPPET] + (_ELLIPSIS if len(body) > _FALLBACK_SNIPPET else "")

    terms = [term for term in normalized.split() if term]
    lower = body.lower()
    matches = [(lower.find(term), term) for term in terms if term in lower]
    if matches:
        position, term = min(matches, key=lambda pair: pair[0])
        start = max(position - _SNIPPET_EARLY, 0)
        end = min(position + len(term) + _SNIPPET_LATE, len(body))
        snippet = body[start:end]
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        snippet = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", snippet, count=1)
        prefix = _ELLIPSIS if start > 0 else ""
        suffix = _ELLIPSIS if end < len(body) else ""
        return f"{prefix}{snippet}{suffix}"

    snippet = body[:_FALLBACK_SNIPPET]
    suffix = _ELLIPSIS if len(body) > _FALLBACK_SNIPPET else ""
    return f"{snippet}{suffix}"


def _derive_title(name: str, body: str, frontmatter: dict | None) -> str:
    """Return the note title (frontmatter title, first H1, or filename)."""
    if frontmatter:
        title = frontmatter.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return Path(name).stem


def refresh_index() -> tuple[int, float]:
    """Rebuild the search index for every note in the vault.

    Returns
    -------
    (count, duration)
        Number of notes indexed and the time taken (seconds).
    """
    notes = _gather_notes()
    start = time.perf_counter()
    conn = database.get_db()
    try:
        _ensure_tables(conn)
        existing = {
            row["path"]: row["mtime"]
            for row in conn.execute("SELECT path, mtime FROM notes_index_meta")
        }
        current_paths = {note["path"] for note in notes}

        for path in set(existing) - current_paths:
            conn.execute("DELETE FROM notes_fts WHERE path = ?", (path,))
            conn.execute("DELETE FROM notes_index_meta WHERE path = ?", (path,))

        for note in notes:
            if existing.get(note["path"]) == note["mtime"]:
                continue
            conn.execute("DELETE FROM notes_fts WHERE path = ?", (note["path"],))
            conn.execute(
                "INSERT INTO notes_fts (path, title, body) VALUES (?, ?, ?)",
                (note["path"], note["title"], note["body"]),
            )
            conn.execute(
                "INSERT OR REPLACE INTO notes_index_meta (path, mtime) VALUES (?, ?)",
                (note["path"], note["mtime"]),
            )
        conn.commit()
    finally:
        conn.close()
    duration = time.perf_counter() - start
    return len(notes), duration


def search_notes(query: str) -> list[dict]:
    """Query the FTS index and return up to 20 matches with snippet highlights."""
    normalized = query.strip()
    if not normalized:
        return []

    conn = database.get_db()
    try:
        rows = conn.execute(
            """
            SELECT path, title, body
            FROM notes_fts
            WHERE notes_fts MATCH ?
            ORDER BY bm25(notes_fts)
            LIMIT ?
            """,
            (normalized, _SEARCH_LIMIT),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        logger.warning("Search query failed (%s): %s", normalized, exc)
        return []
    finally:
        conn.close()

    results = []
    for row in rows:
        snippet = _build_snippet(row["body"], normalized)
        title = row["title"] or Path(row["path"]).stem
        results.append({"path": row["path"], "title": title, "snippet": snippet})
    return results


# ── background manager ───────────────────────────────────────────────────────


class SearchManager:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task or not self._stop_event:
            return
        self._stop_event.set()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self._stop_event = None

    async def _run(self) -> None:
        while self._stop_event and not self._stop_event.is_set():
            try:
                count, duration = await asyncio.to_thread(refresh_index)
                logger.info("Indexed %d notes in %.2fs", count, duration)
            except Exception:
                logger.exception("Search index refresh failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=_REFRESH_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue


search_manager = SearchManager()
