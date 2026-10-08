"""Deterministic MOCK / TEST provider used without Gemini."""

from __future__ import annotations

import re

from .intent_schema import FilterOperator, QueryFilter, QueryIntent, QueryPlan, SortSpec
from .query_errors import UnsupportedQuestionError


class MockQueryProvider:
    """Maps only the Phase 8 benchmark language to approved query plans."""

    def plan(self, question: str) -> QueryPlan:
        text = " ".join(question.lower().strip().split())
        if "drop table" in text or "delete from" in text or "update placement" in text or "insert into" in text or "truncate" in text or "alter table" in text or ";" in text or "--" in text:
            raise UnsupportedQuestionError("Unsafe or destructive requests are not supported.")
        if "branch" in text or "company" in text:
            raise UnsupportedQuestionError("The current dataset does not contain the required information.")
        if "overall placement rate" in text:
            return QueryPlan(intent=QueryIntent.PLACEMENT_RATE)
        if "placement rate" in text and "internship" in text:
            return QueryPlan(intent=QueryIntent.PLACEMENT_RATE, group_by="Internship_Experience")
        if "placement rate" in text and ("cgpa group" in text or "cgpa range" in text):
            return QueryPlan(intent=QueryIntent.PLACEMENT_RATE, group_by="CGPA")
        if "placement rate" in text and ("project" in text or "projects" in text):
            return QueryPlan(intent=QueryIntent.PLACEMENT_RATE, group_by="Projects_Completed")
        if "placement rate" in text and "communication" in text:
            return QueryPlan(intent=QueryIntent.PLACEMENT_RATE, group_by="Communication_Skills")
        if "average" in text and "cgpa" in text:
            return QueryPlan(intent=QueryIntent.AVERAGE, metric_column="CGPA", filters=self._placement_filter(text))
        if "average" in text and "iq" in text:
            return QueryPlan(intent=QueryIntent.AVERAGE, metric_column="IQ", filters=self._placement_filter(text))
        if "average" in text and "project" in text:
            return QueryPlan(intent=QueryIntent.AVERAGE, metric_column="Projects_Completed", filters=self._placement_filter(text))
        if "minimum" in text and "cgpa" in text:
            return QueryPlan(intent=QueryIntent.MINIMUM, metric_column="CGPA")
        if "maximum" in text and "cgpa" in text:
            return QueryPlan(intent=QueryIntent.MAXIMUM, metric_column="CGPA")
        if "students with cgpa above" in text or "students with cgpa over" in text:
            match = re.search(r"(?:above|over)\s+(\d+(?:\.\d+)?)", text)
            if match:
                return QueryPlan(intent=QueryIntent.SELECT, select_columns=["College_ID", "CGPA", "Placement"], filters=[QueryFilter(column="CGPA", operator=FilterOperator.GREATER, value=float(match.group(1)))], limit=100)
        if "how many" in text or "count" in text or "number of students" in text:
            return QueryPlan(intent=QueryIntent.COUNT, filters=self._placement_filter(text))
        raise UnsupportedQuestionError("The mock provider supports only the predefined Phase 8 benchmark questions.")

    @staticmethod
    def _placement_filter(text: str) -> list[QueryFilter]:
        if "placed" in text and "not placed" not in text:
            return [QueryFilter(column="Placement", operator=FilterOperator.EQUAL, value="Yes")]
        if "non-placed" in text or "not placed" in text:
            return [QueryFilter(column="Placement", operator=FilterOperator.EQUAL, value="No")]
        return []