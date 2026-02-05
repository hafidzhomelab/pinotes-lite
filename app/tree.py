"""Vault file-tree walker with filtering and short-lived in-memory cache.

The tree is used by the sidebar UI.  It is a single recursive walk of the
vault directory — perfectly fine at personal-scale (hundreds of files).

Filtering
---------
* Any directory or file whose name starts with ``.`` is skipped (dotfiles /
  dotdirs such as ``.git``, ``.DS_Store``).
* Directories in ``TREE_BLOCKED`` are skipped entirely (``_private``,
  ``_attachments``).

Ordering
--------
Within every directory: sub-directories first (sorted), then files (sorted).
Both lists are sorted case-sensitively by name (matches typical filesystem
behaviour on Linux).
"""

import time
from pathlib import Path

from app import config

# ── filtering ────────────────────────────────────────────────────────────────

# Blocked directory names — hidden even if they exist in the vault.
# _attachments is accessible via /api/attachments/{path} only.
TREE_BLOCKED: frozenset[str] = frozenset({"_private", "_attachments"})

# TTL for the cached tree (seconds).  10 s is plenty for a sidebar that
# doesn't need to reflect brand-new files instantly.
TREE_CACHE_TTL: int = 10


def _is_hidden(name: str) -> bool:
    """Return True if *name* should be excluded from the tree."""
    return name.startswith(".") or name in TREE_BLOCKED


# ── recursive walk ───────────────────────────────────────────────────────────


def _walk(directory: Path, prefix: str) -> dict:
    """Return a nested tree dict for *directory*.

    ``prefix`` is the relative path from the vault root to *directory*
    (empty string for the root itself).
    """
    dirs: list[Path] = []
    files: list[Path] = []

    for entry in directory.iterdir():
        if _is_hidden(entry.name):
            continue
        if entry.is_dir():
            dirs.append(entry)
        elif entry.is_file():
            files.append(entry)
        # symlinks / other — skip silently

    dirs.sort(key=lambda p: p.name)
    files.sort(key=lambda p: p.name)

    children: list[dict] = []

    # Directories first
    for d in dirs:
        child_prefix = prefix + d.name + "/"
        children.append(_walk(d, child_prefix))

    # Then files
    for f in files:
        children.append({
            "type": "file",
            "name": f.name,
            "path": prefix + f.name,
        })

    return {
        "type": "dir",
        "name": directory.name,
        "children": children,
    }


# ── cache + public API ───────────────────────────────────────────────────────

_cache_result: dict | None = None
_cache_time: float | None = None


def get_tree() -> dict:
    """Return the vault tree, using the in-memory cache when fresh."""
    global _cache_result, _cache_time

    now = time.time()
    if _cache_result is not None and _cache_time is not None:
        if now - _cache_time < TREE_CACHE_TTL:
            return _cache_result

    vault_dir: Path = config.get().vault_dir
    tree = _walk(vault_dir, "")
    # Root node name is always "notes" for a consistent frontend label
    tree["name"] = "notes"

    _cache_result = tree
    _cache_time = now
    return tree
