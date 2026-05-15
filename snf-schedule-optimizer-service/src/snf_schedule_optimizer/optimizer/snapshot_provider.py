from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import whenever

from snf_schedule_optimizer.domain.hr.interfaces import IStaffCompensationRepo
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    EmployeeIdType,
    EmployeeStateSnapshot,
    FacilityConfig,
    FacilityIdType,
    HprdEnforcedRole,
    MinMandates,
    MlModelOutputs,
    NurseProfile,
    OptimizationSettings,
    PreferenceType,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
    StaffShiftPreference,
)
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    HprdShiftNurseRequirementHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider


@dataclass(frozen=True)
class _PrefDict:
    preference_type: str
    specific_value: str | None
    penalty_weight: float
    is_hard_block: bool


def _reconstruct_preference(raw: _PrefDict) -> StaffShiftPreference:
    return StaffShiftPreference(
        preference_type=PreferenceType(raw.preference_type),
        specific_value=raw.specific_value,
        penalty_weight=raw.penalty_weight,
        is_hard_block=raw.is_hard_block,
    )


def _shift_from_dict(raw: dict[str, Any], tz: str) -> Shift:
    return Shift(
        org_id=raw["org_id"],
        shift_key=ShiftKey(raw["facility_id"], raw["shift_id"]),
        shift_number=raw["shift_number"],
        day_shift=raw["day_shift"],
        day_of_week=whenever.Weekday[raw["day_of_week"]],
        shift_start_dt=whenever.ZonedDateTime.parse_common_iso(raw["shift_start_iso"]),
        shift_end_dt=whenever.ZonedDateTime.parse_common_iso(raw["shift_end_iso"]),
        unit_id=raw.get("unit_id"),
        is_scheduled=raw["is_scheduled"],
    )


def _employee_from_dict(raw: dict[str, Any]) -> Employee:
    return Employee(
        employee_id=raw["employee_id"],
        name=raw["name"],
        job_title=raw["job_title"],
        hire_date=whenever.Date.parse_common_iso(raw["hire_date"]),
    )


def _nurse_from_dict(raw: dict[str, Any]) -> NurseProfile:
    prefs = raw.get("shift_custom_preferences")
    shift_custom_preferences = (
        [_reconstruct_preference(_PrefDict(**p)) for p in prefs] if prefs else None
    )
    return NurseProfile(
        employee_id=raw["employee_id"],
        available_hours_weekly=raw["available_hours_weekly"],
        skills=raw.get("skills"),
        shift_custom_preferences=shift_custom_preferences,
        primary_unit_id=raw.get("primary_unit_id"),
        is_preceptor=raw.get("is_preceptor", False),
        is_charge_nurse=raw.get("is_charge_nurse", False),
    )


def _config_from_dict(raw: dict[str, Any]) -> FacilityConfig:
    pay_period_days = raw.get("pay_period", 14)
    return FacilityConfig(
        org_id=raw["org_id"],
        facility_id=raw["facility_id"],
        shifts_per_day=raw["shifts_per_day"],
        overtime_threshold_hours_per_week=raw["overtime_threshold_hours_per_week"],
        start_of_work_week_day=whenever.Weekday[raw["start_of_work_week_day"]],
        start_of_work_day_time=whenever.Time.parse_common_iso(
            raw["start_of_work_day_time"]
        ),
        pay_period=whenever.DateDelta(days=int(pay_period_days)),
        weekend_multiplier=raw["weekend_multiplier"],
        night_shift_multiplier=raw["night_shift_multiplier"],
        tz=raw["tz"],
        default_hprd_rn=raw.get("default_hprd_rn", 0.5),
        default_hprd_lpn=raw.get("default_hprd_lpn", 0.0),
        default_hprd_cna=raw.get("default_hprd_cna", 2.4),
        default_hprd_total=raw.get("default_hprd_total", 3.5),
        min_rest_hours_between_shifts=raw.get("min_rest_hours_between_shifts", 10.0),
        max_consecutive_work_days=raw.get("max_consecutive_work_days", 5),
        max_total_hours_per_pay_period=raw.get("max_total_hours_per_pay_period", 80.0),
        min_circadian_rest_after_night=raw.get("min_circadian_rest_after_night", 11.0),
        max_new_grads_per_preceptor=raw.get("max_new_grads_per_preceptor", 2),
        require_charge_nurse_per_shift=raw.get("require_charge_nurse_per_shift", False),
    )


def _comp_from_dict(raw: dict[str, Any]) -> StaffCompensationRecord:
    return StaffCompensationRecord(
        employee_id=raw["employee_id"],
        base_rate_effective=raw["base_rate_effective"],
        ot_multiplier=raw.get("ot_multiplier", 1.5),
        is_agency=raw.get("is_agency", False),
        effective_start_date=whenever.Date.parse_common_iso(
            raw["effective_start_date"]
        ),
        effective_end_date=(
            whenever.Date.parse_common_iso(raw["effective_end_date"])
            if raw.get("effective_end_date")
            else None
        ),
        union_contract_id=raw.get("union_contract_id"),
        pay_grade_or_step=raw.get("pay_grade_or_step"),
    )


def _mandates_from_dict(raw: dict[str, Any]) -> MinMandates:
    return MinMandates(
        min_rn_hprd=raw["min_rn_hprd"],
        min_lpn_hprd=raw.get("min_lpn_hprd", 0.0),
        min_cna_hprd=raw["min_cna_hprd"],
        min_total_hprd=raw["min_total_hprd"],
        min_staff_per_shift_rn=raw["min_staff_per_shift_rn"],
        min_staff_per_shift_lpn=raw.get("min_staff_per_shift_lpn", 0),
        min_staff_per_shift_cna=raw["min_staff_per_shift_cna"],
    )


class _SnapshotCompensationService(IStaffCompensationRepo):
    def __init__(self, records: dict[DomainPrimaryKeyType, StaffCompensationRecord]):
        self._records = records

    async def get_record_for_date(
        self,
        org_id: int,
        employee_id: EmployeeIdType,
        check_date: whenever.Date,
    ) -> StaffCompensationRecord | None:
        return self._records.get(employee_id)

    async def get_all_records_for_org(
        self,
        org_id: int,
        check_date: whenever.Date,
    ) -> dict[DomainPrimaryKeyType, StaffCompensationRecord]:
        return dict(self._records)

    async def save_compensation_record(
        self, org_id: int, record: StaffCompensationRecord
    ) -> None:
        pass


class SnapshotScenarioDataProvider(IScenarioDataProvider):
    def __init__(
        self,
        org_id: DomainPrimaryKeyType,
        facility_contexts: dict[DomainPrimaryKeyType, FacilityScenarioContext],
        employees: list[Employee],
        nurses_by_shift: dict[ShiftKey, list[NurseProfile]],
        hprd_requirements: dict[DomainPrimaryKeyType, HprdShiftNurseRequirementHolder],
        accumulated_hours: dict[DomainPrimaryKeyType, float],
        compensation: dict[DomainPrimaryKeyType, StaffCompensationRecord],
        optimization_settings: OptimizationSettings,
        employee_states: dict[DomainPrimaryKeyType, EmployeeStateSnapshot]
        | None = None,
    ):
        self._org_id = org_id
        self._facility_contexts = facility_contexts
        self._employees = employees
        self._employee_states = employee_states or {}
        self._employees_by_id = {e.employee_id: e for e in employees}
        self._nurses_by_shift = nurses_by_shift
        self._hprd_requirements = hprd_requirements
        self._accumulated_hours = accumulated_hours
        self._compensation = compensation
        self._comp_svc = _SnapshotCompensationService(compensation)
        self._optimization_settings = optimization_settings
        self._all_shifts: list[Shift] | None = None

    def get_org_id(self) -> DomainPrimaryKeyType:
        return self._org_id

    async def get_all_employees(self) -> list[Employee]:
        return self._employees

    async def get_employee_by_id(self, employee_id: EmployeeIdType) -> Employee | None:
        return self._employees_by_id.get(employee_id)

    def get_compensation_service(self) -> _SnapshotCompensationService:
        return self._comp_svc

    async def get_compensation_for_date(
        self,
        employee_id: EmployeeIdType,
        check_date: whenever.Date,
    ) -> StaffCompensationRecord | None:
        return self._compensation.get(employee_id)

    def get_all_shifts(self) -> list[Shift]:
        if self._all_shifts is None:
            self._all_shifts = []
            for ctx in self._facility_contexts.values():
                self._all_shifts.extend(ctx.shifts)
        return self._all_shifts

    def get_facility_ids(self) -> list[FacilityIdType]:
        return list(self._facility_contexts.keys())

    def get_shifts_for_facility(self, facility_id: DomainPrimaryKeyType) -> list[Shift]:
        return self._facility_contexts[facility_id].shifts

    async def get_nurses_for_shift(self, shift: Shift) -> list[NurseProfile]:
        return self._nurses_by_shift.get(shift.shift_key, [])

    async def get_hprd_requirements_for_facility(
        self,
        facility_id: DomainPrimaryKeyType,
    ) -> HprdShiftNurseRequirementHolder:
        return self._hprd_requirements[facility_id]

    def get_ml_model_outputs(self, shift: Shift) -> MlModelOutputs:
        return MlModelOutputs(
            turnover_risk_scores={},
            shift_call_out_forecast=0.0,
            unit_acuity_stress={},
            team_compatibility_scores={},
        )

    async def get_accumulated_hours_for_pay_period(
        self, employee_id: DomainPrimaryKeyType
    ) -> float:
        return self._accumulated_hours.get(employee_id, 0.0)

    def get_facility_config(self, facility_id: DomainPrimaryKeyType) -> FacilityConfig:
        return self._facility_contexts[facility_id].config

    def get_optimization_settings(self) -> OptimizationSettings:
        return self._optimization_settings

    async def get_employee_states(
        self,
    ) -> dict[DomainPrimaryKeyType, EmployeeStateSnapshot]:
        if self._employee_states:
            return self._employee_states
        states: dict[DomainPrimaryKeyType, EmployeeStateSnapshot] = {}
        for emp in self._employees:
            hours = self._accumulated_hours.get(emp.employee_id, 0.0)
            states[emp.employee_id] = EmployeeStateSnapshot(
                employee_id=emp.employee_id,
                worked_hours_day=0.0,
                worked_hours_week=hours,
                worked_hours_pay_period=hours,
                consecutive_days_worked=0,
                last_shift_end=None,
                last_shift_type=None,
            )
        return states

    def get_facility_context(
        self, facility_id: DomainPrimaryKeyType
    ) -> FacilityScenarioContext:
        return self._facility_contexts[facility_id]

    @staticmethod
    def from_snapshot_payload(
        payload: dict[str, object],
    ) -> SnapshotScenarioDataProvider:
        raw_ctxs: dict[str, Any] = payload.get("facility_contexts", {})  # type: ignore[assignment]
        raw_emps: list[Any] = payload.get("employees", [])  # type: ignore[assignment]
        raw_nurses: dict[str, Any] = payload.get("nurses_by_shift", {})  # type: ignore[assignment]
        raw_hprd: dict[str, Any] = payload.get("hprd_requirements", {})  # type: ignore[assignment]
        raw_hours: dict[str, Any] = payload.get("accumulated_hours", {})  # type: ignore[assignment]
        raw_comp: dict[str, Any] = payload.get("compensation", {})  # type: ignore[assignment]

        settings_raw: dict[str, Any] = payload.get("settings", {})  # type: ignore[assignment]
        settings = OptimizationSettings(
            use_ml_forecast=settings_raw.get("use_ml_forecast", False),
            use_callout_buffer=settings_raw.get("use_callout_buffer", True),
            buffer_threshold=settings_raw.get("buffer_threshold", 10),
            min_rest_period=settings_raw.get("min_rest_period", 10),
            max_shift_length=settings_raw.get("max_shift_length", 12.0),
            premium_weekend=settings_raw.get("premium_weekend", True),
            premium_holiday=settings_raw.get("premium_holiday", False),
            overtime_avoidance_penalty=settings_raw.get(
                "overtime_avoidance_penalty", 1000.0
            ),
            team_consistency_penalty=settings_raw.get(
                "team_consistency_penalty", 300.0
            ),
            high_risk_shift_penalty=settings_raw.get("high_risk_shift_penalty", 2000.0),
            custom_preference_penalty=settings_raw.get(
                "custom_preference_penalty", 1500.0
            ),
        )

        org_id: int = payload.get("settings_org_id", 0)  # type: ignore[assignment]

        facility_contexts: dict[DomainPrimaryKeyType, FacilityScenarioContext] = {}
        all_shifts: list[Shift] = []
        for fac_id_str, ctx_raw in raw_ctxs.items():
            fac_id = int(fac_id_str)
            config = _config_from_dict(ctx_raw["config"])
            tz = config.tz
            shifts = [_shift_from_dict(s, tz) for s in ctx_raw["shifts"]]
            all_shifts.extend(shifts)
            mandates = (
                _mandates_from_dict(ctx_raw["min_mandates"])
                if ctx_raw.get("min_mandates")
                else MinMandates(
                    min_rn_hprd=config.default_hprd_rn,
                    min_lpn_hprd=config.default_hprd_lpn,
                    min_cna_hprd=config.default_hprd_cna,
                    min_total_hprd=config.default_hprd_total,
                    min_staff_per_shift_rn=1,
                    min_staff_per_shift_lpn=0,
                    min_staff_per_shift_cna=2,
                )
            )
            facility_contexts[fac_id] = FacilityScenarioContext(
                facility_id=fac_id,
                shifts=shifts,
                config=config,
                min_mandates=mandates,
                optimization_settings=settings,
                default_hprd_rn=ctx_raw.get("default_hprd_rn", config.default_hprd_rn),
                default_hprd_cna=ctx_raw.get(
                    "default_hprd_cna", config.default_hprd_cna
                ),
                default_hprd_total=ctx_raw.get(
                    "default_hprd_total", config.default_hprd_total
                ),
            )

        employees = [_employee_from_dict(e) for e in raw_emps]

        nurses_by_shift: dict[ShiftKey, list[NurseProfile]] = {}
        for key_str, nurse_list in raw_nurses.items():
            parts = key_str.split(":", 1)
            if len(parts) == 2:
                shift_key = ShiftKey(int(parts[0]), int(parts[1]))
                nurses_by_shift[shift_key] = [_nurse_from_dict(n) for n in nurse_list]

        hprd_requirements: dict[
            DomainPrimaryKeyType, HprdShiftNurseRequirementHolder
        ] = {}
        for fac_id_str, req_raw in raw_hprd.items():
            fac_id = int(fac_id_str)
            if fac_id not in facility_contexts:
                continue
            ctx = facility_contexts[fac_id]
            holder = HprdShiftNurseRequirementHolder(
                [s.shift_id for s in ctx.shifts],
                [HprdEnforcedRole.RN, HprdEnforcedRole.LPN, HprdEnforcedRole.CNA],
            )
            for shift_idx, row in enumerate(req_raw.get("values", [])):
                for role_idx, value in enumerate(row):
                    if role_idx < 3:
                        shift_id = ctx.shifts[shift_idx].shift_id
                        holder[shift_id, list(HprdEnforcedRole)[role_idx]] = float(
                            value
                        )
            hprd_requirements[fac_id] = holder

        accumulated_hours = {int(k): float(v) for k, v in raw_hours.items()}

        compensation_records: dict[DomainPrimaryKeyType, StaffCompensationRecord] = {
            int(k): _comp_from_dict(v)
            for k, v in raw_comp.items()
            if isinstance(v, dict)
        }

        return SnapshotScenarioDataProvider(
            org_id=org_id,
            facility_contexts=facility_contexts,
            employees=employees,
            nurses_by_shift=nurses_by_shift,
            hprd_requirements=hprd_requirements,
            accumulated_hours=accumulated_hours,
            compensation=compensation_records,
            optimization_settings=settings,
        )
