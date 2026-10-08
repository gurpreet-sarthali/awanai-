from backend.ai.nlsql.sql_executor import execute_query
from backend.ai.nlsql.sql_generator import GeneratedQuery
from backend.ai.nlsql.sql_validator import SQLValidationResult


class FakeCursor:
    description = [("value",)]
    def execute(self, sql, parameters=()):
        self.sql = sql
        self.parameters = parameters
    def fetchall(self):
        return [{"value": 1}]
    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.progress_handler = None

    def cursor(self, dictionary=False):
        return FakeCursor()

    def set_progress_handler(self, callback, instruction_interval):
        self.progress_handler = callback
        self.instruction_interval = instruction_interval

    def close(self):
        pass


class FakeRepository:
    config = None


def test_executor_returns_normalized_result(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr("backend.ai.nlsql.sql_executor.connect", lambda config: connection)
    result = execute_query(FakeRepository(), GeneratedQuery("SELECT 1", (), False), SQLValidationResult("SELECT 1", True, False))
    assert result["columns"] == ["value"]
    assert result["row_count"] == 1
    assert result["metadata"]["read_only"] is True
    assert connection.instruction_interval == 1000
    assert connection.progress_handler() == 0


def test_executor_progress_handler_interrupts_after_deadline(monkeypatch):
    import backend.ai.nlsql.sql_executor as executor

    connection = FakeConnection()
    monkeypatch.setattr(executor, "connect", lambda config: connection)
    ticks = iter((0.0, 31.0))
    monkeypatch.setattr(executor.time, "monotonic", lambda: next(ticks))

    execute_query(FakeRepository(), GeneratedQuery("SELECT 1", (), False), SQLValidationResult("SELECT 1", True, False))

    assert connection.progress_handler() == 1