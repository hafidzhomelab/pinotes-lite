"""Tests for the search index builder + query helper."""

from pathlib import Path

import pytest

from app.config import Settings
from app import database
from app.search import refresh_index, search_notes


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a small vault and point config.get() → it."""

    vault_dir = tmp_path / "notes"
    vault_dir.mkdir()
    (vault_dir / "00-inbox").mkdir()
    (vault_dir / "00-inbox" / "searchable.md").write_text(
        "# Searchable Note\n\nThe quick brown fox jumps over the lazy dog.\n"
    )
    (vault_dir / "00-inbox" / "title-test.md").write_text(
        "# Big Idea\n\nContent here.\n"
    )

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    settings = Settings(vault_dir=vault_dir, data_dir=data_dir)
    monkeypatch.setattr("app.config.get", lambda: settings)

    database.init_db()

    return vault_dir


def test_search_returns_marked_snippet(vault: Path):
    refresh_index()
    results = search_notes("brown")
    assert results, "Expected at least one result for 'brown'"
    first = results[0]
    assert "searchable" in first["path"]
    assert "<mark>brown</mark>" in first["snippet"]


def test_search_title_from_h1(vault: Path):
    refresh_index()
    results = search_notes("big")
    titles = [res["title"] for res in results]
    assert "Big Idea" in titles


def test_empty_query_returns_empty(vault: Path):
    refresh_index()
    assert search_notes("   ") == []


def test_refresh_index_picks_up_new_note(vault: Path):
    refresh_index()
    new_note = vault / "00-inbox" / "new-note.md"
    new_note.write_text("# Fresh\n\nUnique term: zephyr.\n")
    refresh_index()
    results = search_notes("zephyr")
    assert results
    assert any("new-note" in res["path"] for res in results)
