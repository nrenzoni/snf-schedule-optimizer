"""Tests for scenario data provider candidate cache isolation by ShiftKey."""

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    MlModelOutputs,
    NurseProfile,
    OptimizationSettings,
    Shift,
    ShiftKey,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.persistence.fakes import (
    FakeEmployeeRepo,
    FakeHprdRequirementCalculator,
    FakeMLModelRepo,
    FakeStaffCompensationRepo,
    FakeWorkHistoryService,
)
from snf_schedule_optimizer.persistence.nurse_repo import INurseRepo


class _ShiftScopedNurseRepo(INurseRepo):
    def __init__(self, nurses_by_shift: dict[ShiftKey, list[NurseProfile]]) -> None:
        self.nurses_by_shift = nurses_by_shift

    async def get_nurses(self, shift: Shift) -> list[NurseProfile]:
        return self.nurses_by_shift.get(shift.shift_key, [])

    async def get_nurse(self, employee_id: int) -> NurseProfile | None:
        for nurses in self.nurses_by_shift.values():
            for nurse in nurses:
                if nurse.employee_id == employee_id:
                    return nurse
        return None

    async def save_nurse_profile(self, org_id: int, nurse: NurseProfile) -> None:
        pass


async def test_candidate_cache_is_isolated_by_shift_key() -> None:
    ref_date = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    shift_a = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=301),
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        shift_start_dt=ref_date,
        shift_end_dt=ref_date.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )
    shift_b = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=2, shift_id=301),
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        shift_start_dt=ref_date,
        shift_end_dt=ref_date.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )
    nurse_a = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )
    nurse_b = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )
    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo(
            [
                Employee(1, "Facility A", "CNA", ref_date.date()),
                Employee(2, "Facility B", "CNA", ref_date.date()),
            ]
        ),
        nurse_retriever=_ShiftScopedNurseRepo(
            {shift_a.shift_key: [nurse_a], shift_b.shift_key: [nurse_b]}
        ),
        hprd_calculator=FakeHprdRequirementCalculator(),
        staff_compensation_service=FakeStaffCompensationRepo([]),
        ml_model_retriever=FakeMLModelRepo(
            MlModelOutputs(
                turnover_risk_scores={},
                shift_call_out_forecast=0.0,
                unit_acuity_stress={},
                team_compatibility_scores={},
            )
        ),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift_a],
                config=FacilityConfig(
                    org_id=1,
                    facility_id=1,
                    shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0,
                    night_shift_multiplier=1.0,
                    tz="America/New_York",
                ),
            ),
            2: FacilityScenarioContext(
                facility_id=2,
                shifts=[shift_b],
                config=FacilityConfig(
                    org_id=1,
                    facility_id=2,
                    shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0,
                    night_shift_multiplier=1.0,
                    tz="America/New_York",
                ),
            ),
        },
        pay_period_start=ref_date.start_of_day().to_instant(),
        optimization_start_time=ref_date.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    assert [n.employee_id for n in await provider.get_nurses_for_shift(shift_a)] == [1]
    assert [n.employee_id for n in await provider.get_nurses_for_shift(shift_b)] == [2]
