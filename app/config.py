"""Centralised runtime configuration with fail-fast validation.

Usage
-----
    from app import config

    # once, at startup:
    settings = config.load()   # prints diagnostics, sys.exit(1) on error

    # anywhere else in the app:
    settings = config.get()    # returns cached Settings; raises if not loaded
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# honour a .env file in the project root (local-dev convenience)
from dotenv import load_dotenv

load_dotenv()  # no-op when .env doesn't exist


# ── public data class ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Settings:
    """Immutable, app-wide settings."""

    vault_dir: Path  # notes vault root (read-only)
    data_dir: Path  # writable dir for SQLite, search index, etc.


# ── module-level singleton ───────────────────────────────────────────────────

_settings: Settings | None = None


def load() -> Settings:
    """Read env vars, validate, cache, and return Settings.

    * Creates DATA_DIR if it doesn't exist (but errors if it can't be created).
    * Prints a clear summary on success; prints errors and calls sys.exit(1) on
      failure — the app should never start with a bad config.
    * Idempotent: returns the cached singleton on subsequent calls.
    """
    global _settings
    if _settings is not None:
        return _settings

    errors: list[str] = []

    # ── VAULT_DIR ────────────────────────────────────────────────────────
    vault_path: Path | None = None
    vault_raw = os.environ.get("VAULT_DIR", "").strip()
    if not vault_raw:
        errors.append(
            "VAULT_DIR is not set. "
            "Set it to the absolute path of your notes vault "
            "(e.g. /home/professor/notes or /vault inside Docker)."
        )
    else:
        vault_path = Path(vault_raw)
        if not vault_path.exists():
            errors.append(
                f"VAULT_DIR={vault_raw} does not exist. "
                "Check your bind mount or path."
            )
        elif not vault_path.is_dir():
            errors.append(f"VAULT_DIR={vault_raw} exists but is not a directory.")

    # ── DATA_DIR ─────────────────────────────────────────────────────────
    data_path: Path | None = None
    data_raw = os.environ.get("DATA_DIR", "").strip()
    if not data_raw:
        errors.append(
            "DATA_DIR is not set. "
            "Set it to a writable path for app data "
            "(e.g. ./data locally or /data inside Docker)."
        )
    else:
        data_path = Path(data_raw)
        if not data_path.exists():
            try:
                data_path.mkdir(parents=True, exist_ok=True)
                print(f"  ℹ  Created DATA_DIR: {data_path}")
            except OSError as exc:
                errors.append(
                    f"DATA_DIR={data_raw} does not exist and could not be created: {exc}"
                )
                data_path = None  # mark as invalid
        if data_path is not None and not data_path.is_dir():
            errors.append(f"DATA_DIR={data_raw} exists but is not a directory.")
            data_path = None

    # ── Abort on any error ───────────────────────────────────────────────
    if errors:
        print("\n❌  PiNotes Lite — configuration error\n", file=sys.stderr)
        for e in errors:
            print(f"     • {e}", file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(1)

    # mypy / runtime: both paths are valid at this point
    assert vault_path is not None and data_path is not None

    _settings = Settings(
        vault_dir=vault_path.resolve(),
        data_dir=data_path.resolve(),
    )

    print("✅  PiNotes Lite — config loaded")
    print(f"     VAULT_DIR = {_settings.vault_dir}")
    print(f"     DATA_DIR  = {_settings.data_dir}")
    return _settings


def get() -> Settings:
    """Return the already-loaded Settings.  Raises if load() hasn't run."""
    if _settings is None:
        raise RuntimeError("Config not initialised — call config.load() at startup.")
    return _settings
