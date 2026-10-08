"""User persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect
from backend.core.user_model import UserRecord


class UserNotFoundError(LookupError):
    pass


class UserConflictError(ValueError):
    pass


class UserRepository:
    SYSTEM_USER_ID = "system-migration"

    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT NOT NULL PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        password_hash TEXT NULL,
                        google_id TEXT NULL,
                        google_access_token TEXT NULL,
                        google_refresh_token TEXT NULL,
                        profile_picture_url TEXT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        is_admin INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_login_at TIMESTAMP NULL
                    )
                    """
                )
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        email VARCHAR(255) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        password_hash VARCHAR(255) NULL,
                        google_id VARCHAR(255) NULL,
                        google_access_token TEXT NULL,
                        google_refresh_token TEXT NULL,
                        profile_picture_url VARCHAR(512) NULL,
                        is_active TINYINT(1) NOT NULL DEFAULT 1,
                        is_admin TINYINT(1) NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        last_login_at TIMESTAMP NULL,
                        UNIQUE KEY uq_users_email (email),
                        UNIQUE KEY uq_users_google_id (google_id),
                        KEY idx_users_active (is_active)
                    )
                    """
                )
            connection.commit()

            if self.config.uses_sqlite:
                existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()}
                if "google_access_token" not in existing_cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN google_access_token TEXT NULL")
                if "google_refresh_token" not in existing_cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN google_refresh_token TEXT NULL")
                if "is_admin" not in existing_cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
                    cursor.execute("UPDATE users SET is_admin = 1 WHERE email IN ('goru@rezzai.com', 'admin@askmydata.local')")
                connection.commit()
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users' AND COLUMN_NAME = 'google_access_token'
                    """,
                    (self.config.database,),
                )
                if int(cursor.fetchone()[0]) == 0:
                    cursor.execute("ALTER TABLE users ADD COLUMN google_access_token TEXT NULL AFTER google_id")
                    cursor.execute("ALTER TABLE users ADD COLUMN google_refresh_token TEXT NULL AFTER google_access_token")
                    connection.commit()

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users' AND COLUMN_NAME = 'is_admin'
                    """,
                    (self.config.database,),
                )
                if int(cursor.fetchone()[0]) == 0:
                    cursor.execute("ALTER TABLE users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active")
                    cursor.execute("UPDATE users SET is_admin = 1 WHERE email IN ('goru@rezzai.com', 'admin@askmydata.local')")
                    connection.commit()

            cursor.close()
        finally:
            connection.close()
        self._ensure_system_user()

    def _ensure_system_user(self) -> None:
        from backend.core.config import settings
        from backend.core.security import hash_password
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM users WHERE id = %s", (self.SYSTEM_USER_ID,))
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO users (id, email, name, password_hash, google_id, profile_picture_url, is_active, is_admin)
                    VALUES (%s, %s, %s, NULL, NULL, NULL, 1, 0)
                    """,
                    (self.SYSTEM_USER_ID, "system@askmydata.local", "System Migration User"),
                )
            cursor.execute("SELECT 1 FROM users WHERE email = %s", ("goru@rezzai.com",))
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO users (id, email, name, password_hash, google_id, profile_picture_url, is_active, is_admin)
                    VALUES (%s, %s, %s, %s, NULL, NULL, 1, 1)
                    """,
                    ("user-goru", "goru@rezzai.com", "Goru", hash_password("goru5")),
                )
            for admin_email in settings.admin_emails:
                cursor.execute("UPDATE users SET is_admin = 1 WHERE email = %s", (admin_email.lower().strip(),))
            connection.commit()
            cursor.close()
        finally:
            connection.close()


    def migrate_dataset_ownership(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(datasets)").fetchall()}
                if "user_id" not in existing_cols:
                    cursor.execute("ALTER TABLE datasets ADD COLUMN user_id TEXT NULL")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_datasets_user_id ON datasets (user_id)")
                    cursor.execute(
                        """
                        UPDATE datasets
                        SET user_id = ?
                        WHERE user_id IS NULL AND is_builtin = 0
                        """,
                        (self.SYSTEM_USER_ID,),
                    )
                    connection.commit()
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'datasets' AND COLUMN_NAME = 'user_id'
                    """,
                    (self.config.database,),
                )
                if int(cursor.fetchone()[0]) == 0:
                    cursor.execute("ALTER TABLE datasets ADD COLUMN user_id VARCHAR(64) NULL AFTER dataset_id")
                    cursor.execute("CREATE INDEX idx_datasets_user_id ON datasets (user_id)")
                    cursor.execute(
                        """
                        UPDATE datasets
                        SET user_id = %s
                        WHERE user_id IS NULL AND is_builtin = 0
                        """,
                        (self.SYSTEM_USER_ID,),
                    )
                    connection.commit()
            cursor.close()
        finally:
            connection.close()

    def create_user(self, *, email: str, name: str, password_hash: str | None, google_id: str | None = None, profile_picture_url: str | None = None, is_admin: bool = False) -> UserRecord:
        from backend.core.config import settings
        normalized_email = email.lower().strip()
        try:
            self.get_by_email(normalized_email)
        except UserNotFoundError:
            pass
        else:
            raise UserConflictError("A user with this email already exists.")
        user_id = str(uuid4())
        should_be_admin = is_admin or (normalized_email in settings.admin_emails)
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO users (id, email, name, password_hash, google_id, profile_picture_url, is_active, is_admin)
                VALUES (%s, %s, %s, %s, %s, %s, 1, %s)
                """,
                (user_id, normalized_email, name.strip(), password_hash, google_id, profile_picture_url, 1 if should_be_admin else 0),
            )
            connection.commit()
            cursor.close()
        except Exception as error:
            raise UserConflictError("A user with this email already exists.") from error
        return self.get_by_id(user_id)

    def get_by_id(self, user_id: str) -> UserRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise UserNotFoundError(user_id)
            return _row_to_user(row)
        finally:
            connection.close()

    def get_by_email(self, email: str) -> UserRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise UserNotFoundError(email)
            return _row_to_user(row)
        finally:
            connection.close()

    def touch_login(self, user_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                cursor.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
            else:
                cursor.execute("UPDATE users SET last_login_at = UTC_TIMESTAMP() WHERE id = %s", (user_id,))
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def update_google_id(self, user_id: str, google_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("UPDATE users SET google_id = %s WHERE id = %s", (google_id, user_id))
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def update_google_tokens(self, user_id: str, access_token: str | None, refresh_token: str | None) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("UPDATE users SET google_access_token = %s, google_refresh_token = COALESCE(%s, google_refresh_token) WHERE id = %s", (access_token, refresh_token, user_id))
            connection.commit()
            cursor.close()
        finally:
            connection.close()


def _row_to_user(row: Any) -> UserRecord:
    if not isinstance(row, dict):
        row = {key: row[key] for key in row.keys()}
    return UserRecord(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        password_hash=row.get("password_hash"),
        google_id=row.get("google_id"),
        google_access_token=row.get("google_access_token"),
        google_refresh_token=row.get("google_refresh_token"),
        profile_picture_url=row.get("profile_picture_url"),
        is_active=bool(row["is_active"]),
        is_admin=bool(row.get("is_admin", 0)),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_login_at=row.get("last_login_at"),
    )
