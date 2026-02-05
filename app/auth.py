"""Authentication: admin bootstrap, login, session management."""

import os
import secrets
import time
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.database import get_db

# Argon2id with recommended parameters: m=65536 KiB, t=3 iterations, p=4 parallelism
_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

# Session expiry in hours (default 24)
SESSION_EXPIRY_HOURS = int(os.environ.get("SESSION_EXPIRY_HOURS", "24"))
LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))


@dataclass
class LoginResult:
    token: str | None = None
    locked_until: float | None = None


def bootstrap_admin() -> None:
    """Create the admin user if users table is empty.

    Reads ADMIN_USERNAME and ADMIN_PASSWORD from env.
    If missing, logs a warning and skips.
    """
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()

    if not username or not password:
        print(
            "  ⚠  ADMIN_USERNAME or ADMIN_PASSWORD not set — skipping admin bootstrap"
        )
        return

    conn = get_db()
    try:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        if row[0] > 0:
            # Users already exist, don't overwrite
            return

        password_hash = _ph.hash(password)
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        print(f"  ✅  Admin user '{username}' created")
    finally:
        conn.close()


def login(username: str, password: str) -> LoginResult:
    """Authenticate user and create a session.

    Returns a LoginResult with token or lockout details.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, password_hash, failed_attempts, locked_until FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return LoginResult()

        if row["locked_until"] > time.time():
            return LoginResult(locked_until=row["locked_until"])

        try:
            _ph.verify(row["password_hash"], password)
        except VerifyMismatchError:
            new_failures = row["failed_attempts"] + 1
            if new_failures >= LOGIN_MAX_FAILURES:
                locked_until_ts = time.time() + LOGIN_LOCKOUT_MINUTES * 60
                conn.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (new_failures, locked_until_ts, row["id"]),
                )
                conn.commit()
                return LoginResult(locked_until=locked_until_ts)
            conn.execute(
                "UPDATE users SET failed_attempts = ? WHERE id = ?",
                (new_failures, row["id"]),
            )
            conn.commit()
            return LoginResult()

        # Check if rehash is needed (argon2-cffi handles param upgrades)
        if _ph.check_needs_rehash(row["password_hash"]):
            new_hash = _ph.hash(password)
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row["id"])
            )
            conn.commit()

        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = 0 WHERE id = ?",
            (row["id"],),
        )
        conn.commit()

        # Create session
        token = secrets.token_hex(32)
        now = time.time()
        expires_at = now + SESSION_EXPIRY_HOURS * 3600
        conn.execute(
            "INSERT INTO sessions (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (row["id"], token, now, expires_at),
        )
        conn.commit()
        return LoginResult(token=token)
    finally:
        conn.close()


def validate_session(token: str) -> int | None:
    """Check if a session token is valid.

    Returns user_id if valid, None otherwise.
    """
    if not token:
        return None

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= time.time():
            # Expired — clean it up
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        return row["user_id"]
    finally:
        conn.close()


def logout(token: str) -> None:
    """Delete a session by token."""
    if not token:
        return
    conn = get_db()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()
