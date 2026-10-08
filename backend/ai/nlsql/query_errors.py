class NLQueryError(RuntimeError):
    """Base error for the controlled natural-language SQL pipeline."""


class UnsupportedQuestionError(NLQueryError):
    pass


class QueryPlanValidationError(NLQueryError):
    pass


class SQLValidationError(NLQueryError):
    pass


class QueryExecutionError(NLQueryError):
    pass