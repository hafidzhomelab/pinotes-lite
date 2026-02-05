"""Note reader — read a single .md file, split frontmatter from body.

Public API
----------
read_note(raw_path: str) -> dict
    Validates *raw_path* through the safe-path layer, reads the file, and
    returns ``{"path": ..., "frontmatter": ... | None, "body": ...}``.

Frontmatter handling
--------------------
* If the file starts with ``---\\n``, the block up to the next ``---`` is
  parsed as YAML.  On success ``frontmatter`` is the parsed dict; on failure
  (malformed YAML) it falls back to ``None`` and the *entire* file content
  becomes the body.
* If there is no opening ``---``, ``frontmatter`` is ``None`` and the whole
  file is the body.
"""

import logging
from pathlib import Path

import yaml

from app.pathguard import resolve_note

logger = logging.getLogger(__name__)

# ── frontmatter splitter ─────────────────────────────────────────────────────

_DELIM = "---"


def _parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Split *content* into (frontmatter_dict | None, body_string).

    Returns (None, content) when there is no valid frontmatter block.
    """
    # Must start with --- on its own line
    if not content.startswith(_DELIM + "\n"):
        return None, content

    # Find the closing ---
    end = content.find("\n" + _DELIM + "\n", len(_DELIM))
    if end == -1:
        # No closing delimiter — treat as no frontmatter
        return None, content

    raw_yaml = content[len(_DELIM) + 1 : end + 1]  # between the two ---
    body = content[end + 1 + len(_DELIM) + 1 :]  # after closing ---\n

    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        logger.warning("Malformed YAML frontmatter: %s", exc)
        return None, content

    # yaml.safe_load can return a scalar if the YAML is e.g. just a string
    if not isinstance(parsed, dict):
        logger.warning("Frontmatter is not a mapping — treating as absent")
        return None, content

    return parsed, body


# ── public API ───────────────────────────────────────────────────────────────


def read_note(raw_path: str) -> dict:
    """Validate *raw_path*, read the note, and return parsed result.

    Raises
    ------
    HTTPException (400)  – not a .md file or bad path syntax.
    HTTPException (403)  – sandbox violation.
    HTTPException (404)  – file not found.
    """
    resolved: Path = resolve_note(raw_path)  # all validation here
    content = resolved.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(content)

    return {
        "path": raw_path,
        "frontmatter": frontmatter,
        "body": body,
    }
