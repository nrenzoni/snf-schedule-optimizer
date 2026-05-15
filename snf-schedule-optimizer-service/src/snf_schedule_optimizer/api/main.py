import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from hypercorn import Config
from hypercorn.asyncio import serve
from hypercorn.typing import ASGIFramework
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.responses import Response

from snf_schedule_optimizer.api.grpc.scheduler_handler import SchedulingServiceHandler
from snf_schedule_optimizer.generated.scheduling.v1.scheduling_connect import (
    SchedulingServiceASGIApplication,
)
from snf_schedule_optimizer.infrastructure.composition import build_infra_container

logger = logging.getLogger("snf_schedule_optimizer.api")


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
    engine = create_async_engine(db_url, pool_pre_ping=True)
    session_local = async_sessionmaker(bind=engine)

    infra_container_type = build_infra_container()

    id_obfuscator = await infra_container_type.id_obfuscator()

    rpc_handler = SchedulingServiceHandler(
        engine,
        session_local,
        id_obfuscator,
    )

    if not getattr(app.state, "rpc_mounted", False):
        app.mount(
            "/scheduling.v1.SchedulingService",
            SchedulingServiceASGIApplication(rpc_handler),
        )
        app.state.rpc_mounted = True

    app.state.engine = engine
    try:
        yield
    finally:
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

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request.failed method=%s path=%s run_id=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                run_id,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request.completed method=%s path=%s status=%s run_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            run_id,
            duration_ms,
        )
        return response

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


async def main() -> None:
    app = create_app()
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
