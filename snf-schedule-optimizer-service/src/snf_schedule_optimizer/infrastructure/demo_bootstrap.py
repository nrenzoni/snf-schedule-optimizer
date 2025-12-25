import asyncio
import logging
import os

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from snf_schedule_optimizer.infrastructure.composition import (
    build_repos_container,
)
from snf_schedule_optimizer.infrastructure.demo_seeder import DemoSeeder
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase
from snf_schedule_optimizer.sqlalchemy_models.employee import EmployeeModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo-bootstrap")


async def bootstrap() -> None:
    """
    Idempotently sets up the database schema and seeds demo data
    if the database is empty.
    """
    logger.info("Initializing Demo Bootstrap...")

    # 1. Create Schema
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, pool_pre_ping=True, echo=False)
    session_maker = async_sessionmaker(bind=engine)
    repos_container = build_repos_container(engine, session_maker)

    async with engine.begin() as conn:
        logger.info("Synchronizing database schema...")
        await conn.run_sync(SQLABase.metadata.create_all)

    session: AsyncSession = await repos_container.db_session()

    # 2. Check if seeding is required
    # Use a scoped session from the container
    async with session.begin() as transaction:
        # Check for existing employees as a marker for seeded data
        stmt = select(func.count()).select_from(EmployeeModel)
        result = await session.execute(stmt)
        count = result.scalar()

        if count == 0:
            logger.info("No data found. Running DemoSeeder...")

            # Use the DIContainer to resolve repositories automatically
            # We construct the seeder manually here to ensure it uses the current session
            seeder = DemoSeeder(
                employee_repo=await repos_container.employee_retriever.resolve(),
                nurse_repo=await repos_container.nurse_retriever.resolve(),
                shift_repo=await repos_container.shift_retriever.resolve(),
                comp_repo=await repos_container.compensation_retriever.resolve(),
                db_session=session,
            )

            await seeder.seed_from_scenario(seed=42)
            logger.info("Seeding complete.")
        else:
            logger.info(
                f"Database already contains {count} employees. Skipping seeding."
            )


if __name__ == "__main__":
    asyncio.run(bootstrap())
