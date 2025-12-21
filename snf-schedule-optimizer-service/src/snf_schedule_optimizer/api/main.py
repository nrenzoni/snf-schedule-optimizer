import asyncio
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
    compose_scheduler_service,
)

DB_URL = "postgresql+asyncpg://user:pass@localhost/dbname"
engine = create_async_engine(DB_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine)

app = FastAPI(
    title="Workforce Optimizer API",
    version="0.0.1",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


async def main() -> None:
    scheduler_facade = await compose_scheduler_service(SessionLocal)

    rpc_handler = SchedulingServiceHandler(scheduler_facade)
    scheduling_rpc_app = SchedulingServiceASGIApplication(rpc_handler)

    app.mount("/scheduling.v1.SchedulingService", scheduling_rpc_app)

    config = Config()
    config.bind = ["0.0.0.0:8000"]

    try:
        await serve(cast(ASGIFramework, cast(object, app)), config)
    finally:
        await scheduler_facade.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
