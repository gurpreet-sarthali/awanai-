"""Identifiers and validation rules for managed datasets."""

from __future__ import annotations

import re

DEMO_PLACEMENT_DATASET_ID = "demo-placement"
DEMO_PLACEMENT_NAME = "Demo Placement Dataset"
DEMO_PLACEMENT_TABLE = "placement"

DATASET_ID_PATTERN = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
BUILTIN_DATASET_IDS = frozenset({DEMO_PLACEMENT_DATASET_ID})
INTERNAL_TABLE_PATTERN = re.compile(r"^ds_[a-f0-9]{12}$")

DATASET_STATUSES = frozenset(
    {
        "UPLOADING",
        "VALIDATING",
        "PROCESSING",
        "READY",
        "FAILED",
        "DELETING",
        "DELETED",
    }
)

SQL_RESERVED_WORDS = frozenset(
    {
        "select",
        "from",
        "where",
        "table",
        "database",
        "index",
        "key",
        "order",
        "group",
        "by",
        "join",
        "insert",
        "update",
        "delete",
        "drop",
        "create",
        "alter",
        "limit",
        "values",
        "null",
        "primary",
        "foreign",
        "constraint",
    }
)


def is_valid_dataset_id(dataset_id: str) -> bool:
    if dataset_id in BUILTIN_DATASET_IDS:
        return True
    return bool(DATASET_ID_PATTERN.match(dataset_id))


def is_safe_internal_table_name(table_name: str) -> bool:
    if table_name == DEMO_PLACEMENT_TABLE:
        return True
    return bool(INTERNAL_TABLE_PATTERN.match(table_name))
