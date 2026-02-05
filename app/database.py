"""SQLite database initialisation and connection helpers."""

import sqlite3
from pathlib import Path

from app import config


def init_db() -> None:
    """Create the SQLite database and tables if they don't exist."""
    db_path = config.get().data_dir / "pinotes_lite.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )
        conn.commit()
        print(f"  ℹ  Database initialised: {db_path}")
    finally:
        conn.close()


def get_db() -> sqlite3.Connection:
    """Return a connection to the app database with Row factory enabled."""
    db_path = config.get().data_dir / "pinotes_lite.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
