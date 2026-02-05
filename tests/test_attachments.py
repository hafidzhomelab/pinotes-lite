"""Tests for the attachments endpoint logic — path resolution + MIME detection.

We test resolve_attachment (pathguard) integration and the mimetypes detection
used by the route.  The route itself is a thin wrapper so we keep tests focused
on the important parts: sandbox enforcement and correct MIME guessing.
"""

import mimetypes
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.pathguard import resolve_attachment


# ── fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Scaffold a mini-vault with various attachment types."""

    (tmp_path / "_attachments").mkdir()
    (tmp_path / "_attachments" / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "_attachments" / "chart.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "_attachments" / "anim.gif").write_bytes(b"GIF89a")
    (tmp_path / "_attachments" / "modern.webp").write_bytes(b"RIFF")
    (tmp_path / "_attachments" / "logo.svg").write_text("<svg></svg>")
    (tmp_path / "_attachments" / "report.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "_attachments" / "mystery.qwerty").write_bytes(b"\x00\x01")

    # Nested attachment in a resources dir
    (tmp_path / "04-resources").mkdir()
    (tmp_path / "04-resources" / "inline.png").write_bytes(b"\x89PNG")

    # Blocked / edge cases
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "secret.bin").write_bytes(b"secret")
    (tmp_path / "_private").mkdir()
    (tmp_path / "_private" / "key.pem").write_text("PRIVATE KEY\n")

    # Symlink escaping vault
    (tmp_path / "evil.png").symlink_to("/etc/hostname")

    settings = Settings(vault_dir=tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr("app.pathguard.config.get", lambda: settings)

    return tmp_path


# ── helpers ──────────────────────────────────────────────────────────────────


def _mime(path: str) -> str:
    """Guess MIME the same way the route does."""
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


# ════════════════════════════════════════════════════════════════════════════════
# Path resolution (via pathguard)
# ════════════════════════════════════════════════════════════════════════════════


class TestAttachmentResolution:
    # ── happy path ───────────────────────────────────────────────────────

    def test_resolve_attachment_in_attachments_dir(self, vault):
        resolved = resolve_attachment("_attachments/photo.png")
        assert resolved.name == "photo.png"
        assert resolved.is_file()

    def test_resolve_nested_attachment(self, vault):
        resolved = resolve_attachment("04-resources/inline.png")
        assert resolved.name == "inline.png"
        assert resolved.is_file()

    # ── 400 – malformed ──────────────────────────────────────────────────

    def test_absolute_path(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            resolve_attachment("/etc/passwd")
        assert exc_info.value.status_code == 400

    def test_dotdot_traversal(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            resolve_attachment("_attachments/../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_null_byte(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            resolve_attachment("_attachments/photo\x00.png")
        assert exc_info.value.status_code == 400

    # ── 403 – sandbox ────────────────────────────────────────────────────

    def test_dotgit_blocked(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            resolve_attachment(".git/secret.bin")
        assert exc_info.value.status_code == 403

    def test_private_blocked(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            resolve_attachment("_private/key.pem")
        assert exc_info.value.status_code == 403

    def test_symlink_escape(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            resolve_attachment("evil.png")
        assert exc_info.value.status_code == 403

    # ── 404 – not found ──────────────────────────────────────────────────

    def test_missing_file(self, vault):
        with pytest.raises(HTTPException) as exc_info:
            resolve_attachment("_attachments/nope.png")
        assert exc_info.value.status_code == 404


# ════════════════════════════════════════════════════════════════════════════════
# MIME type detection (mirrors route logic)
# ════════════════════════════════════════════════════════════════════════════════


class TestMimeDetection:
    def test_png(self):
        assert _mime("photo.png") == "image/png"

    def test_jpg(self):
        assert _mime("chart.jpg") == "image/jpeg"

    def test_jpeg(self):
        assert _mime("chart.jpeg") == "image/jpeg"

    def test_gif(self):
        assert _mime("anim.gif") == "image/gif"

    def test_webp(self):
        assert _mime("modern.webp") == "image/webp"

    def test_svg(self):
        assert _mime("logo.svg") == "image/svg+xml"

    def test_pdf(self):
        assert _mime("report.pdf") == "application/pdf"

    def test_unknown_extension_fallback(self):
        assert _mime("mystery.qwerty") == "application/octet-stream"

    def test_no_extension_fallback(self):
        assert _mime("noext") == "application/octet-stream"
