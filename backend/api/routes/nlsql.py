from fastapi import APIRouter, Depends

from backend.ai.nlsql.query_errors import NLQueryError
from backend.ai.nlsql.query_manager import QueryManager
from backend.api.dependencies import get_query_manager
from backend.exceptions.handlers import AppError
from backend.schemas.nlsql import NLExecuteResponse, NLPlanRequest, NLQuestionRequest, NLValidateResponse

router = APIRouter(prefix="/nlsql", tags=["natural-language-sql"])


@router.post("/validate", response_model=NLValidateResponse, summary="Plan and validate a mock natural-language query")
def validate(request: NLQuestionRequest, manager: QueryManager = Depends(get_query_manager)) -> NLValidateResponse:
    try:
        plan = manager.plan_question(request.question)
        _, query, validation = manager.prepare(plan, dataset_id=request.dataset_id)
        return NLValidateResponse(question=request.question, plan=plan, sql=query.sql, parameters=list(query.parameters), read_only=validation.read_only, row_query=validation.row_query)
    except NLQueryError as error:
        raise AppError(400, "unsupported_query", str(error)) from error
    except Exception as error:
        raise AppError(503, "nlsql_unavailable", "The natural-language query could not be prepared.") from error


@router.post("/execute", response_model=NLExecuteResponse, summary="Execute an approved internal query plan")
def execute(request: NLPlanRequest, manager: QueryManager = Depends(get_query_manager)) -> NLExecuteResponse:
    try:
        return NLExecuteResponse(**manager.execute_plan(request.plan, dataset_id=request.dataset_id))
    except NLQueryError as error:
        raise AppError(400, "invalid_query_plan", str(error)) from error
    except Exception as error:
        raise AppError(503, "nlsql_unavailable", "The validated query could not be executed.") from error