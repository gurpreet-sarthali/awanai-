"""Normalize CSV column names into safe SQL identifiers."""

from __future__ import annotations

import re
from typing import Iterable

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

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


def _base_name(raw: str) -> str:
    cleaned = _NON_ALNUM.sub("_", raw.strip().lower())
    cleaned = cleaned.strip("_")
    if not cleaned:
        cleaned = "column"
    if cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"
    if cleaned in SQL_RESERVED_WORDS:
        cleaned = f"{cleaned}_col"
    return cleaned[:64]


def normalize_column_names(original_names: Iterable[str]) -> list[tuple[str, str]]:
    """Return (original_name, normalized_name) pairs with unique normalized names."""

    seen: dict[str, int] = {}
    result: list[tuple[str, str]] = []
    for original in original_names:
        base = _base_name(str(original))
        count = seen.get(base, 0)
        normalized = base if count == 0 else f"{base}_{count + 1}"
        seen[base] = count + 1
        result.append((str(original), normalized))
    return result
