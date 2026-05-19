"""Unit tests for IUnitOfWork pattern."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from snf_schedule_optimizer.persistence.unit_of_work import (
    AsyncUnitOfWork,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.begin = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    factory = MagicMock()
    factory.return_value = mock_session
    return factory


class TestAsyncUnitOfWork:
    async def test_aenter_begins_transaction(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)
        async with uow:
            pass
        mock_session.begin.assert_awaited_once()

    async def test_creates_all_repos_on_entry(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        async with uow as ctx:
            assert ctx is uow
            assert ctx.shift_repo is not None
            assert ctx.schedule_repo is not None
            assert ctx.facility_repo is not None
            assert ctx.employee_repo is not None
            assert ctx.nurse_repo is not None
            assert ctx.certification_repo is not None
            assert ctx.history_repo is not None
            assert ctx.compensation_repo is not None
            assert ctx.differential_rule_repo is not None
            assert ctx.overtime_rule_repo is not None
            assert ctx.facility_rules_repo is not None
            assert ctx.employee_rules_repo is not None
            assert ctx.shift_requirements_repo is not None
            assert ctx.acuity_repo is not None

        mock_session_factory.assert_called_once()

    async def test_commit_delegates_to_session(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        async with uow:
            await uow.commit()

        mock_session.commit.assert_awaited_once()

    async def test_commit_marks_committed(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        async with uow:
            assert not uow._committed
            await uow.commit()
            assert uow._committed

    async def test_rollback_delegates_to_session(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        async with uow:
            await uow.rollback()
            assert mock_session.rollback.await_count == 1

        assert mock_session.rollback.await_count == 2

    async def test_close_on_exit(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        async with uow:
            pass

        mock_session.close.assert_awaited_once()

    async def test_aexit_rollback_when_not_committed(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        async with uow:
            pass  # no commit

        mock_session.rollback.assert_awaited_once()

    async def test_aexit_no_rollback_when_committed(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        async with uow:
            await uow.commit()

        mock_session.rollback.assert_not_awaited()
        mock_session.close.assert_awaited_once()

    async def test_aexit_rollback_on_exception(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        with pytest.raises(ValueError):
            async with uow:
                raise ValueError("boom")

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    async def test_close_nulls_session(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        uow = AsyncUnitOfWork(mock_session_factory)

        async with uow:
            assert uow._session is not None

        assert uow._session is None

    async def test_commit_noop_when_no_session(self) -> None:
        uow = AsyncUnitOfWork(MagicMock())
        await uow.commit()

    async def test_rollback_noop_when_no_session(self) -> None:
        uow = AsyncUnitOfWork(MagicMock())
        await uow.rollback()

    async def test_close_noop_when_no_session(self) -> None:
        uow = AsyncUnitOfWork(MagicMock())
        await uow.close()
