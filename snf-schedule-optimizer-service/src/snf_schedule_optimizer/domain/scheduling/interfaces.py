import abc
from typing import NamedTuple

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    NurseProfile,
    OptimizationRun,
    PatchConflict,
    PreferenceWeights,
    Schedule,
    Shift,
    ShiftSpecificRequirements,
    StagedSchedulePatch,
)


class IShiftRequirementsRepo(abc.ABC):
    @abc.abstractmethod
    async def get_shift_requirements(
        self, shift: Shift
    ) -> ShiftSpecificRequirements | None:
        pass


class IPreferencePenaltyProcessor(abc.ABC):
    """Defines the service for calculating non-financial penalties for soft constraints."""

    @abc.abstractmethod
    async def calculate_penalty_cost(
        self,
        employee: Employee,
        nurse: NurseProfile,
        shift: Shift,
        preference_weights: PreferenceWeights,
    ) -> float:
        """
        Calculates the non-financial penalty cost if the assignment violates a soft preference.
        This cost is added to the LP objective function.
        """
        pass


class ScheduleLookupKey(NamedTuple):
    org_id: DomainPrimaryKeyType
    schedule_id: DomainPrimaryKeyType


class IScheduleRepo(abc.ABC):
    """
    Interface for retrieving Schedule objects (assignments) from persistence.
    """

    @abc.abstractmethod
    async def get_schedule(self, schedule_lookup: ScheduleLookupKey) -> Schedule | None:
        """
        Retrieves the schedule assignments for a specific schedule ID.
        Returns None if not found.
        """
        pass

    @abc.abstractmethod
    async def get_schedule_for_month(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType | None,
        start_date: str,
    ) -> Schedule | None:
        """Returns the demo schedule that overlaps the requested month."""
        pass

    @abc.abstractmethod
    async def save_schedule(self, schedule: Schedule) -> None:
        """Persists a schedule and its assignments."""
        pass

    @abc.abstractmethod
    async def next_schedule_id(self, org_id: DomainPrimaryKeyType) -> DomainPrimaryKeyType:
        """Allocates the next schedule identifier for the org."""
        pass

    @abc.abstractmethod
    async def get_latest_schedule_version(
        self,
        org_id: DomainPrimaryKeyType,
        schedule_id: DomainPrimaryKeyType,
    ) -> int | None:
        """Returns the latest persisted version for the stable schedule workspace."""
        pass

    @abc.abstractmethod
    async def reapply_patches(
        self,
        schedule: Schedule,
        patches: list[StagedSchedulePatch],
    ) -> tuple[Schedule, list[PatchConflict]]:
        """Applies staged manual patches to a schedule, returning any conflicts."""
        pass

    @abc.abstractmethod
    async def save_optimization_run(self, run: OptimizationRun) -> None:
        """Persists optimization run metadata."""
        pass

    @abc.abstractmethod
    async def get_optimization_run(self, run_id: str) -> OptimizationRun | None:
        """Loads a persisted optimization run by its public ID."""
        pass

    @abc.abstractmethod
    async def get_active_optimization_run(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        schedule_id: DomainPrimaryKeyType,
    ) -> OptimizationRun | None:
        """Returns the most recent queued/running optimization run for the workspace."""
        pass

    @abc.abstractmethod
    async def commit(self) -> None:
        """Flushes and commits request-scoped mutations."""
        pass
