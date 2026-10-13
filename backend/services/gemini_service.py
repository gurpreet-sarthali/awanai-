"""Gemini planner/explainer service — Phase 12.

Architecture:
  1. plan()    → Gemini understands the question, returns an AnalyticsPlan (structured JSON)
  2. validate_plan() → backend validates the plan (allowlist, column checks)
  3. analytics_service.run_operation() → MySQL/Pandas computes the actual numbers
  4. explain() → Gemini narrates the verified result (cannot invent numbers)

Gemini NEVER executes SQL, Python, or shell commands.
Gemini NEVER sets numerical results — it only reads them back.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.schemas.ai import AnalyticsPlan, ExplanationPayload
from backend.services.analytics_service import ALLOWED_OPERATIONS

logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).resolve().parents[1] / "ai" / "prompts"
SUPPORTED_CHARTS = {"bar", "line", "pie", "histogram", "scatter", "box"}

# ── Placement-specific columns that Gemini may reference for allowed_values ──
_PLACEMENT_CATEGORICAL = {"Placement", "Internship_Experience", "Communication_Skills"}


class AIConfigurationError(RuntimeError):
    pass


class AIServiceError(RuntimeError):
    pass


class UnsupportedQuestionError(RuntimeError):
    pass


# Valid Gemini model names to try in order (most capable to fallback)
# gemini-flash-lite-latest and gemini-3.1-flash-lite confirmed working on free tier
_GEMINI_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
]


class GeminiService:
    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        chosen_model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self.model = chosen_model
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.api_key or self.api_key in ("YOUR_GEMINI_API_KEY_HERE", "your_api_key_here", "your_gemini_api_key_here"):
                raise AIConfigurationError(
                    "GEMINI_API_KEY is not configured. "
                    "Set it in your .env file. "
                    "Get a free key at https://aistudio.google.com/app/apikey"
                )
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def plan(self, question: str, schema_context: dict[str, Any]) -> AnalyticsPlan:
        """Convert a natural-language question into a validated AnalyticsPlan."""
        if not question.strip():
            raise UnsupportedQuestionError("Please enter a question about the dataset.")
        prompt = self._read_prompt("analytics_planner.txt").format(
            schema_context=json.dumps(schema_context, sort_keys=True),
            operations=", ".join(sorted(ALLOWED_OPERATIONS)),
            chart_types=", ".join(sorted(SUPPORTED_CHARTS)),
            question=question.strip(),
        )
        raw = self._generate_json(prompt, AnalyticsPlan)
        try:
            plan = AnalyticsPlan.model_validate(raw)
        except ValidationError as error:
            logger.warning("gemini_invalid_plan raw=%s", raw)
            raise AIServiceError("Gemini returned an invalid analytics plan.") from error
        self.validate_plan(plan, schema_context)
        return plan

    def general_answer(self, question: str) -> ExplanationPayload:
        """Answer general knowledge / math questions without running dataset analytics."""
        prompt = self._read_prompt("general_answer.txt").format(question=question.strip())
        raw = self._generate_json(prompt, ExplanationPayload, temperature=0.4)
        try:
            return ExplanationPayload.model_validate(raw)
        except ValidationError as error:
            logger.warning("gemini_invalid_general_answer raw=%s", raw)
            raise AIServiceError("Gemini returned an invalid answer.") from error

    def explain(self, question: str, operation: str, result: Any, warnings: list[str]) -> ExplanationPayload:
        """Generate a natural-language explanation for a verified analytics result."""
        prompt = self._read_prompt("result_explainer.txt").format(
            question=question,
            operation=operation,
            result=json.dumps(result, default=str, sort_keys=True),
            warnings=json.dumps(warnings),
        )
        raw = self._generate_json(prompt, ExplanationPayload)
        try:
            return ExplanationPayload.model_validate(raw)
        except ValidationError as error:
            logger.warning("gemini_invalid_explanation raw=%s", raw)
            raise AIServiceError("Gemini returned an invalid explanation.") from error

    def validate_plan(self, plan: AnalyticsPlan, schema_context: dict[str, Any]) -> None:
        """Validate that the Gemini-generated plan only uses allowed operations and columns.

        Raises UnsupportedQuestionError for:
        - unsupported intent ('unsupported')
        - operations not in the approved allowlist
        - chart types not in the approved set
        - filters referencing columns not present in the dataset
        - NOTE: We no longer blanket-reject filters — we validate each one against schema
        """
        if plan.answer_mode == "general":
            if plan.operation != "general_answer":
                raise UnsupportedQuestionError(
                    "General questions must use operation 'general_answer'."
                )
            return
        if plan.operation == "custom_analytics":
            if not plan.pandas_script or not plan.pandas_script.strip():
                raise UnsupportedQuestionError(
                    "Custom analytics requires a pandas_script that assigns `result`."
                )
            from analytics.safe_pandas import UnsafeAnalyticsScript, _validate_script

            try:
                _validate_script(plan.pandas_script)
            except UnsafeAnalyticsScript as error:
                raise UnsupportedQuestionError(str(error)) from error
        if plan.intent == "unsupported":
            raise UnsupportedQuestionError(
                "This question cannot be answered using the current dataset and approved analytics."
            )
        if plan.operation not in ALLOWED_OPERATIONS:
            raise UnsupportedQuestionError(
                f"The operation '{plan.operation}' is not in the approved analytics registry."
            )
        if plan.chart_type and plan.chart_type not in SUPPORTED_CHARTS:
            raise UnsupportedQuestionError(
                f"The chart type '{plan.chart_type}' is not supported."
            )
        columns = set(schema_context.get("columns", []))
        invalid_filters = [item.field for item in plan.filters if item.field not in columns]
        if invalid_filters:
            raise UnsupportedQuestionError(
                f"The current dataset does not contain the requested column(s): {', '.join(invalid_filters)}."
            )

    @staticmethod
    def _clean_schema(schema: type[Any]) -> dict[str, Any]:
        """Convert a Pydantic model to a Gemini-compatible JSON schema.

        Gemini's response_schema does not accept:
        - additionalProperties (raises 400 Bad Request)
        - title fields (raises 400 Bad Request)
        We strip these recursively before sending.
        """
        raw: dict[str, Any] = schema.model_json_schema()

        def _strip(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: _strip(v)
                    for k, v in obj.items()
                    if k not in ("additionalProperties", "title")
                }
            if isinstance(obj, list):
                return [_strip(item) for item in obj]
            return obj

        return _strip(raw)

    def _generate_json(self, prompt: str, schema: type[Any], *, temperature: float = 0.1) -> dict[str, Any]:
        started = time.perf_counter()
        clean_schema = self._clean_schema(schema)

        models_to_try = [self.model]
        for candidate in _GEMINI_FALLBACK_MODELS:
            if candidate not in models_to_try:
                models_to_try.append(candidate)

        last_error = None
        for attempt_model in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=attempt_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=clean_schema,
                        temperature=temperature,
                    ),
                )
                text = getattr(response, "text", None)
                if not text:
                    continue
                value = json.loads(text)
                if isinstance(value, dict):
                    logger.info(
                        "gemini_request_success model=%s duration_ms=%.2f",
                        attempt_model,
                        (time.perf_counter() - started) * 1000,
                    )
                    return value
            except Exception as error:
                last_error = error
                logger.warning(
                    "gemini_request_retry model=%s error=%s (%s), trying next available model...",
                    attempt_model,
                    type(error).__name__,
                    error,
                )
                time.sleep(0.5)

        logger.error("All Gemini candidate models failed. Last error: %s", last_error)
        raise AIServiceError("AI service is temporarily unavailable. Please try again.") from last_error

    @staticmethod
    def _read_prompt(name: str) -> str:
        return (PROMPT_DIR / name).read_text(encoding="utf-8")


def schema_context_from_dataframe(dataframe: Any, dataset_name: str = "") -> dict[str, Any]:
    """Build a schema context dict from a Pandas DataFrame for the Gemini planner prompt.

    Works for both the demo placement dataset and arbitrary uploaded datasets.
    """
    try:
        columns = list(dataframe.columns)
    except Exception:
        from analytics.loader import EXPECTED_COLUMNS, PLACEMENT_TABLE
        return {"table": PLACEMENT_TABLE, "columns": EXPECTED_COLUMNS, "types": {}, "allowed_values": {}, "row_count": 0}

    context: dict[str, Any] = {
        "dataset_name": dataset_name or "uploaded_dataset",
        "columns": columns,
        "types": {},
        "allowed_values": {},
        "row_count": int(len(dataframe)),
        "sample_values": {},
    }

    for column in columns:
        try:
            context["types"][column] = str(dataframe[column].dtype)
        except Exception:
            context["types"][column] = "unknown"

    # For categorical columns, include distinct values (capped at 20)
    for column in columns:
        try:
            if str(dataframe[column].dtype) in ("object", "bool", "category"):
                distinct = sorted(str(v) for v in dataframe[column].dropna().unique())
                if len(distinct) <= 20:
                    context["allowed_values"][column] = distinct
                    context["sample_values"][column] = distinct[:5]
        except Exception:
            pass

    # For numeric columns include min/max/mean for context
    numeric_summary: dict[str, Any] = {}
    for column in columns:
        try:
            if str(dataframe[column].dtype).startswith(("int", "float")):
                col_data = dataframe[column].dropna()
                if len(col_data) > 0:
                    numeric_summary[column] = {
                        "min": round(float(col_data.min()), 4),
                        "max": round(float(col_data.max()), 4),
                        "mean": round(float(col_data.mean()), 4),
                    }
        except Exception:
            pass
    if numeric_summary:
        context["numeric_summary"] = numeric_summary

    try:
        import numpy as np
        context["sample_records"] = dataframe.head(4).replace({np.nan: None}).to_dict(orient="records")
    except Exception:
        pass

    return context