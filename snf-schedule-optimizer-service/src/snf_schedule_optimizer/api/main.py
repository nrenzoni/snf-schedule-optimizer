import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from hypercorn import Config
from hypercorn.asyncio import serve
from hypercorn.typing import ASGIFramework
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from snf_schedule_optimizer.api.grpc.scheduler_handler import SchedulingServiceHandler
from snf_schedule_optimizer.generated.scheduling.v1.scheduling_connect import (
    SchedulingServiceASGIApplication,
)
from snf_schedule_optimizer.infrastructure.composition import (
    build_facility_container,
    build_infra_container,
    build_repos_container,
    build_scheduler_container,
)


def _allowed_origins() -> list[str]:
    return [
        origin.strip()
        for origin in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, pool_pre_ping=True)
    session_local = async_sessionmaker(bind=engine)

    retrievers_container_type = build_repos_container(engine, session_local)
    scheduler_container_type = build_scheduler_container(retrievers_container_type)
    facility_container_type = build_facility_container(retrievers_container_type)
    infra_container_type = build_infra_container()

    scheduler_facade = await scheduler_container_type.scheduler_service()
    facility_facade = await facility_container_type.facility_facade()
    id_obfuscator = await infra_container_type.id_obfuscator()

    rpc_handler = SchedulingServiceHandler(
        scheduler_facade,
        facility_facade,
        id_obfuscator,
    )

    if not getattr(app.state, "rpc_mounted", False):
        app.mount(
            "/scheduling.v1.SchedulingService",
            SchedulingServiceASGIApplication(rpc_handler),
        )
        app.state.rpc_mounted = True

    app.state.engine = engine
    app.state.scheduler_facade = scheduler_facade

    try:
        yield
    finally:
        await scheduler_facade.close()
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

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_app()


async def main() -> None:
    config = Config()
    config.bind = ["0.0.0.0:8000"]

    # Enable Hypercorn access logs (Method, Path, Status Code)
    config.accesslog = "-"  # "-" means log to stdout
    config.errorlog = "-"
    config.loglevel = "debug"

    logging.info("Starting Workforce Optimizer API server")
    await serve(cast(ASGIFramework, cast(object, app)), config)


if __name__ == "__main__":
    asyncio.run(main())
