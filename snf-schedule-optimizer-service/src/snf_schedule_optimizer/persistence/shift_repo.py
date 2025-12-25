import whenever
from sqlalchemy import and_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.domain.repositories import IShiftRepo
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Shift,
    ShiftKey,
)
from snf_schedule_optimizer.sqlalchemy_models.shift import ShiftModel


class SQLShiftRepo(IShiftRepo):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_shifts_for_org(
        self,
        org_id: DomainPrimaryKeyType,
        facility_timezones: dict[DomainPrimaryKeyType, str],
    ) -> list[Shift]:
        # 1. Single DB Query for the whole Org
        stmt = select(ShiftModel).where(ShiftModel.org_id == org_id)
        results = (await self.session.scalars(stmt)).all()

        domain_shifts = []

        for row in results:
            fac_id = row.facility_id
            tz_str = facility_timezones.get(fac_id, "UTC")

            domain_shifts.append(self._map_row_to_domain(row, tz_str))

        return domain_shifts

    async def get_shifts_by_keys(
        self,
        shift_keys: list[ShiftKey],
        facility_timezones: dict[DomainPrimaryKeyType, str],
        org_id: DomainPrimaryKeyType,
    ) -> dict[ShiftKey, Shift]:
        if not shift_keys:
            return {}

        # Prepare composite keys for SQL IN clause
        keys_tuples = [(k.facility_id, k.shift_id) for k in shift_keys]

        # Join with FacilityModel to get the timezone for hydration
        stmt = select(ShiftModel).where(
            and_(
                ShiftModel.org_id == org_id,
                tuple_(
                    ShiftModel.org_id, ShiftModel.facility_id, ShiftModel.shift_id
                ).in_(keys_tuples),
            )
        )

        results = (await self.session.scalars(stmt)).all()

        shift_map: dict[ShiftKey, Shift] = {}

        for shift_row in results:
            fac_id = shift_row.facility_id
            timezone_str = facility_timezones.get(fac_id)
            if not timezone_str:
                raise ValueError(f"Timezone not found for facility_id: {fac_id}")

            domain_shift = self._map_row_to_domain(shift_row, timezone_str)

            # Reconstruct key from domain object to ensure perfect match
            key = ShiftKey(
                facility_id=domain_shift.facility_id,
                shift_id=domain_shift.shift_id,
            )
            shift_map[key] = domain_shift

        return shift_map

    async def save_shift(self, org_id: DomainPrimaryKeyType, shift: Shift) -> None:
        model = ShiftModel.from_domain(org_id, shift)
        await self.session.merge(model)

    def _map_row_to_domain(self, row: ShiftModel, timezone_str: str) -> Shift:
        """Helper to map a DB row to a Domain Shift using a timezone string."""
        start_instant = row.shift_start_dt.to_tz(timezone_str)
        end_instant = row.shift_end_dt.to_tz(timezone_str)

        return Shift(
            org_id=row.org_id,
            shift_key=ShiftKey(
                row.facility_id,
                row.shift_id,
            ),
            shift_number=int(row.shift_number or 0),
            day_shift=bool(row.day_shift),
            day_of_week=whenever.Weekday(row.day_of_week),
            shift_start_dt=start_instant,
            shift_end_dt=end_instant,
            unit_id=row.unit_id,
            is_scheduled=row.is_scheduled,
        )
