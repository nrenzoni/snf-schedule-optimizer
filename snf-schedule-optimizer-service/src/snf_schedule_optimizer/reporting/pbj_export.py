import csv
from typing import Any

import whenever

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    ShiftKey,
)
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider

PBJ_HEADERS = [
    "STAFFING_HOURS",
    "EMPLID",
    "WORK_DATE",
    "HRS_WORKED",
    "JOB_TTL_CD",
    "PAY_TYPE",
    "FACILITY_ID",
]


class PbjReportGenerator:
    async def generate_pbj_report(
        self,
        shift_assignments: dict[ShiftKey, list[int]],
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
        reporting_period_start: whenever.Date,
        reporting_period_end: whenever.Date,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for shift_key, emp_ids in shift_assignments.items():
            if shift_key.facility_id != facility_id:
                continue

            shift = None
            for s in data_provider.get_all_shifts():
                if s.shift_key == shift_key:
                    shift = s
                    break
            if shift is None:
                continue

            shift_date = shift.shift_start_dt.date()
            if shift_date < reporting_period_start or shift_date > reporting_period_end:
                continue

            for emp_id in emp_ids:
                employee = await data_provider.get_employee_by_id(emp_id)
                if employee is None:
                    continue

                rows.append(
                    {
                        "STAFFING_HOURS": "Y",
                        "EMPLID": str(emp_id),
                        "WORK_DATE": shift_date.format_iso(),
                        "HRS_WORKED": shift.duration_hours,
                        "JOB_TTL_CD": employee.job_title,
                        "PAY_TYPE": "REG",
                        "FACILITY_ID": str(facility_id),
                    }
                )

        return rows

    def generate_pbj_csv(
        self,
        report_rows: list[dict[str, Any]],
        filepath: str,
    ) -> None:
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=PBJ_HEADERS)
            writer.writeheader()
            writer.writerows(report_rows)
