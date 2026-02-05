"""Tests for app.auth — login rate limiting and lockout."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app import auth, database
from app.auth import LoginResult
from app.config import Settings


# ── fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Scaffold a fresh DB with one admin user and wire config + auth env."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Vault dir just needs to exist for Settings
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    settings = Settings(vault_dir=vault_dir, data_dir=data_dir)
    monkeypatch.setattr("app.database.config.get", lambda: settings)
    monkeypatch.setattr("app.auth.get_db", lambda: database.get_db.__wrapped__()
                        if hasattr(database.get_db, "__wrapped__") else _get_db(data_dir))

    # Patch get_db in auth module to use our temp DB
    import sqlite3

    def _patched_get_db() -> sqlite3.Connection:
        db_path = data_dir / "pinotes_lite.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr("app.auth.get_db", _patched_get_db)
    monkeypatch.setattr("app.database.config.get", lambda: settings)

    # Init DB
    database.init_db()

    # Bootstrap admin via env
    monkeypatch.setenv("ADMIN_USERNAME", "testadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
    auth.bootstrap_admin()

    return data_dir


def _get_db(data_dir: Path):
    """Fallback helper — shouldn't normally be called."""
    import sqlite3
    db_path = data_dir / "pinotes_lite.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── helpers ──────────────────────────────────────────────────────────────────


def _set_rate_limit(monkeypatch: pytest.MonkeyPatch, max_failures: int = 5, lockout_minutes: int = 15):
    """Override rate-limit config on the auth module."""
    monkeypatch.setattr("app.auth.LOGIN_MAX_FAILURES", max_failures)
    monkeypatch.setattr("app.auth.LOGIN_LOCKOUT_MINUTES", lockout_minutes)


# ════════════════════════════════════════════════════════════════════════════════
# Basic login
# ════════════════════════════════════════════════════════════════════════════════


class TestLoginBasic:
    def test_successful_login_returns_token(self, db, monkeypatch):
        _set_rate_limit(monkeypatch)
        result = auth.login("testadmin", "secret123")
        assert isinstance(result, LoginResult)
        assert result.token is not None
        assert result.locked_until is None

    def test_wrong_password_returns_no_token(self, db, monkeypatch):
        _set_rate_limit(monkeypatch)
        result = auth.login("testadmin", "wrongpassword")
        assert result.token is None
        assert result.locked_until is None

    def test_unknown_user_returns_no_token(self, db, monkeypatch):
        _set_rate_limit(monkeypatch)
        result = auth.login("nonexistent", "password")
        assert result.token is None
        assert result.locked_until is None


# ════════════════════════════════════════════════════════════════════════════════
# Rate limiting
# ════════════════════════════════════════════════════════════════════════════════


class TestRateLimiting:
    def test_lockout_after_max_failures(self, db, monkeypatch):
        """5 wrong passwords → account locked."""
        _set_rate_limit(monkeypatch, max_failures=5)

        for i in range(4):
            result = auth.login("testadmin", "wrong")
            assert result.token is None
            assert result.locked_until is None, f"Should not be locked after {i + 1} failures"

        # 5th failure triggers lockout
        result = auth.login("testadmin", "wrong")
        assert result.token is None
        assert result.locked_until is not None
        assert result.locked_until > time.time()

    def test_locked_account_returns_locked_until(self, db, monkeypatch):
        """Once locked, subsequent attempts return locked_until without checking password."""
        _set_rate_limit(monkeypatch, max_failures=3)

        # Trigger lockout
        for _ in range(3):
            auth.login("testadmin", "wrong")

        # Even with correct password, should return locked
        result = auth.login("testadmin", "secret123")
        assert result.token is None
        assert result.locked_until is not None

    def test_successful_login_resets_counter(self, db, monkeypatch):
        """A successful login clears failed_attempts."""
        _set_rate_limit(monkeypatch, max_failures=5)

        # 3 failures
        for _ in range(3):
            auth.login("testadmin", "wrong")

        # Successful login
        result = auth.login("testadmin", "secret123")
        assert result.token is not None
        assert result.locked_until is None

        # Now 4 more failures shouldn't lock (counter was reset)
        for i in range(4):
            result = auth.login("testadmin", "wrong")
            assert result.locked_until is None, f"Should not be locked after {i + 1} failures post-reset"

    def test_lockout_persists_across_calls(self, db, monkeypatch):
        """locked_until stored in DB survives across login() calls."""
        _set_rate_limit(monkeypatch, max_failures=2, lockout_minutes=15)

        # Trigger lockout
        auth.login("testadmin", "wrong")
        auth.login("testadmin", "wrong")

        # Multiple calls all return locked_until
        for _ in range(3):
            result = auth.login("testadmin", "wrong")
            assert result.locked_until is not None

    def test_lockout_expires_and_login_works(self, db, monkeypatch):
        """After lockout duration passes, login works again."""
        _set_rate_limit(monkeypatch, max_failures=2, lockout_minutes=1)

        # Trigger lockout
        auth.login("testadmin", "wrong")
        result = auth.login("testadmin", "wrong")
        assert result.locked_until is not None

        # Mock time.time() to be 2 minutes in the future
        future_time = time.time() + 120  # 2 min ahead
        with patch("app.auth.time.time", return_value=future_time):
            result = auth.login("testadmin", "secret123")
            assert result.token is not None
            assert result.locked_until is None

    def test_custom_max_failures_env(self, db, monkeypatch):
        """LOGIN_MAX_FAILURES=2 locks after 2 failures."""
        _set_rate_limit(monkeypatch, max_failures=2)

        result = auth.login("testadmin", "wrong")
        assert result.locked_until is None

        result = auth.login("testadmin", "wrong")
        assert result.locked_until is not None

    def test_lockout_duration_is_correct(self, db, monkeypatch):
        """locked_until is approximately now + lockout_minutes * 60."""
        _set_rate_limit(monkeypatch, max_failures=1, lockout_minutes=15)

        before = time.time()
        result = auth.login("testadmin", "wrong")
        after = time.time()

        assert result.locked_until is not None
        # locked_until should be ~15 min from now
        expected_min = before + 15 * 60
        expected_max = after + 15 * 60
        assert expected_min <= result.locked_until <= expected_max
