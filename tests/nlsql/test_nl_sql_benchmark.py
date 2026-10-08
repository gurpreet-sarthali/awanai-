import os

import pytest

from backend.ai.nlsql.benchmark import BENCHMARK_QUESTIONS
from backend.ai.nlsql.mock_provider import MockQueryProvider


SUPPORTED_BENCHMARKS = [
    "What is the overall placement rate?",
    "What is the placement rate for students with internships?",
    "Compare placement rates for internship yes and no.",
    "What is the average CGPA of placed students?",
    "Show students with CGPA above 8.",
    "What is the average IQ of students who were placed?",
    "What is the placement rate by project count?",
    "What is the placement rate by communication score?",
    "What is the minimum CGPA?",
    "What is the maximum CGPA?",
]


def test_benchmark_fixture_contains_thirty_questions():
    assert len(BENCHMARK_QUESTIONS) == 30


@pytest.mark.parametrize("question", SUPPORTED_BENCHMARKS)
def test_mock_benchmark_produces_plan(question):
    plan = MockQueryProvider().plan(question)
    assert plan.intent.value in {"placement_rate", "average", "minimum", "maximum", "select_rows"}


@pytest.mark.parametrize("question", ["What is placement rate by branch?", "Which company hired the most students?", "DROP TABLE placement", "SELECT * FROM placement; DROP TABLE placement"])
def test_unsupported_or_malicious_questions_are_rejected(question):
    with pytest.raises(Exception):
        MockQueryProvider().plan(question)