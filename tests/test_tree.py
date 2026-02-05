"""Tests for app.tree — vault file-tree walker, filtering, caching."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import Settings


# ── fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Scaffold a mini-vault and wire config.get() → tmp_path."""

    # PARA structure
    (tmp_path / "00-inbox").mkdir()
    (tmp_path / "02-projects" / "pinotes-lite").mkdir(parents=True)
    (tmp_path / "03-areas").mkdir()  # intentionally empty after filtering
    (tmp_path / "04-resources").mkdir()

    # Notes
    (tmp_path / "00-inbox" / "hello.md").write_text("# Hello\n")
    (tmp_path / "00-inbox" / "alpha.md").write_text("# Alpha\n")
    (tmp_path / "02-projects" / "pinotes-lite" / "notes.md").write_text("# Notes\n")
    (tmp_path / "04-resources" / "market.md").write_text("# Market\n")
    (tmp_path / "readme.md").write_text("# Readme\n")

    # Should be filtered out
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n")
    (tmp_path / "_private").mkdir()
    (tmp_path / "_private" / "secret.md").write_text("secret\n")
    (tmp_path / "_attachments").mkdir()
    (tmp_path / "_attachments" / "chart.png").write_bytes(b"\x89PNG")
    (tmp_path / ".gitignore").write_text("__pycache__\n")
    (tmp_path / ".DS_Store").write_bytes(b"\x00")

    settings = Settings(vault_dir=tmp_path, data_dir=tmp_path / "data")
    monkeypatch.setattr("app.tree.config.get", lambda: settings)

    # Reset module-level cache between tests
    import app.tree as tree_mod
    tree_mod._cache_result = None
    tree_mod._cache_time = None

    return tmp_path


# ── helpers ──────────────────────────────────────────────────────────────────


def _names_at(tree: dict, path: list[str] | None = None) -> dict[str, list[str]]:
    """Collect dir-names and file-names at a given path in the tree.

    Returns {"dirs": [...], "files": [...]}.
    """
    node = tree
    for segment in (path or []):
        node = next(c for c in node["children"] if c["name"] == segment)
    dirs = [c["name"] for c in node["children"] if c["type"] == "dir"]
    files = [c["name"] for c in node["children"] if c["type"] == "file"]
    return {"dirs": dirs, "files": files}


# ════════════════════════════════════════════════════════════════════════════════
# Structure & filtering
# ════════════════════════════════════════════════════════════════════════════════


class TestTreeStructure:
    def test_root_name_is_notes(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        assert tree["type"] == "dir"
        assert tree["name"] == "notes"

    def test_para_dirs_present(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        names = _names_at(tree)
        assert "00-inbox" in names["dirs"]
        assert "02-projects" in names["dirs"]
        assert "03-areas" in names["dirs"]
        assert "04-resources" in names["dirs"]

    def test_root_file_present(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        names = _names_at(tree)
        assert "readme.md" in names["files"]

    def test_nested_file_path(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        # Navigate to 00-inbox
        inbox = next(c for c in tree["children"] if c["name"] == "00-inbox")
        files = [c for c in inbox["children"] if c["type"] == "file"]
        paths = {f["path"] for f in files}
        assert "00-inbox/hello.md" in paths
        assert "00-inbox/alpha.md" in paths

    def test_deeply_nested_path(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        projects = next(c for c in tree["children"] if c["name"] == "02-projects")
        pinotes = next(c for c in projects["children"] if c["name"] == "pinotes-lite")
        files = [c for c in pinotes["children"] if c["type"] == "file"]
        assert len(files) == 1
        assert files[0]["path"] == "02-projects/pinotes-lite/notes.md"


class TestTreeFiltering:
    def test_dotgit_filtered(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        names = _names_at(tree)
        assert ".git" not in names["dirs"]

    def test_private_filtered(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        names = _names_at(tree)
        assert "_private" not in names["dirs"]

    def test_attachments_filtered(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        names = _names_at(tree)
        assert "_attachments" not in names["dirs"]

    def test_dotfiles_filtered(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        names = _names_at(tree)
        assert ".gitignore" not in names["files"]
        assert ".DS_Store" not in names["files"]

    def test_no_blocked_content_anywhere(self, vault):
        """Recursively verify nothing blocked appears anywhere in the tree."""
        from app.tree import get_tree

        blocked = {".git", "_private", "_attachments", ".gitignore", ".DS_Store"}

        def _check(node: dict):
            assert node["name"] not in blocked, f"Blocked name found: {node['name']}"
            if node["type"] == "dir":
                for child in node["children"]:
                    _check(child)

        _check(get_tree())


class TestTreeOrdering:
    def test_dirs_before_files(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        # Root has both dirs and files — dirs should come first
        saw_file = False
        for child in tree["children"]:
            if child["type"] == "file":
                saw_file = True
            if child["type"] == "dir" and saw_file:
                pytest.fail("Directory appeared after a file at root level")

    def test_dirs_sorted_alphabetically(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        dirs = [c["name"] for c in tree["children"] if c["type"] == "dir"]
        assert dirs == sorted(dirs)

    def test_files_sorted_alphabetically(self, vault):
        from app.tree import get_tree
        tree = get_tree()
        # Check inbox — has alpha.md and hello.md
        inbox = next(c for c in tree["children"] if c["name"] == "00-inbox")
        files = [c["name"] for c in inbox["children"] if c["type"] == "file"]
        assert files == sorted(files)
        assert files == ["alpha.md", "hello.md"]


class TestEmptyDirs:
    def test_empty_dir_included(self, vault):
        """03-areas is empty — should still appear."""
        from app.tree import get_tree
        tree = get_tree()
        areas = next((c for c in tree["children"] if c["name"] == "03-areas"), None)
        assert areas is not None
        assert areas["type"] == "dir"
        assert areas["children"] == []


# ════════════════════════════════════════════════════════════════════════════════
# Cache
# ════════════════════════════════════════════════════════════════════════════════


class TestTreeCache:
    def test_cache_returns_same_object(self, vault):
        from app.tree import get_tree
        first = get_tree()
        second = get_tree()
        assert first is second  # same object — cache hit

    def test_cache_expires(self, vault):
        from app.tree import get_tree
        import app.tree as tree_mod

        first = get_tree()

        # Pretend 11 seconds have passed
        tree_mod._cache_time = time.time() - 11

        # Add a new file to the vault so the fresh walk differs
        (vault / "00-inbox" / "new-note.md").write_text("# New\n")

        second = get_tree()
        assert first is not second  # fresh walk after TTL

        # Verify the new file is present
        inbox = next(c for c in second["children"] if c["name"] == "00-inbox")
        file_names = [c["name"] for c in inbox["children"] if c["type"] == "file"]
        assert "new-note.md" in file_names
