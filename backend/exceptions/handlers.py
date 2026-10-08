from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status_code: int, error: str, detail: str) -> None:
        self.status_code = status_code
        self.error = error
        self.detail = detail


async def app_error_handler(request: Request, exception: AppError) -> JSONResponse:
    if request.url.path.startswith("/api/v1/public/"):
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "success": False,
                "error": {"code": exception.error, "message": exception.detail},
                "request_id": getattr(request.state, "request_id", ""),
            },
        )
    return JSONResponse(status_code=exception.status_code, content={"error": exception.error, "detail": exception.detail})


async def validation_error_handler(request: Request, exception: RequestValidationError) -> JSONResponse:
    if request.url.path.startswith("/api/v1/public/"):
        return JSONResponse(status_code=422, content={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed."}, "request_id": getattr(request.state, "request_id", "")})
    return JSONResponse(status_code=422, content={"error": "validation_error", "detail": exception.errors()})


async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
    logger.exception("Unhandled API error", exc_info=exception)
    if request.url.path.startswith("/api/v1/public/"):
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}, "request_id": getattr(request.state, "request_id", "")})
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": "An unexpected internal error occurred."})