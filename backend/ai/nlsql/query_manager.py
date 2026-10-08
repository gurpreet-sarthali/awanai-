from __future__ import annotations

from typing import Any

from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from backend.repositories.database_repository import DatabaseRepository
from backend.core.config import settings

from backend.services.dataset_access_service import DatasetAccessService

from .intent_schema import QueryPlan
from .mock_provider import MockQueryProvider
from .schema_context import SchemaContext, load_schema_context
from .sql_executor import execute_query
from .sql_generator import GeneratedQuery, generate_sql
from .sql_validator import SQLValidationResult, validate_sql


class QueryManager:
    """Provider-independent pipeline: plan, validate, generate, validate, execute."""

    def __init__(self, repository: DatabaseRepository, provider: Any | None = None, dataset_access: DatasetAccessService | None = None) -> None:
        self.repository = repository
        self.provider = provider or MockQueryProvider()
        self.dataset_access = dataset_access

    def _ensure_dataset_access(self, dataset_id: str) -> None:
        if self.dataset_access is not None:
            self.dataset_access.can_use_for_analytics(dataset_id)

    def schema(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> SchemaContext:
        return load_schema_context(self.repository, dataset_id)

    def plan_question(self, question: str) -> QueryPlan:
        return self.provider.plan(question)

    def prepare(self, plan: QueryPlan, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> tuple[SchemaContext, GeneratedQuery, SQLValidationResult]:
        self._ensure_dataset_access(dataset_id)
        schema = self.schema(dataset_id)
        query = generate_sql(plan, schema)
        validation = validate_sql(query.sql, schema, row_query=query.row_query, max_query_length=settings.max_query_length, max_result_rows=settings.max_result_rows)
        return schema, query, validation

    def execute_plan(self, plan: QueryPlan, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, Any]:
        _, query, validation = self.prepare(plan, dataset_id)
        return execute_query(self.repository, query, validation)

    def execute_question(self, question: str, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, Any]:
        plan = self.plan_question(question)
        result = self.execute_plan(plan, dataset_id)
        result["metadata"]["plan"] = plan.model_dump(mode="json")
        result["metadata"]["provider"] = "MOCK / TEST PROVIDER"
        result["metadata"]["dataset_id"] = dataset_id
        return result
