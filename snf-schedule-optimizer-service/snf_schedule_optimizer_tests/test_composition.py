from types import TracebackType
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from that_depends import container_context
from that_depends.providers.context_resources import ContextScopes, SupportsContext

from snf_schedule_optimizer.infrastructure.composition import (
    build_facility_container,
    build_infra_container,
    build_repos_container,
    build_scheduler_container,
)


class FakeSession:
    def __init__(self) -> None:
        self.closed = False


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.session.closed = True


class FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSessionContext:
        session = FakeSession()
        self.sessions.append(session)
        return FakeSessionContext(session)


async def test_repos_container_db_session_is_scoped_to_container_context() -> None:
    session_factory = FakeSessionFactory()
    repos_container = build_repos_container(
        cast(AsyncEngine, object()),
        cast(async_sessionmaker[AsyncSession], session_factory),
    )

    async with container_context(
        cast(SupportsContext[Any], repos_container),
        scope=ContextScopes.REQUEST,
    ):
        session = cast(FakeSession, await repos_container.db_session.resolve())
        assert not session.closed

    assert len(session_factory.sessions) == 1
    assert session_factory.sessions[0].closed


async def test_repos_container_db_session_requires_container_context() -> None:
    session_factory = FakeSessionFactory()
    repos_container = build_repos_container(
        cast(AsyncEngine, object()),
        cast(async_sessionmaker[AsyncSession], session_factory),
    )

    try:
        await repos_container.db_session.resolve()
    except RuntimeError as exc:
        assert "Context is not set" in str(exc)
    else:
        raise AssertionError("db_session resolved outside container_context")


async def test_infra_container_id_obfuscator_resolves() -> None:
    infra_container = build_infra_container()
    await infra_container.id_obfuscator.resolve()


async def test_facility_container_all_top_level_providers_resolve() -> None:
    session_factory = FakeSessionFactory()
    repos_container = build_repos_container(
        cast(AsyncEngine, object()),
        cast(async_sessionmaker[AsyncSession], session_factory),
    )
    facility_container = build_facility_container(repos_container)

    async with container_context(
        cast(SupportsContext[Any], facility_container),
        scope=ContextScopes.REQUEST,
    ):
        await facility_container.facility_facade.resolve()
        await facility_container.facility_repo.resolve()


async def test_scheduler_container_all_top_level_providers_resolve() -> None:
    session_factory = FakeSessionFactory()
    repos_container = build_repos_container(
        cast(AsyncEngine, object()),
        cast(async_sessionmaker[AsyncSession], session_factory),
    )
    scheduler_container = build_scheduler_container(repos_container)

    async with container_context(
        cast(SupportsContext[Any], scheduler_container),
        scope=ContextScopes.REQUEST,
    ):
        await scheduler_container.scheduler_service.resolve()
        await scheduler_container.optimizer.resolve()
        await scheduler_container.provider_factory.resolve()
        await scheduler_container.cost_evaluator.resolve()
        await scheduler_container.gap_detector.resolve()
        await scheduler_container.pbj_generator.resolve()
