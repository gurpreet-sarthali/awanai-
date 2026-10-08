"""Search, catalog metadata, tags, favorites, and history persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, kw_only=True)
class CatalogMetadataRecord:
    dataset_id: str
    description: str | None
    source_type: str
    file_format: str | None
    quality_score: float | None
    version_label: str
    last_analyzed_at: str | None
    updated_by_user_id: str | None
    updated_at: str


class SearchRepository:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                statements = [
                    """CREATE TABLE IF NOT EXISTS dataset_catalog_metadata (
                        dataset_id TEXT PRIMARY KEY,
                        description TEXT NULL,
                        source_type TEXT NOT NULL DEFAULT 'upload',
                        file_format TEXT NULL,
                        quality_score REAL NULL,
                        version_label TEXT NOT NULL DEFAULT 'v1',
                        last_analyzed_at TEXT NULL,
                        updated_by_user_id TEXT NULL,
                        updated_at TEXT NOT NULL
                    )""",
                    """CREATE TABLE IF NOT EXISTS dataset_tags (
                        id TEXT PRIMARY KEY,
                        dataset_id TEXT NOT NULL,
                        tag TEXT NOT NULL,
                        workspace_id TEXT NULL,
                        created_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(dataset_id, tag)
                    )""",
                    """CREATE TABLE IF NOT EXISTS user_favorites (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        resource_id TEXT NOT NULL,
                        workspace_id TEXT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(user_id, resource_type, resource_id)
                    )""",
                    """CREATE TABLE IF NOT EXISTS recent_items (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        resource_id TEXT NOT NULL,
                        workspace_id TEXT NULL,
                        title TEXT NOT NULL,
                        accessed_at TEXT NOT NULL,
                        UNIQUE(user_id, resource_type, resource_id)
                    )""",
                    """CREATE TABLE IF NOT EXISTS search_history (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        workspace_id TEXT NULL,
                        search_query TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )""",
                ]
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_catalog_source ON dataset_catalog_metadata(source_type)",
                    "CREATE INDEX IF NOT EXISTS idx_dataset_tags_dataset ON dataset_tags(dataset_id)",
                    "CREATE INDEX IF NOT EXISTS idx_dataset_tags_tag ON dataset_tags(tag)",
                    "CREATE INDEX IF NOT EXISTS idx_favorites_user ON user_favorites(user_id, resource_type)",
                    "CREATE INDEX IF NOT EXISTS idx_recent_user ON recent_items(user_id, accessed_at)",
                    "CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history(user_id, created_at)",
                ]
            else:
                statements = [
                    """CREATE TABLE IF NOT EXISTS dataset_catalog_metadata (
                        dataset_id VARCHAR(64) PRIMARY KEY,
                        description TEXT NULL,
                        source_type VARCHAR(32) NOT NULL DEFAULT 'upload',
                        file_format VARCHAR(32) NULL,
                        quality_score DOUBLE NULL,
                        version_label VARCHAR(64) NOT NULL DEFAULT 'v1',
                        last_analyzed_at VARCHAR(40) NULL,
                        updated_by_user_id VARCHAR(64) NULL,
                        updated_at VARCHAR(40) NOT NULL,
                        KEY idx_catalog_source (source_type)
                    )""",
                    """CREATE TABLE IF NOT EXISTS dataset_tags (
                        id VARCHAR(64) PRIMARY KEY,
                        dataset_id VARCHAR(64) NOT NULL,
                        tag VARCHAR(64) NOT NULL,
                        workspace_id VARCHAR(64) NULL,
                        created_by_user_id VARCHAR(64) NOT NULL,
                        created_at VARCHAR(40) NOT NULL,
                        UNIQUE KEY uq_dataset_tag (dataset_id, tag),
                        KEY idx_dataset_tags_dataset (dataset_id),
                        KEY idx_dataset_tags_tag (tag)
                    )""",
                    """CREATE TABLE IF NOT EXISTS user_favorites (
                        id VARCHAR(64) PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        resource_type VARCHAR(32) NOT NULL,
                        resource_id VARCHAR(64) NOT NULL,
                        workspace_id VARCHAR(64) NULL,
                        created_at VARCHAR(40) NOT NULL,
                        UNIQUE KEY uq_user_favorite (user_id, resource_type, resource_id),
                        KEY idx_favorites_user (user_id, resource_type)
                    )""",
                    """CREATE TABLE IF NOT EXISTS recent_items (
                        id VARCHAR(64) PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        resource_type VARCHAR(32) NOT NULL,
                        resource_id VARCHAR(64) NOT NULL,
                        workspace_id VARCHAR(64) NULL,
                        title VARCHAR(255) NOT NULL,
                        accessed_at VARCHAR(40) NOT NULL,
                        UNIQUE KEY uq_recent_item (user_id, resource_type, resource_id),
                        KEY idx_recent_user (user_id, accessed_at)
                    )""",
                    """CREATE TABLE IF NOT EXISTS search_history (
                        id VARCHAR(64) PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        workspace_id VARCHAR(64) NULL,
                        search_query VARCHAR(512) NOT NULL,
                        created_at VARCHAR(40) NOT NULL,
                        KEY idx_search_history_user (user_id, created_at)
                    )""",
                ]
                indexes = []
            for statement in statements:
                cursor.execute(statement)
            for statement in indexes:
                cursor.execute(statement)
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def _execute(self, statement: str, params: tuple[Any, ...] = (), *, fetch: str | None = None) -> Any:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(statement, params)
            if fetch == "one":
                row = cursor.fetchone()
                result = self._row_dict(cursor, row) if row else None
            elif fetch == "all":
                result = [self._row_dict(cursor, row) for row in cursor.fetchall()]
            else:
                result = cursor.rowcount
            connection.commit()
            cursor.close()
            return result
        finally:
            connection.close()

    @staticmethod
    def _row_dict(cursor: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return row
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        return dict(zip((item[0] for item in cursor.description), row))

    def get_metadata(self, dataset_id: str) -> CatalogMetadataRecord | None:
        row = self._execute("SELECT * FROM dataset_catalog_metadata WHERE dataset_id=%s", (dataset_id,), fetch="one")
        return self._metadata_from_row(row) if row else None

    def list_metadata(self, dataset_ids: list[str]) -> dict[str, CatalogMetadataRecord]:
        if not dataset_ids:
            return {}
        placeholders = ",".join(["%s"] * len(dataset_ids))
        rows = self._execute(f"SELECT * FROM dataset_catalog_metadata WHERE dataset_id IN ({placeholders})", tuple(dataset_ids), fetch="all")
        return {row["dataset_id"]: self._metadata_from_row(row) for row in rows}

    def upsert_metadata(
        self,
        *,
        dataset_id: str,
        user_id: str,
        description: str | None = None,
        source_type: str | None = None,
        file_format: str | None = None,
        quality_score: float | None = None,
        version_label: str | None = None,
        last_analyzed_at: str | None = None,
    ) -> CatalogMetadataRecord:
        existing = self.get_metadata(dataset_id)
        now = _now()
        payload = {
            "description": description if description is not None else (existing.description if existing else None),
            "source_type": source_type if source_type is not None else (existing.source_type if existing else "upload"),
            "file_format": file_format if file_format is not None else (existing.file_format if existing else None),
            "quality_score": quality_score if quality_score is not None else (existing.quality_score if existing else None),
            "version_label": version_label if version_label is not None else (existing.version_label if existing else "v1"),
            "last_analyzed_at": last_analyzed_at if last_analyzed_at is not None else (existing.last_analyzed_at if existing else None),
        }
        if existing:
            self._execute(
                """UPDATE dataset_catalog_metadata
                SET description=%s, source_type=%s, file_format=%s, quality_score=%s,
                    version_label=%s, last_analyzed_at=%s, updated_by_user_id=%s, updated_at=%s
                WHERE dataset_id=%s""",
                (
                    payload["description"],
                    payload["source_type"],
                    payload["file_format"],
                    payload["quality_score"],
                    payload["version_label"],
                    payload["last_analyzed_at"],
                    user_id,
                    now,
                    dataset_id,
                ),
            )
        else:
            self._execute(
                """INSERT INTO dataset_catalog_metadata
                (dataset_id, description, source_type, file_format, quality_score, version_label, last_analyzed_at, updated_by_user_id, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    dataset_id,
                    payload["description"],
                    payload["source_type"],
                    payload["file_format"],
                    payload["quality_score"],
                    payload["version_label"],
                    payload["last_analyzed_at"],
                    user_id,
                    now,
                ),
            )
        return self.get_metadata(dataset_id)  # type: ignore[return-value]

    def list_tags(self, dataset_ids: list[str]) -> dict[str, list[str]]:
        if not dataset_ids:
            return {}
        placeholders = ",".join(["%s"] * len(dataset_ids))
        rows = self._execute(f"SELECT dataset_id, tag FROM dataset_tags WHERE dataset_id IN ({placeholders}) ORDER BY tag", tuple(dataset_ids), fetch="all")
        tags: dict[str, list[str]] = {dataset_id: [] for dataset_id in dataset_ids}
        for row in rows:
            tags.setdefault(row["dataset_id"], []).append(row["tag"])
        return tags

    def add_tag(self, *, dataset_id: str, tag: str, user_id: str, workspace_id: str | None = None) -> list[str]:
        normalized = tag.strip().lower()
        sql = (
            "INSERT OR IGNORE INTO dataset_tags (id,dataset_id,tag,workspace_id,created_by_user_id,created_at) VALUES (%s,%s,%s,%s,%s,%s)"
            if self.config.uses_sqlite
            else "INSERT IGNORE INTO dataset_tags (id,dataset_id,tag,workspace_id,created_by_user_id,created_at) VALUES (%s,%s,%s,%s,%s,%s)"
        )
        self._execute(sql, (str(uuid4()), dataset_id, normalized, workspace_id, user_id, _now()))
        return self.list_tags([dataset_id]).get(dataset_id, [])

    def remove_tag(self, dataset_id: str, tag: str) -> None:
        self._execute("DELETE FROM dataset_tags WHERE dataset_id=%s AND tag=%s", (dataset_id, tag.strip().lower()))

    def favorite_ids(self, user_id: str, resource_type: str | None = None) -> set[tuple[str, str]]:
        if resource_type:
            rows = self._execute("SELECT resource_type, resource_id FROM user_favorites WHERE user_id=%s AND resource_type=%s", (user_id, resource_type), fetch="all")
        else:
            rows = self._execute("SELECT resource_type, resource_id FROM user_favorites WHERE user_id=%s", (user_id,), fetch="all")
        return {(row["resource_type"], row["resource_id"]) for row in rows}

    def set_favorite(self, *, user_id: str, resource_type: str, resource_id: str, workspace_id: str | None = None) -> None:
        sql = (
            "INSERT OR IGNORE INTO user_favorites (id,user_id,resource_type,resource_id,workspace_id,created_at) VALUES (%s,%s,%s,%s,%s,%s)"
            if self.config.uses_sqlite
            else "INSERT IGNORE INTO user_favorites (id,user_id,resource_type,resource_id,workspace_id,created_at) VALUES (%s,%s,%s,%s,%s,%s)"
        )
        self._execute(sql, (str(uuid4()), user_id, resource_type, resource_id, workspace_id, _now()))

    def remove_favorite(self, *, user_id: str, resource_type: str, resource_id: str) -> None:
        self._execute("DELETE FROM user_favorites WHERE user_id=%s AND resource_type=%s AND resource_id=%s", (user_id, resource_type, resource_id))

    def record_recent(self, *, user_id: str, resource_type: str, resource_id: str, title: str, workspace_id: str | None = None) -> None:
        existing = self._execute(
            "SELECT id FROM recent_items WHERE user_id=%s AND resource_type=%s AND resource_id=%s",
            (user_id, resource_type, resource_id),
            fetch="one",
        )
        now = _now()
        if existing:
            self._execute("UPDATE recent_items SET title=%s, workspace_id=%s, accessed_at=%s WHERE id=%s", (title, workspace_id, now, existing["id"]))
        else:
            self._execute(
                "INSERT INTO recent_items (id,user_id,resource_type,resource_id,workspace_id,title,accessed_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (str(uuid4()), user_id, resource_type, resource_id, workspace_id, title[:255], now),
            )

    def list_recent(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._execute("SELECT * FROM recent_items WHERE user_id=%s ORDER BY accessed_at DESC LIMIT %s", (user_id, limit), fetch="all")

    def record_search(self, *, user_id: str, query: str, workspace_id: str | None = None) -> None:
        normalized = query.strip()
        if not normalized:
            return
        self._execute(
            "INSERT INTO search_history (id,user_id,workspace_id,search_query,created_at) VALUES (%s,%s,%s,%s,%s)",
            (str(uuid4()), user_id, workspace_id, normalized[:512], _now()),
        )

    def list_search_history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._execute("SELECT * FROM search_history WHERE user_id=%s ORDER BY created_at DESC LIMIT %s", (user_id, limit), fetch="all")

    def clear_search_history(self, user_id: str) -> None:
        self._execute("DELETE FROM search_history WHERE user_id=%s", (user_id,))

    @staticmethod
    def _metadata_from_row(row: dict[str, Any]) -> CatalogMetadataRecord:
        return CatalogMetadataRecord(
            dataset_id=row["dataset_id"],
            description=row.get("description"),
            source_type=row.get("source_type") or "upload",
            file_format=row.get("file_format"),
            quality_score=float(row["quality_score"]) if row.get("quality_score") is not None else None,
            version_label=row.get("version_label") or "v1",
            last_analyzed_at=row.get("last_analyzed_at"),
            updated_by_user_id=row.get("updated_by_user_id"),
            updated_at=row.get("updated_at"),
        )
