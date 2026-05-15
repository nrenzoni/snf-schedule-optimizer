from contextlib import suppress
from dataclasses import dataclass

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    HprdEnforcedRole,
    Shift,
    ShiftKey,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider


@dataclass
class ShiftGapAlert:
    shift_key: ShiftKey
    gap_type: str
    role: str | None
    severity: str
    detail: str


class GapDetectionProcessor:
    async def detect_gaps(
        self,
        shift_assignments: dict[ShiftKey, list[int]],
        shifts: list[Shift],
        data_provider: IScenarioDataProvider,
        facility_contexts: dict[int, FacilityScenarioContext],
    ) -> list[ShiftGapAlert]:
        alerts: list[ShiftGapAlert] = []

        facility_shifts: dict[DomainPrimaryKeyType, list[Shift]] = {}
        for shift in shifts:
            facility_shifts.setdefault(shift.facility_id, []).append(shift)

        for shift in shifts:
            assigned = shift_assignments.get(shift.shift_key, [])
            if not assigned:
                alerts.append(
                    ShiftGapAlert(
                        shift_key=shift.shift_key,
                        gap_type="UNCOVERED",
                        role=None,
                        severity="CRITICAL",
                        detail=f"Shift {shift.shift_id} at facility {shift.facility_id} "
                        f"starting {shift.shift_start_dt} has zero nurses assigned",
                    )
                )

        for shift in shifts:
            assigned = shift_assignments.get(shift.shift_key, [])
            if not assigned:
                continue

            context = facility_contexts.get(shift.facility_id)
            if context is None:
                continue

            try:
                hprd_holder = await data_provider.get_hprd_requirements_for_facility(
                    shift.facility_id
                )
            except Exception:
                continue

            rn_required: float = 0.0
            with suppress(ValueError, KeyError):
                rn_required = hprd_holder[shift.shift_id, HprdEnforcedRole.RN]

            if rn_required > 0:
                assigned_employees = []
                for emp_id in assigned:
                    emp = await data_provider.get_employee_by_id(emp_id)
                    if emp is not None:
                        assigned_employees.append(emp)

                has_rn = any(
                    "RN" in (emp.job_title or "") for emp in assigned_employees
                )
                if not has_rn:
                    alerts.append(
                        ShiftGapAlert(
                            shift_key=shift.shift_key,
                            gap_type="SKILL_GAP",
                            role="RN",
                            severity="WARNING",
                            detail=f"Shift {shift.shift_id} at facility "
                            f"{shift.facility_id} requires RN but none assigned",
                        )
                    )

            lpn_required: float = 0.0
            with suppress(ValueError, KeyError):
                lpn_required = hprd_holder[shift.shift_id, HprdEnforcedRole.LPN]
            if lpn_required > 0:
                assigned_employees = []
                for emp_id in assigned:
                    emp = await data_provider.get_employee_by_id(emp_id)
                    if emp is not None:
                        assigned_employees.append(emp)

                has_lpn = any(
                    "LPN" in (emp.job_title or "") for emp in assigned_employees
                )
                if not has_lpn:
                    alerts.append(
                        ShiftGapAlert(
                            shift_key=shift.shift_key,
                            gap_type="SKILL_GAP",
                            role="LPN",
                            severity="WARNING",
                            detail=f"Shift {shift.shift_id} at facility "
                            f"{shift.facility_id} requires LPN but none assigned",
                        )
                    )

        for facility_id, fac_shifts in facility_shifts.items():
            sorted_shifts = sorted(fac_shifts, key=lambda s: s.shift_start_dt)
            for i in range(len(sorted_shifts) - 1):
                current = sorted_shifts[i]
                next_shift = sorted_shifts[i + 1]
                if current.shift_start_dt.date() != next_shift.shift_start_dt.date():
                    continue
                gap_minutes = (
                    next_shift.shift_start_dt - current.shift_end_dt
                ).in_minutes()
                if gap_minutes > 30:
                    alerts.append(
                        ShiftGapAlert(
                            shift_key=current.shift_key,
                            gap_type="CONSECUTIVE_GAP",
                            role=None,
                            severity="WARNING",
                            detail=f"Gap of {gap_minutes:.0f} min between shift "
                            f"{current.shift_id} and {next_shift.shift_id} "
                            f"at facility {facility_id} on "
                            f"{current.shift_start_dt.date()}",
                        )
                    )

        return alerts
