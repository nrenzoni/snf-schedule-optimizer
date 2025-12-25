import asyncio
import logging
import os
from typing import cast

from fastapi import FastAPI
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

db_url = os.environ["DATABASE_URL"]
engine = create_async_engine(db_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine)

app = FastAPI(
    title="Workforce Optimizer API",
    version="0.0.1",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


async def main() -> None:
    retrievers_container_type = build_repos_container(engine, SessionLocal)
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
    scheduling_rpc_app = SchedulingServiceASGIApplication(rpc_handler)

    app.mount("/scheduling.v1.SchedulingService", scheduling_rpc_app)

    config = Config()
    config.bind = ["0.0.0.0:8000"]

    # Enable Hypercorn access logs (Method, Path, Status Code)
    config.accesslog = "-"  # "-" means log to stdout
    config.errorlog = "-"
    config.loglevel = "debug"

    try:
        logging.info("Starting Workforce Optimizer API server")
        await serve(cast(ASGIFramework, cast(object, app)), config)
    finally:
        await scheduler_facade.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
