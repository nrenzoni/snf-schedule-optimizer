import abc

from snf_schedule_optimizer.models import FacilityConfig, Shift, ShiftKey


class IShiftRetriever(abc.ABC):
    @abc.abstractmethod
    async def get_shifts_for_org(
        self,
        org_id: str,
        facility_timezones: dict[str, str],
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
        facility_timezones: dict[str, str],
        org_id: str,
    ) -> dict[ShiftKey, Shift]:
        """
        Batched retrieval of shifts by their composite keys.
        Hydrates datetimes by resolving facility timezones internally (via join).
        """
        pass


class IFacilityRetriever(abc.ABC):
    """
    Interface for retrieving Facility Configurations.
    """

    @abc.abstractmethod
    async def get_configs(
        self,
        org_id: str,
        facility_ids: list[str] | None = None,
    ) -> list[FacilityConfig]:
        """
        Retrieves configuration (including timezone) for facilities in an org.

        :param org_id: The organization ID (Required).
        :param facility_ids: Specific list of facilities to fetch.
                             If None, fetches ALL facilities for the org.
        """
        pass
