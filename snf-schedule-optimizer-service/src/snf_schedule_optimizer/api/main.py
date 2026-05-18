import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

import structlog.contextvars
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from hypercorn import Config
from hypercorn.asyncio import serve
from hypercorn.typing import ASGIFramework
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.responses import Response

from snf_schedule_optimizer.api.grpc.scheduler_handler import SchedulingServiceHandler
from snf_schedule_optimizer.api.health import router as health_router
from snf_schedule_optimizer.generated.scheduling.v1.scheduling_connect import (
    SchedulingServiceASGIApplication,
)
from snf_schedule_optimizer.infrastructure.composition import build_infra_container
from snf_schedule_optimizer.infrastructure.logging import (
    configure_logging,
    get_logger,
)
from snf_schedule_optimizer.infrastructure.tracing import setup_tracing

configure_logging()
logger = get_logger(__name__)


def _allowed_origins() -> list[str]:
    return [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOW_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_url = os.environ["DATABASE_URL"]
    read_db_url = os.environ.get("READ_DATABASE_URL", db_url)

    engine = create_async_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
        pool_recycle=3600,
        echo=False,
    )
    read_engine = (
        create_async_engine(
            read_db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=5,
            pool_recycle=3600,
            echo=False,
        )
        if read_db_url != db_url
        else engine
    )
    session_local = async_sessionmaker(bind=engine)
    read_session_local = (
        async_sessionmaker(bind=read_engine)
        if read_engine is not engine
        else session_local
    )

    infra_container_type = build_infra_container()

    id_obfuscator = await infra_container_type.id_obfuscator()

    rpc_handler = SchedulingServiceHandler(
        engine,
        session_local,
        id_obfuscator,
        read_session_factory=read_session_local,
    )

    if not getattr(app.state, "rpc_mounted", False):
        app.mount(
            "/scheduling.v1.SchedulingService",
            SchedulingServiceASGIApplication(rpc_handler),  # type: ignore[arg-type]
        )
        app.state.rpc_mounted = True

    app.state.engine = engine
    app.state.read_engine = read_engine
    try:
        yield
    finally:
        if read_engine is not engine:
            await read_engine.dispose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Workforce Optimizer API",
        version="0.0.1",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        run_id = request.headers.get("x-e2e-run-id", "-")
        structlog.contextvars.bind_contextvars(correlation_id=run_id)

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "request.failed",
                method=request.method,
                path=request.url.path,
                run_id=run_id,
                duration_ms=duration_ms,
                exc_info=True,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            run_id=run_id,
            duration_ms=duration_ms,
        )
        return response

    app.include_router(health_router)

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_app()


async def main() -> None:
    setup_tracing()
    config = Config()
    port = os.getenv("PORT", "8000")
    config.bind = [f"0.0.0.0:{port}"]

    config.accesslog = "-"
    config.errorlog = "-"
    config.loglevel = "debug"

    logging.info("Starting Workforce Optimizer API server")
    await serve(cast(ASGIFramework, cast(object, app)), config)


if __name__ == "__main__":
    asyncio.run(main())
