from __future__ import annotations

from datetime import date, timedelta

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
    EmployeeStateSnapshot,
    LockedAssignment,
    Shift,
    WorkedHistoryFact,
)


class EmployeeStateSnapshotBuilder:
    def build(
        self,
        employee_ids: list[EmployeeIdType],
        worked_history: list[WorkedHistoryFact],
        locked_assignments: list[LockedAssignment],
        shifts_by_key: dict[DomainPrimaryKeyType, Shift],
    ) -> dict[DomainPrimaryKeyType, EmployeeStateSnapshot]:
        worked_by_emp: dict[EmployeeIdType, list[WorkedHistoryFact]] = {}
        for fact in worked_history:
            worked_by_emp.setdefault(fact.employee_id, []).append(fact)

        locked_by_emp: dict[EmployeeIdType, list[LockedAssignment]] = {}
        for la in locked_assignments:
            locked_by_emp.setdefault(la.employee_id, []).append(la)

        result: dict[DomainPrimaryKeyType, EmployeeStateSnapshot] = {}
        for emp_id in employee_ids:
            facts = sorted(worked_by_emp.get(emp_id, []), key=lambda f: f.shift_start)
            worked_hours_week = sum(f.duration_hours for f in facts)
            consecutive_days = self._count_consecutive_days(facts)
            last_shift_end = facts[-1].shift_end if facts else None

            locked_hours = 0.0
            for la in locked_by_emp.get(emp_id, []):
                shift = shifts_by_key.get(la.shift_key.shift_id)
                if shift is not None:
                    locked_hours += shift.duration_hours

            result[emp_id] = EmployeeStateSnapshot(
                employee_id=emp_id,
                worked_hours_day=0.0,
                worked_hours_week=worked_hours_week,
                worked_hours_pay_period=worked_hours_week + locked_hours,
                consecutive_days_worked=consecutive_days,
                last_shift_end=last_shift_end,
            )

        return result

    @staticmethod
    def _count_consecutive_days(facts: list[WorkedHistoryFact]) -> int:
        if not facts:
            return 0

        dates = sorted(
            {date.fromisoformat(f.shift_start[:10]) for f in facts}, reverse=True
        )
        streak = 1
        for i in range(len(dates) - 1):
            if (dates[i] - dates[i + 1]) == timedelta(days=1):
                streak += 1
            else:
                break
        return streak
