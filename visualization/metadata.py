"""Chart metadata and output-path helpers."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from typing import Any


def output_path(output_dir: str | Path, filename: str | None, chart_type: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = filename or f"{chart_type}_{uuid4().hex[:10]}.png"
    if not safe_name.lower().endswith(".png"):
        safe_name += ".png"
    path = directory / safe_name
    if filename and path.exists():
        path = directory / f"{path.stem}_{uuid4().hex[:8]}{path.suffix}"
    return path


def success_metadata(
    *, chart_type: str, path: Path, title: str, row_count: int, x_column: str | None = None,
    y_column: str | None = None, warnings: list[str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": True,
        "chart_type": chart_type,
        "file_path": str(path),
        "title": title,
        "row_count": row_count,
        "warnings": warnings or [],
    }
    if x_column is not None:
        result["x_column"] = x_column
    if y_column is not None:
        result["y_column"] = y_column
    return result


def failure_metadata(chart_type: str, errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    return {"success": False, "chart_type": chart_type, "errors": errors, "warnings": warnings or []}