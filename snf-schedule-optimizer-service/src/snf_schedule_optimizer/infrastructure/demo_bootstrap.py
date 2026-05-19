import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, cast

from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from that_depends import container_context
from that_depends.providers.context_resources import ContextScopes, SupportsContext

from snf_schedule_optimizer.infrastructure.composition import (
    build_repos_container,
)
from snf_schedule_optimizer.infrastructure.demo_seeder import DemoSeeder
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo-bootstrap")

MAX_BOOTSTRAP_ATTEMPTS = 5
BOOTSTRAP_RETRY_DELAY_SECONDS = 1.0


async def bootstrap() -> None:
    """
    Rebuilds the demo database from current models and seeds demo data.
    """
    logger.info("Initializing Demo Bootstrap...")

    # 1. Create Schema
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, pool_pre_ping=True, echo=False)
    try:
        session_maker = async_sessionmaker(bind=engine)
        repos_container = build_repos_container(engine, session_maker)

        async with engine.begin() as conn:
            logger.info("Rebuilding demo database schema...")
            await conn.run_sync(SQLABase.metadata.drop_all)
            await conn.run_sync(SQLABase.metadata.create_all)

        async with container_context(
            cast(SupportsContext[Any], repos_container),
            scope=ContextScopes.REQUEST,
        ):
            session: AsyncSession = await repos_container.db_session()

            async with session.begin():
                seeder = DemoSeeder(
                    employee_repo=await repos_container.employee_retriever.resolve(),
                    nurse_repo=await repos_container.nurse_retriever.resolve(),
                    shift_repo=await repos_container.shift_retriever.resolve(),
                    comp_repo=await repos_container.compensation_retriever.resolve(),
                    facility_repo=await repos_container.facility_retriever.resolve(),
                    schedule_repo=await repos_container.schedule_retriever.resolve(),
                    db_session=session,
                )

                logger.info("Seeding demo data...")
                seed = int(os.environ.get("DEMO_SEED", "42"))
                await seeder.seed_from_scenario(seed=seed)
                logger.info("Seeding complete.")
    finally:
        await engine.dispose()


def _is_transient_database_disconnect(exc: BaseException) -> bool:
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True

    message = str(exc)
    return (
        "ConnectionDoesNotExistError" in message
        or "connection was closed in the middle of operation" in message
        or "Connection reset by peer" in message
    )


async def _retry_transient_disconnects(
    operation: Callable[[], Awaitable[None]],
) -> None:
    for attempt in range(1, MAX_BOOTSTRAP_ATTEMPTS + 1):
        try:
            await operation()
            return
        except Exception as exc:
            if (
                attempt == MAX_BOOTSTRAP_ATTEMPTS
                or not _is_transient_database_disconnect(exc)
            ):
                raise

            logger.warning(
                "Database connection dropped during bootstrap; retrying (%s/%s)...",
                attempt,
                MAX_BOOTSTRAP_ATTEMPTS,
            )
            await asyncio.sleep(BOOTSTRAP_RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    asyncio.run(_retry_transient_disconnects(bootstrap))
