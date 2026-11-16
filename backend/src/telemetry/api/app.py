"""FastAPI application factory.

Run with: uvicorn telemetry.api.app:create_app --factory
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, FastAPI, Request, Response
from psycopg_pool import ConnectionPool, PoolTimeout
from pydantic import BaseModel

from telemetry import __version__, logs
from telemetry.api import problems
from telemetry.config import Settings
from telemetry.domain.health import evaluate_health

API_PREFIX = "/api/v1"

log = logging.getLogger("telemetry.api")


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    dataset_loaded: bool


def _check_database(pool: ConnectionPool, timeout_s: float) -> tuple[bool, bool]:
    """Return (database reachable, dataset loaded)."""
    try:
        with pool.connection(timeout=timeout_s) as conn:
            row = conn.execute("SELECT EXISTS (SELECT 1 FROM dataset)").fetchone()
    except (PoolTimeout, OSError):
        return False, False
    return True, bool(row and row[0])


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    pool = ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=5,
        open=False,
        kwargs={"connect_timeout": max(1, int(settings.db_timeout_s))},
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        pool.open(wait=False)
        try:
            yield
        finally:
            pool.close()

    app = FastAPI(
        title="Pump Skid Telemetry Explorer API",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    problems.install(app)

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response

    router = APIRouter(prefix=API_PREFIX)

    @router.get("/health", tags=["system"])
    def health() -> Health:
        database_ok, dataset_loaded = _check_database(pool, settings.db_timeout_s)
        report = evaluate_health(database_ok=database_ok, dataset_loaded=dataset_loaded)
        return Health(
            status=report.status, database=report.database, dataset_loaded=report.dataset_loaded
        )

    app.include_router(router)
    logs.configure(settings.log_level)
    return app
