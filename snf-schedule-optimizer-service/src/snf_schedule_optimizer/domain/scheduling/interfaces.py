import abc
from typing import NamedTuple

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    NurseProfile,
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSnapshot,
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
        accumulated_hours: float = 0.0,
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
    async def get_schedule(
        self,
        schedule_lookup: ScheduleLookupKey,
        include_latest_run: bool = True,
    ) -> Schedule | None:
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
        include_latest_run: bool = True,
    ) -> Schedule | None:
        """Returns the demo schedule that overlaps the requested month."""
        pass

    @abc.abstractmethod
    async def save_schedule(self, schedule: Schedule) -> None:
        """Persists a schedule and its assignments."""
        pass

    @abc.abstractmethod
    async def next_schedule_id(
        self, org_id: DomainPrimaryKeyType
    ) -> DomainPrimaryKeyType:
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
    async def get_optimization_run_by_client_request(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        schedule_id: DomainPrimaryKeyType,
        client_request_id: str,
    ) -> OptimizationRun | None:
        """Loads an existing submitted run for idempotent request handling."""
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
    async def append_optimization_run_event(self, event: OptimizationRunEvent) -> None:
        """Appends a durable lifecycle event for an optimization run."""
        pass

    @abc.abstractmethod
    async def list_optimization_run_events(
        self,
        run_id: str,
    ) -> list[OptimizationRunEvent]:
        """Returns persisted events ordered by sequence for the run."""
        pass

    @abc.abstractmethod
    async def claim_next_queued_optimization_run(
        self,
        worker_id: str,
        claim_token: str,
        lease_expires_at: str,
    ) -> OptimizationRun | None:
        """Atomically claims the next queued or stale running run for a worker."""
        pass

    @abc.abstractmethod
    async def renew_optimization_run_lease(
        self,
        run_id: str,
        claim_token: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> bool:
        """Renews a claimed run lease if the claim token still matches."""
        pass

    @abc.abstractmethod
    async def release_optimization_run_claim(
        self,
        run_id: str,
        claim_token: str,
        status: str,
        stage: str,
        status_message: str,
        error_details: str | None = None,
        failure_code: str | None = None,
    ) -> bool:
        """Releases a claimed run into a terminal or queued state if the claim token matches."""
        pass

    @abc.abstractmethod
    async def save_optimization_snapshot(self, snapshot: OptimizationSnapshot) -> None:
        """Persists an immutable optimization snapshot for a run."""
        pass

    @abc.abstractmethod
    async def get_optimization_snapshot(
        self, snapshot_id: str
    ) -> OptimizationSnapshot | None:
        """Loads a persisted optimization snapshot by ID."""
        pass


