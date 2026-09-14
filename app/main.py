"""Today AI Module 1 — Input Layer HTTP app."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.input import router as input_router
from app.core.security import (
    AccessLogMiddleware,
    AppError,
    BodySizeLimitMiddleware,
    JsonOnlyMiddleware,
    error_body,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("today_ai")

app = FastAPI(
    title="Today AI",
) 
app.include_router(input_router)

# Last added runs first. Access log is outermost so 413/415 are logged.
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(JsonOnlyMiddleware)
app.add_middleware(AccessLogMiddleware)


def _safe_validation_message(exc: RequestValidationError) -> str:
    try:
        errors = exc.errors()
    except Exception:
        return "Invalid request."
    if not errors:
        return "Invalid request."
    first = errors[0]
    loc = first.get("loc") or ()
    msg = first.get("msg") or "Invalid request."
    err_type = first.get("type") or ""

    if "json" in err_type or err_type == "json_invalid":
        return "Malformed JSON."
    if err_type == "missing":
        field = loc[-1] if loc else "field"
        if field in {"content", "input_type"}:
            return f"Missing {field}."
        return "Missing required field."
    if err_type == "extra_forbidden":
        return "Extra fields are not allowed."
    if "Unknown input_type" in str(msg):
        return "Unknown input_type."
    if err_type in {"string_type", "int_type", "bool_type", "float_type", "list_type", "dict_type"}:
        return "Invalid field type."
    text = str(msg)
    if "Traceback" in text or 'File "' in text:
        return "Invalid request."
    return "Invalid request."


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content=error_body(exc.error, exc.message, exc.status),
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", _safe_validation_message(exc), 422),
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(
    _request: Request, exc: ValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", "Invalid request.", 422),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    message = "Request could not be completed."
    if exc.status_code == 404:
        message = "Not found."
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body("http_error", message, exc.status_code),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.info(
        "%s %s %s %s",
        request.method,
        request.url.path,
        500,
        getattr(request.state, "request_id", "-"),
    )
    return JSONResponse(
        status_code=500,
        content=error_body(
            "internal_error",
            "An unexpected error occurred.",
            500,
        ),
    )
