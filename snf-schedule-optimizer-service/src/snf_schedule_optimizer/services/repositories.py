import abc

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    FacilityConfig,
    FacilityIdType,
    Shift,
    ShiftKey,
)


class IShiftRepo(abc.ABC):
    @abc.abstractmethod
    async def get_shifts_for_org(
        self,
        org_id: DomainPrimaryKeyType,
        facility_timezones: dict[DomainPrimaryKeyType, str],
    ) -> list[Shift]:
        """
        Fetches all shifts for an organization.
        Hydrates datetimes using the provided facility_id -> timezone map.
        """
        pass

    @abc.abstractmethod
    async def get_shifts_by_keys(
        self,
        shift_keys: list[ShiftKey],
        facility_timezones: dict[FacilityIdType, str],
        org_id: DomainPrimaryKeyType,
    ) -> dict[ShiftKey, Shift]:
        """
        Batched retrieval of shifts by their composite keys.
        Hydrates datetimes by resolving facility timezones internally (via join).
        """
        pass

    @abc.abstractmethod
    async def save_shift(
        self,
        org_id: DomainPrimaryKeyType,
        shift: Shift,
    ) -> None:
        """Persists a domain Shift object."""
        pass


class IFacilityRepo(abc.ABC):
    """
    Interface for retrieving Facility Configurations.
    """

    @abc.abstractmethod
    async def get_configs(
        self,
        org_id: DomainPrimaryKeyType,
        facility_ids: list[DomainPrimaryKeyType] | None = None,
    ) -> list[FacilityConfig]:
        """
        Retrieves configuration (including timezone) for facilities in an org.

        :param org_id: The organization ID (Required).
        :param facility_ids: Specific list of facilities to fetch.
                             If None, fetches ALL facilities for the org.
        """
        pass

    @abc.abstractmethod
    async def save_config(self, config: FacilityConfig) -> None:
        """Persists a domain FacilityConfig object."""
        pass
