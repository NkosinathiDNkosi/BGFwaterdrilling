"""Shared SQLite configuration and schema migrations for both Flask apps."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def _database_path() -> Path:
    """Resolve DATABASE_PATH or use a safe local default."""
    configured = os.getenv("DATABASE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()

    production = (
        os.getenv("APP_ENV", "").lower() == "production"
        or os.getenv("FLASK_ENV", "").lower() == "production"
    )
    if production:
        raise RuntimeError(
            "DATABASE_PATH must be explicitly configured in production and must "
            "point to persistent storage that survives application restarts."
        )
    return PROJECT_DIR / "instance" / "bwd_enquiries.db"


DATABASE_PATH = _database_path()


def get_db_connection() -> sqlite3.Connection:
    """Create a configured connection to the one shared application database."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def validate_admin_credentials(username: str, password: str) -> None:
    """Enforce reasonable bootstrap and password-rotation requirements."""
    if len(username.strip()) < 3 or len(username) > 80:
        raise ValueError("Administrator usernames must be 3–80 characters long.")
    if len(password) < 14:
        raise ValueError("Administrator passwords must contain at least 14 characters.")
    if username and username.casefold() in password.casefold():
        raise ValueError("The administrator password must not contain the username.")
    if password.strip().lower() in {
        "admin@123",
        "password123456",
        "change me now!",
        "changemechangeme",
        "12345678901234",
        "qwertyuiopasdf",
    }:
        raise ValueError("Choose a unique administrator password, not a common/starter password.")
    character_classes = sum((
        any(char.islower() for char in password),
        any(char.isupper() for char in password),
        any(char.isdigit() for char in password),
        any(not char.isalnum() and not char.isspace() for char in password),
    ))
    # Long multi-word passphrases are also acceptable without artificial symbol rules.
    if character_classes < 3 and len(password) < 20:
        raise ValueError(
            "Use at least three character types, or a unique passphrase of 20+ characters."
        )


def init_database() -> None:
    """Create/update the schema safely and remove the legacy all-date unique index.

    Pending requests may share a requested date. Only active confirmed appointments
    participate in the unique date index, so cancellation or trashing releases it.
    """
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = get_db_connection()
    try:
        # WAL improves concurrent read performance on a local persistent SQLite disk.
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("BEGIN IMMEDIATE")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS enquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                location TEXT NOT NULL,
                preferred_drilling_date TEXT,
                service TEXT NOT NULL,
                message TEXT,
                status TEXT NOT NULL DEFAULT 'New',
                created_at TEXT NOT NULL,
                appointment_status TEXT NOT NULL DEFAULT 'Pending Request',
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        columns = _column_names(connection, "enquiries")
        if "preferred_drilling_date" not in columns:
            connection.execute(
                "ALTER TABLE enquiries ADD COLUMN preferred_drilling_date TEXT"
            )
        if "is_deleted" not in columns:
            connection.execute(
                "ALTER TABLE enquiries ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"
            )
        appointment_status_was_added = "appointment_status" not in columns
        if appointment_status_was_added:
            connection.execute(
                "ALTER TABLE enquiries ADD COLUMN appointment_status "
                "TEXT NOT NULL DEFAULT 'Pending Request'"
            )
            # One-time migration: preserve legacy scheduled/cancelled intent, but do
            # not re-run this mapping on every boot after an administrator changes it.
            connection.execute(
                """
                UPDATE enquiries SET appointment_status = 'Confirmed'
                WHERE status = 'Scheduled' AND preferred_drilling_date IS NOT NULL
                """
            )
            connection.execute(
                """
                UPDATE enquiries SET appointment_status = 'Cancelled'
                WHERE status = 'Cancelled'
                """
            )
            connection.execute(
                """
                UPDATE enquiries SET appointment_status = 'Completed'
                WHERE status = 'Completed'
                """
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_changed_at TEXT
            )
            """
        )
        admin_columns = _column_names(connection, "admins")
        if "password_changed_at" not in admin_columns:
            connection.execute("ALTER TABLE admins ADD COLUMN password_changed_at TEXT")

        # Remove the old constraint that blocked every request on a date forever.
        connection.execute("DROP INDEX IF EXISTS unique_enquiry_drilling_date")
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS unique_confirmed_appointment_date
            ON enquiries(preferred_drilling_date)
            WHERE preferred_drilling_date IS NOT NULL
              AND appointment_status = 'Confirmed'
              AND is_deleted = 0
            """
        )

        existing_admin_count = connection.execute(
            "SELECT COUNT(*) FROM admins"
        ).fetchone()[0]
        if existing_admin_count == 0:
            username = os.getenv("ADMIN_USERNAME", "").strip()
            password = os.getenv("ADMIN_PASSWORD", "")
            if username or password:
                if not username or not password:
                    raise RuntimeError(
                        "For first-time administrator setup, configure both "
                        "ADMIN_USERNAME and ADMIN_PASSWORD; otherwise leave both "
                        "unset and run manage_admin.py set-password."
                    )
                try:
                    validate_admin_credentials(username, password)
                except ValueError as exc:
                    raise RuntimeError(f"Invalid administrator bootstrap credentials: {exc}") from exc
                from werkzeug.security import generate_password_hash

                connection.execute(
                    "INSERT INTO admins (username, password_hash, password_changed_at) "
                    "VALUES (?, ?, datetime('now'))",
                    (username, generate_password_hash(password)),
                )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_admin_password(username: str, password: str) -> bool:
    """Create an administrator if missing, or deliberately rotate the password."""
    username = username.strip()
    validate_admin_credentials(username, password)
    from werkzeug.security import generate_password_hash

    connection = get_db_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT id FROM admins WHERE username = ?", (username,)
        ).fetchone()
        hashed = generate_password_hash(password)
        if existing:
            connection.execute(
                "UPDATE admins SET password_hash = ?, password_changed_at = datetime('now') "
                "WHERE username = ?",
                (hashed, username),
            )
            created = False
        else:
            connection.execute(
                "INSERT INTO admins (username, password_hash, password_changed_at) "
                "VALUES (?, ?, datetime('now'))",
                (username, hashed),
            )
            created = True
        connection.commit()
        return created
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
