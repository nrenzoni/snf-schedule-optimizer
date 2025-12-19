import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from snf_schedule_optimizer.api.grpc.scheduler_handler import SchedulingServiceHandler
from snf_schedule_optimizer.generated.scheduling.v1.scheduling_connect import (
    SchedulingServiceASGIApplication,
)
from snf_schedule_optimizer.infrastructure.composition import compose_scheduler_service

# 1. Database Setup (Infrastructure)
DB_URL = "postgresql://user:pass@localhost/dbname"
engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


@contextlib.asynccontextmanager
async def lifespan(app_param: FastAPI) -> AsyncIterator[None]:
    """Handles startup and shutdown logic."""
    yield
    engine.dispose()


# 2. Initialize FastAPI
app = FastAPI(title="Workforce Optimizer API", version="0.0.1", lifespan=lifespan)

# 3. Dependency Injection & Service Composition
# We create a single instance of the Facade using our composition helper.
# In a production app, you might use a DI library, but manual wiring is clearer for DDD-lite.
scheduler_facade = compose_scheduler_service(SessionLocal)

# 4. Initialize the RPC Handler
rpc_handler = SchedulingServiceHandler(scheduler_facade)

scheduling_rpc_app = SchedulingServiceASGIApplication(rpc_handler)

# 5. Register ConnectRPC Handler
# We mount the Connect handler into the FastAPI ASGI pipeline.
app.mount("/scheduling.v1.SchedulingService", scheduling_rpc_app)


# 6. Optional: Standard FastAPI Endpoints
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
