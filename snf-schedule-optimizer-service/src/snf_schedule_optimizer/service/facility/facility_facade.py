from snf_schedule_optimizer.domain.repositories import IFacilityRepo
from snf_schedule_optimizer.models import DomainPrimaryKeyType, FacilityConfig


class FacilityFacade:
    """
    Application Service (Facade) for facility-related operations.

    This facade coordinates the retrieval and management of facility
    configurations, ensuring that the API layer (ConnectRPC) remains
    decoupled from the specifics of the persistence implementation.
    """

    def __init__(self, facility_repo: IFacilityRepo):
        self.facility_repo = facility_repo

    async def get_all_org_facilities(
        self, org_id: DomainPrimaryKeyType
    ) -> list[FacilityConfig]:
        """
        Retrieves all facility configurations belonging to a specific organization.

        This method supports the 'GetAllOrgFacilities' RPC call by fetching
        domain objects from the tenant-scoped repository.
        """
        # IFacilityRepository.get_configs is naturally tenant-aware
        return await self.facility_repo.get_configs(
            org_id=org_id,
            facility_ids=None,
        )

    async def get_facility_config(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
    ) -> FacilityConfig | None:
        """
        Retrieves a single facility configuration by its ID,
        verifying it belongs to the specified organization.
        """

        configs = await self.facility_repo.get_configs(
            org_id=org_id,
            facility_ids=[facility_id],
        )
        return configs[0] if configs else None

    async def get_all_system_facilities(self) -> list[FacilityConfig]:
        """
        Admin-level retrieval of all facilities across the entire system.
        This ignores tenant scoping and is intended for cross-organization reporting.
        """
        return await self.facility_repo.get_all_facilities()

    async def update_facility_config(self, config: FacilityConfig) -> None:
        """
        Updates an existing facility configuration or creates a new one.
        Note: The transaction boundary should be managed by the caller
        if this is part of a larger unit of work.
        """
        await self.facility_repo.save_config(config)
