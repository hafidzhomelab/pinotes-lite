"""Vault path-guard — validates and sandboxes every file path.

All vault reads **must** go through this module.
Never call ``open()`` on user-supplied paths directly.

Public helpers
--------------
resolve_note(raw)        → Path   – must be a ``.md`` file inside the vault.
resolve_attachment(raw)  → Path   – any file inside the vault (images, …).

Raised exceptions map directly to HTTP status codes so FastAPI can
return them as-is.

PathError    (400)  – malformed input (absolute path, null byte, …).
SandboxError (403)  – path escapes the vault or targets a blocked name.
HTTPException(404)  – file does not exist.
"""

from pathlib import Path

from fastapi import HTTPException

from app import config

# ── blocked path segments ────────────────────────────────────────────────────
# Any segment that *is* one of these explicit names, or that starts with ".",
# is rejected.  This covers .git/, _private/, .DS_Store, etc.
_BLOCKED_NAMES: frozenset[str] = frozenset({".git", "_private"})


# ── custom exception helpers ─────────────────────────────────────────────────


class PathError(HTTPException):
    """400 – the path itself is syntactically invalid."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=400, detail=detail)


class SandboxError(HTTPException):
    """403 – well-formed path that escapes the vault or hits a blocked name."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=403, detail=detail)


# ── core validation ──────────────────────────────────────────────────────────


def _validate_and_resolve(raw: str) -> Path:
    """Validate *raw* and return its resolved absolute path inside the vault.

    Checks (in order)
    -----------------
    1. No null bytes.
    2. No backslashes (rules out Windows-style path tricks).
    3. Must be a relative path – no leading ``/``.
    4. No ``..`` segments anywhere.
    5. Every segment must not be a dotfile/dotdir and must not be in
       ``_BLOCKED_NAMES``.
    6. The fully-resolved path (symlinks followed) must remain inside
       ``VAULT_DIR``.  Because ``Path.resolve()`` follows every symlink
       before we compare, this single check catches all symlink-escape
       attempts transparently.
    """
    vault: Path = config.get().vault_dir

    # 1 – null bytes
    if "\x00" in raw:
        raise PathError("Path must not contain null bytes.")

    # 2 – backslashes
    if "\\" in raw:
        raise PathError("Path must not contain backslashes.")

    # 3 – must be relative
    if raw.startswith("/"):
        raise PathError("Path must be relative (no leading /).")

    # 4 – no ".." anywhere
    segments = Path(raw).parts
    if ".." in segments:
        raise PathError("Path must not contain '..' segments.")

    # 5 – blocked / hidden segments
    for seg in segments:
        if seg.startswith(".") or seg in _BLOCKED_NAMES:
            raise SandboxError(
                f"Access denied: '{seg}' is a blocked or hidden path segment."
            )

    # 6 – resolve (follows symlinks) and sandbox-check
    resolved: Path = (vault / raw).resolve()
    try:
        resolved.relative_to(vault)
    except ValueError as exc:
        raise SandboxError("Path resolves outside the vault.") from exc

    return resolved


# ── public API ───────────────────────────────────────────────────────────────


def resolve_note(raw: str) -> Path:
    """Validate *raw* and return the absolute path to a ``.md`` note.

    Raises
    ------
    PathError (400)        – malformed input.
    SandboxError (403)     – escapes vault / blocked segment.
    HTTPException (400)    – path does not end in ``.md``.
    HTTPException (404)    – file does not exist.
    """
    # Extension check on the *requested* name (not the symlink target)
    if not raw.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are allowed.")

    path = _validate_and_resolve(raw)

    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Note not found: {raw}")

    return path


def resolve_attachment(raw: str) -> Path:
    """Validate *raw* and return the absolute path to any vault file.

    Raises
    ------
    PathError (400)        – malformed input.
    SandboxError (403)     – escapes vault / blocked segment.
    HTTPException (404)    – file does not exist.
    """
    path = _validate_and_resolve(raw)

    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {raw}")

    return path
