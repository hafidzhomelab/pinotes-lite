"""Tests for app.pathguard — path validation and vault sandboxing."""

import pytest
from pathlib import Path

from fastapi import HTTPException

from app.config import Settings
from app.pathguard import PathError, SandboxError, resolve_note, resolve_attachment


# ── fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Scaffold a mini-vault and wire config.get() to point at it."""

    # directories
    (tmp_path / "00-inbox").mkdir()
    (tmp_path / "04-resources" / "market").mkdir(parents=True)
    (tmp_path / "_attachments").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "_private").mkdir()

    # files
    (tmp_path / "00-inbox" / "hello.md").write_text("# Hello\n")
    (tmp_path / "04-resources" / "market" / "btc.md").write_text("# BTC\n")
    (tmp_path / "_attachments" / "chart.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / ".git" / "config").write_text("[core]\n")
    (tmp_path / "_private" / "secret.md").write_text("secret\n")

    # symlink that stays inside the vault  → allowed
    (tmp_path / "good-link.md").symlink_to(tmp_path / "00-inbox" / "hello.md")
    # symlink that escapes the vault       → blocked
    (tmp_path / "evil-link.md").symlink_to("/etc/hostname")

    # patch config.get() in the pathguard module
    settings = Settings(vault_dir=tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr("app.pathguard.config.get", lambda: settings)

    return tmp_path


# ════════════════════════════════════════════════════════════════════════════════
# resolve_note
# ════════════════════════════════════════════════════════════════════════════════


class TestResolveNote:
    # ── happy path ───────────────────────────────────────────────────────

    def test_valid_note(self, vault: Path):
        result = resolve_note("00-inbox/hello.md")
        assert result == (vault / "00-inbox" / "hello.md").resolve()

    def test_nested_note(self, vault: Path):
        result = resolve_note("04-resources/market/btc.md")
        assert result.name == "btc.md"
        assert result.is_file()

    def test_symlink_inside_vault_allowed(self, vault: Path):
        result = resolve_note("good-link.md")
        assert result.is_file()

    # ── 400 – malformed paths ────────────────────────────────────────────

    def test_absolute_path(self, vault: Path):
        with pytest.raises(PathError):
            resolve_note("/etc/passwd.md")

    def test_dotdot_traversal(self, vault: Path):
        with pytest.raises(PathError):
            resolve_note("00-inbox/../../etc/passwd.md")

    def test_null_byte(self, vault: Path):
        with pytest.raises(PathError):
            resolve_note("00-inbox/hello\x00.md")

    def test_backslash(self, vault: Path):
        with pytest.raises(PathError):
            resolve_note("00-inbox\\hello.md")

    def test_non_md_extension(self, vault: Path):
        with pytest.raises(HTTPException) as exc_info:
            resolve_note("_attachments/chart.png")
        assert exc_info.value.status_code == 400

    # ── 403 – sandbox violations ─────────────────────────────────────────

    def test_dotgit_blocked(self, vault: Path):
        with pytest.raises(SandboxError):
            resolve_note(".git/config.md")

    def test_private_blocked(self, vault: Path):
        with pytest.raises(SandboxError):
            resolve_note("_private/secret.md")

    def test_hidden_segment_blocked(self, vault: Path):
        with pytest.raises(SandboxError):
            resolve_note(".hidden/note.md")

    def test_dotfile_in_name_blocked(self, vault: Path):
        with pytest.raises(SandboxError):
            resolve_note(".sneaky.md")

    def test_symlink_outside_vault(self, vault: Path):
        with pytest.raises(SandboxError):
            resolve_note("evil-link.md")

    # ── 404 – not found ──────────────────────────────────────────────────

    def test_missing_note(self, vault: Path):
        with pytest.raises(HTTPException) as exc_info:
            resolve_note("00-inbox/missing.md")
        assert exc_info.value.status_code == 404


# ════════════════════════════════════════════════════════════════════════════════
# resolve_attachment
# ════════════════════════════════════════════════════════════════════════════════


class TestResolveAttachment:
    # ── happy path ───────────────────────────────────────────────────────

    def test_valid_attachment(self, vault: Path):
        result = resolve_attachment("_attachments/chart.png")
        assert result == (vault / "_attachments" / "chart.png").resolve()

    # ── 400 – malformed ──────────────────────────────────────────────────

    def test_absolute_path(self, vault: Path):
        with pytest.raises(PathError):
            resolve_attachment("/etc/passwd")

    def test_dotdot_traversal(self, vault: Path):
        with pytest.raises(PathError):
            resolve_attachment("_attachments/../../etc/passwd")

    def test_null_byte(self, vault: Path):
        with pytest.raises(PathError):
            resolve_attachment("_attachments/chart\x00.png")

    def test_backslash(self, vault: Path):
        with pytest.raises(PathError):
            resolve_attachment("_attachments\\chart.png")

    # ── 403 – sandbox ────────────────────────────────────────────────────

    def test_private_blocked(self, vault: Path):
        with pytest.raises(SandboxError):
            resolve_attachment("_private/secret.md")

    def test_dotgit_blocked(self, vault: Path):
        with pytest.raises(SandboxError):
            resolve_attachment(".git/config")

    def test_symlink_outside_vault(self, vault: Path):
        with pytest.raises(SandboxError):
            resolve_attachment("evil-link.md")

    # ── 404 – not found ──────────────────────────────────────────────────

    def test_missing_attachment(self, vault: Path):
        with pytest.raises(HTTPException) as exc_info:
            resolve_attachment("_attachments/nope.png")
        assert exc_info.value.status_code == 404
