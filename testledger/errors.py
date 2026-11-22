from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody


class LedgerError(HTTPException):
    def __init__(
        self, status_code: int, code: str, message: str, headers: dict[str, str] | None = None
    ):
        super().__init__(status_code, detail=message, headers=headers)
        self.code = code


def error_response(
    status: int, code: str, message: str, details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        code = exc.code if isinstance(exc, LedgerError) else "http_error"
        return error_response(exc.status_code, code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError):
        details = [
            ErrorDetail(field=".".join(map(str, issue["loc"])), message=issue["msg"])
            for issue in exc.errors()
        ]
        return error_response(422, "validation_error", "Request validation failed.", details)


def documented_errors(*statuses: int) -> dict[int | str, dict[str, Any]]:
    descriptions = {
        401: "Authentication required or invalid credentials",
        403: "Insufficient permissions",
        404: "Resource not found",
        409: "Business rule conflict",
        422: "Invalid request",
        503: "Database unavailable",
    }
    return {
        status: {"model": ErrorResponse, "description": descriptions[status]}
        for status in statuses
    }
