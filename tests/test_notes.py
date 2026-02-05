"""Tests for app.notes — note reading and frontmatter parsing."""

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.notes import read_note, _parse_frontmatter


# ── fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Scaffold a mini-vault and wire config.get() → tmp_path."""

    # Valid notes
    (tmp_path / "00-inbox").mkdir()
    (tmp_path / "00-inbox" / "with-frontmatter.md").write_text(
        '---\ntitle: "Hello World"\ntags: ["test", "inbox"]\ncreated: "2026-01-01"\n---\n'
        "# Hello World\n\nThis is the body.\n"
    )
    (tmp_path / "00-inbox" / "no-frontmatter.md").write_text(
        "# Plain note\n\nNo frontmatter here.\n"
    )
    (tmp_path / "00-inbox" / "malformed-yaml.md").write_text(
        "---\ntitle: [unclosed bracket\n---\n# Oops\n"
    )
    (tmp_path / "00-inbox" / "empty-frontmatter.md").write_text(
        "---\n---\n# Empty FM\n\nBody here.\n"
    )
    (tmp_path / "00-inbox" / "scalar-frontmatter.md").write_text(
        "---\njust a string\n---\n# Scalar FM\n"
    )

    # Blocked / edge cases
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.md").write_text("secret\n")
    (tmp_path / "_private").mkdir()
    (tmp_path / "_private" / "secret.md").write_text("secret\n")
    (tmp_path / "00-inbox" / "image.png").write_bytes(b"\x89PNG")

    # Symlink escaping vault
    (tmp_path / "evil-link.md").symlink_to("/etc/hostname")

    settings = Settings(vault_dir=tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr("app.pathguard.config.get", lambda: settings)

    return tmp_path


# ════════════════════════════════════════════════════════════════════════════════
# _parse_frontmatter (unit)
# ════════════════════════════════════════════════════════════════════════════════


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        content = '---\ntitle: "Hello"\ntags: [a, b]\n---\n# Body\n'
        fm, body = _parse_frontmatter(content)
        assert fm == {"title": "Hello", "tags": ["a", "b"]}
        assert body == "# Body\n"

    def test_no_frontmatter(self):
        content = "# Just a note\n\nNo delimiters.\n"
        fm, body = _parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_no_closing_delimiter(self):
        content = "---\ntitle: Orphan\n# No close\n"
        fm, body = _parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_malformed_yaml(self):
        content = "---\ntitle: [broken\n---\n# Body\n"
        fm, body = _parse_frontmatter(content)
        assert fm is None
        assert body == content  # full content returned as body

    def test_empty_frontmatter_block(self):
        content = "---\n---\n# Body\n"
        fm, body = _parse_frontmatter(content)
        # yaml.safe_load("") → None, not a dict → treated as absent
        assert fm is None
        assert body == content

    def test_scalar_frontmatter(self):
        content = "---\njust a string\n---\n# Body\n"
        fm, body = _parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_body_preserves_leading_newline(self):
        content = "---\ntitle: Hi\n---\n\n# Spaced body\n"
        fm, body = _parse_frontmatter(content)
        assert fm == {"title": "Hi"}
        assert body == "\n# Spaced body\n"


# ════════════════════════════════════════════════════════════════════════════════
# read_note (integration — goes through pathguard)
# ════════════════════════════════════════════════════════════════════════════════


class TestReadNote:
    # ── happy path ───────────────────────────────────────────────────────

    def test_read_note_with_frontmatter(self, vault):
        result = read_note("00-inbox/with-frontmatter.md")
        assert result["path"] == "00-inbox/with-frontmatter.md"
        assert result["frontmatter"]["title"] == "Hello World"
        assert result["frontmatter"]["tags"] == ["test", "inbox"]
        assert "# Hello World" in result["body"]

    def test_read_note_without_frontmatter(self, vault):
        result = read_note("00-inbox/no-frontmatter.md")
        assert result["frontmatter"] is None
        assert result["body"].startswith("# Plain note")

    def test_read_note_malformed_yaml_no_crash(self, vault):
        result = read_note("00-inbox/malformed-yaml.md")
        assert result["frontmatter"] is None
        # Full file content returned as body
        assert "unclosed bracket" in result["body"]

    def test_read_note_empty_frontmatter(self, vault):
        result = read_note("00-inbox/empty-frontmatter.md")
        assert result["frontmatter"] is None

    def test_read_note_scalar_frontmatter(self, vault):
        result = read_note("00-inbox/scalar-frontmatter.md")
        assert result["frontmatter"] is None

    # ── 400 – bad path / wrong extension ─────────────────────────────────

    def test_non_md_extension(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            read_note("00-inbox/image.png")
        assert exc_info.value.status_code == 400

    def test_absolute_path(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            read_note("/etc/passwd.md")
        assert exc_info.value.status_code == 400

    def test_dotdot_traversal(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            read_note("00-inbox/../../etc/passwd.md")
        assert exc_info.value.status_code == 400

    # ── 403 – sandbox violations ─────────────────────────────────────────

    def test_dotgit_blocked(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            read_note(".git/config.md")
        assert exc_info.value.status_code == 403

    def test_private_blocked(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            read_note("_private/secret.md")
        assert exc_info.value.status_code == 403

    def test_symlink_escape(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            read_note("evil-link.md")
        assert exc_info.value.status_code == 403

    # ── 404 – not found ──────────────────────────────────────────────────

    def test_missing_note(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            read_note("00-inbox/missing.md")
        assert exc_info.value.status_code == 404
