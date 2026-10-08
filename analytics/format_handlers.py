"""Multi-format parsing and validation for CSV, TSV, XLSX, JSON, and Parquet datasets."""

from __future__ import annotations

import io
import json
import re
from typing import Any

import pandas as pd


class DataFormatError(ValueError):
    """Raised when data cannot be parsed or violates format constraints."""
    pass


SUPPORTED_FORMATS = {
    "csv": {"name": "CSV", "mime_types": ["text/csv", "application/csv", "text/plain"], "extensions": [".csv"]},
    "tsv": {"name": "TSV", "mime_types": ["text/tab-separated-values", "text/tsv"], "extensions": [".tsv", ".tab"]},
    "xlsx": {"name": "Excel (XLSX)", "mime_types": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"], "extensions": [".xlsx", ".xls"]},
    "json": {"name": "JSON", "mime_types": ["application/json", "text/json"], "extensions": [".json"]},
    "parquet": {"name": "Parquet", "mime_types": ["application/vnd.apache.parquet", "application/x-parquet", "application/octet-stream"], "extensions": [".parquet", ".pq"]},
}


def detect_file_format(filename: str, content: bytes) -> str:
    """Detect format from file extension and header/magic bytes."""
    lower_name = (filename or "").lower()
    
    # Check magic bytes first
    if content.startswith(b"PAR1"):
        return "parquet"
    if content.startswith(b"PK\x03\x04") and (lower_name.endswith(".xlsx") or lower_name.endswith(".xls")):
        return "xlsx"
    if content.startswith(b"{") or content.startswith(b"["):
        return "json"
    
    # Extension checks
    if lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
        return "xlsx"
    if lower_name.endswith(".json"):
        return "json"
    if lower_name.endswith(".parquet") or lower_name.endswith(".pq"):
        return "parquet"
    if lower_name.endswith(".tsv") or lower_name.endswith(".tab"):
        return "tsv"
    if lower_name.endswith(".csv"):
        return "csv"
    
    # Try decoding a snippet as text to inspect structure
    try:
        sample = content[:4096].decode("utf-8", errors="ignore").strip()
        if sample.startswith("{") or sample.startswith("["):
            return "json"
        if "\t" in sample and "\n" in sample and sample.count("\t") > sample.count(","):
            return "tsv"
        if "," in sample and "\n" in sample:
            return "csv"
    except Exception:
        pass
        
    return "csv"


def parse_dataset_bytes(
    content: bytes,
    filename: str,
    format_type: str | None = None,
    max_rows: int | None = None,
    max_columns: int | None = None,
) -> pd.DataFrame:
    """Parse byte content into a Pandas DataFrame based on detected or specified format."""
    if not content or not content.strip():
        raise DataFormatError("The uploaded file is empty.")
    
    detected_format = format_type or detect_file_format(filename, content)
    
    try:
        if detected_format == "csv":
            df = _read_csv(content)
        elif detected_format == "tsv":
            df = _read_tsv(content)
        elif detected_format == "xlsx":
            df = _read_excel(content)
        elif detected_format == "json":
            df = _read_json(content)
        elif detected_format == "parquet":
            df = _read_parquet(content)
        else:
            raise DataFormatError(f"Unsupported format '{detected_format}'. Supported formats are: CSV, TSV, XLSX, JSON, Parquet.")
    except DataFormatError:
        raise
    except Exception as error:
        raise DataFormatError(f"Failed to parse {detected_format.upper()} file: {error}") from error

    if df.shape[1] == 0:
        raise DataFormatError("The dataset contains no columns.")
    if df.shape[0] == 0:
        raise DataFormatError("The dataset contains no rows.")

    # Deduplicate column names if necessary by appending suffix
    df.columns = _ensure_unique_headers(df.columns)

    if max_rows and len(df) > max_rows:
        raise DataFormatError(f"Dataset exceeds the maximum allowed row count of {max_rows} (found {len(df)} rows).")
    if max_columns and len(df.columns) > max_columns:
        raise DataFormatError(f"Dataset exceeds the maximum allowed column count of {max_columns} (found {len(df.columns)} columns).")

    return df


def _read_csv(content: bytes) -> pd.DataFrame:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError as err:
            raise DataFormatError("Could not decode CSV text using UTF-8 or Latin-1.") from err
            
    buffer = io.StringIO(text)
    try:
        return pd.read_csv(buffer, sep=None, engine="python")
    except Exception as err:
        buffer.seek(0)
        try:
            return pd.read_csv(buffer, sep=",")
        except Exception:
            raise DataFormatError("The file is not a valid CSV.") from err


def _read_tsv(content: bytes) -> pd.DataFrame:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    buffer = io.StringIO(text)
    try:
        return pd.read_csv(buffer, sep="\t")
    except Exception as err:
        raise DataFormatError("The file is not a valid TSV.") from err


def _read_excel(content: bytes) -> pd.DataFrame:
    buffer = io.BytesIO(content)
    try:
        # Read the first sheet
        return pd.read_excel(buffer, engine="openpyxl")
    except Exception as err:
        raise DataFormatError("The file is not a readable Excel (.xlsx) workbook.") from err


def _read_json(content: bytes) -> pd.DataFrame:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as err:
        raise DataFormatError("Invalid JSON structure.") from err
        
    if isinstance(parsed, list):
        if not parsed:
            raise DataFormatError("JSON array is empty.")
        if all(isinstance(item, dict) for item in parsed):
            return pd.DataFrame(parsed)
        raise DataFormatError("JSON must be an array of key-value objects or an object containing record arrays.")
    elif isinstance(parsed, dict):
        # Look for typical nested record lists (e.g. {"data": [...]}, {"records": [...]}, {"rows": [...]})
        for key in ("data", "records", "rows", "items", "results"):
            if key in parsed and isinstance(parsed[key], list) and parsed[key] and isinstance(parsed[key][0], dict):
                return pd.DataFrame(parsed[key])
        try:
            return pd.DataFrame(parsed)
        except Exception:
            try:
                return pd.json_normalize(parsed)
            except Exception as err:
                raise DataFormatError("Could not convert JSON object to tabular dataset.") from err
    else:
        raise DataFormatError("Root JSON structure must be an array of records or an object.")


def _read_parquet(content: bytes) -> pd.DataFrame:
    buffer = io.BytesIO(content)
    try:
        return pd.read_parquet(buffer, engine="pyarrow")
    except Exception as err:
        raise DataFormatError("The file is not a valid Parquet dataset.") from err


def _ensure_unique_headers(headers: Any) -> list[str]:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for raw in headers:
        name = str(raw).strip() or "unnamed_column"
        if name in seen:
            seen[name] += 1
            unique.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            unique.append(name)
    return unique
