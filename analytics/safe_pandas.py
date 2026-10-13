"""Run Gemini-authored pandas snippets against a dataframe in a restricted sandbox."""

from __future__ import annotations

import ast
import math
from typing import Any

import numpy as np
import pandas as pd

_ALLOWED_NODES = (
    ast.Module,
    ast.Assign,
    ast.AugAssign,
    ast.Expr,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.BoolOp,
    ast.If,
    ast.IfExp,
    ast.Subscript,
    ast.Slice,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.ListComp,
    ast.DictComp,
    ast.comprehension,
    ast.Call,
    ast.Attribute,
    ast.keyword,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.USub,
    ast.UAdd,
)

_FORBIDDEN_NAMES = {"exec", "eval", "compile", "open", "__import__", "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir", "input", "help"}


class UnsafeAnalyticsScript(ValueError):
    pass


_SAFE_BUILTINS: dict[str, Any] = {
    "float": float,
    "int": int,
    "str": str,
    "bool": bool,
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "abs": abs,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "sorted": sorted,
    "all": all,
    "any": any,
}


def _validate_script(source: str) -> None:
    if not source or not source.strip():
        raise UnsafeAnalyticsScript("Analytics script is empty.")
    if len(source) > 4000:
        raise UnsafeAnalyticsScript("Analytics script is too long.")
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as error:
        raise UnsafeAnalyticsScript(f"Invalid Python syntax: {error}") from error
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise UnsafeAnalyticsScript(f"Disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise UnsafeAnalyticsScript(f"Disallowed name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise UnsafeAnalyticsScript(f"Disallowed attribute access: {node.attr}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_NAMES:
            raise UnsafeAnalyticsScript(f"Disallowed call: {node.func.id}")


def _serialize_result(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value
    if isinstance(value, (np.integer, np.floating)):
        scalar = value.item()
        if isinstance(scalar, float) and (math.isnan(scalar) or math.isinf(scalar)):
            return None
        return scalar
    if isinstance(value, pd.Series):
        if len(value) > 50:
            value = value.head(50)
        return [{"index": str(k), "value": _serialize_result(v)} for k, v in value.items()]
    if isinstance(value, pd.DataFrame):
        limited = value.head(50)
        return limited.replace({np.nan: None}).to_dict(orient="records")
    if isinstance(value, dict):
        return {str(k): _serialize_result(v) for k, v in list(value.items())[:50]}
    if isinstance(value, (list, tuple)):
        return [_serialize_result(v) for v in list(value)[:50]]
    return str(value)


def run_pandas_script(dataframe: pd.DataFrame, script: str) -> dict[str, Any]:
    """Execute script with variables df, pd, np, math; script must assign `result`."""
    _validate_script(script)
    namespace: dict[str, Any] = {
        "df": dataframe.copy(),
        "pd": pd,
        "np": np,
        "math": math,
        "result": None,
    }
    exec(
        compile(script, "<custom_analytics>", "exec"),
        {"__builtins__": _SAFE_BUILTINS},
        namespace,
    )
    raw = namespace.get("result")
    if raw is None:
        raise UnsafeAnalyticsScript("Script must assign a value to variable `result`.")
    return {"result": _serialize_result(raw)}
