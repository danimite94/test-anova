"""RFC 9457 problem details for every error response (SPEC §6.2)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

PROBLEM_BASE = "https://telemetry.local/problems/"
MEDIA_TYPE = "application/problem+json"

_TYPES = {404: "not-found", 422: "validation-error", 503: "dataset-not-loaded"}

log = logging.getLogger(__name__)


def problem(status: int, title: str, detail: str, **extra: Any) -> JSONResponse:
    body = {
        "type": PROBLEM_BASE + _TYPES.get(status, "internal-error"),
        "title": title,
        "status": status,
        "detail": detail,
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type=MEDIA_TYPE)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    title = "Not found" if exc.status_code == 404 else "Request failed"
    return problem(exc.status_code, title, str(exc.detail))


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = [
        {"param": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()
    ]
    return problem(422, "Invalid request parameters", errors[0]["message"], errors=errors)


async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error", exc_info=exc)
    return problem(500, "Internal error", "An unexpected error occurred; see server logs.")


def install(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unexpected_error)
