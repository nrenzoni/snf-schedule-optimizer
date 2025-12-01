from __future__ import annotations

import random
import uuid
from typing import cast

import pendulum

from snf_schedule_optimizer.models import (
    Employee,
    NurseProfile,
    Shift,
    StaffCompensationRecord,
    StaffShiftPreference,
)

from .scenario_models import (
    HistoryConfig,
    PayBandConfig,
    PreferenceConfig,
    ScenarioResult,
    TimeConfig,
    WorkforceConfig,
)


class ScenarioBuilder:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

        # Defaults
        self.workforce_cfg = WorkforceConfig()
        self.pay_bands = {
            "low": PayBandConfig(25.0, 15.0),
            "med": PayBandConfig(32.0, 18.0),
            "high": PayBandConfig(40.0, 22.0),
        }
        self.history_cfg = HistoryConfig()
        self.pref_cfg = PreferenceConfig()
        self.time_cfg = TimeConfig(
            start_date=pendulum.datetime(2025, 1, 1, tz="America/New_York")
        )
        self.facility_id = "FAC_1"
        self.org_id = "ORG_1"

    # --- Configuration Methods ---
    def with_workforce(self, cfg: WorkforceConfig) -> ScenarioBuilder:
        self.workforce_cfg = cfg
        return self

    def with_time(self, cfg: TimeConfig) -> ScenarioBuilder:
        self.time_cfg = cfg
        return self

    def with_history(self, cfg: HistoryConfig) -> ScenarioBuilder:
        self.history_cfg = cfg
        return self

    # --- Generation Logic ---

    def build(self) -> ScenarioResult:
        shifts = self._generate_shifts()
        employees, nurses, financials, history = self._generate_workforce()

        return ScenarioResult(
            shifts=shifts,
            employees=employees,
            nurses=nurses,
            financials=financials,
            history_map=history,
            preference_penalties={},  # Can be populated if using the Fake Processor logic
        )

    def _generate_shifts(self) -> list[Shift]:
        shifts = []
        current_dt = self.time_cfg.start_date

        for day in range(self.time_cfg.num_days):
            for s_num in range(1, self.time_cfg.shifts_per_day + 1):
                # Simple logic to stagger start times
                start_hour = 7 + ((s_num - 1) * 8)  # 7, 15, 23
                shift_start = current_dt.add(days=day).set(
                    hour=start_hour % 24, minute=0, second=0
                )
                shift_end = shift_start.add(hours=self.time_cfg.shift_duration_hours)

                is_day = 7 <= shift_start.hour < 15

                shifts.append(
                    Shift(
                        org_id=self.org_id,
                        facility_id=self.facility_id,
                        shift_id=f"S_D{day}_N{s_num}",
                        shift_number=s_num,
                        day_shift=is_day,
                        day_of_week=shift_start.day_of_week,
                        shift_start_dt=shift_start,
                        shift_end_dt=shift_end,
                        timezone=cast(
                            pendulum.Timezone, self.time_cfg.start_date.timezone
                        ),
                    )
                )
        return shifts

    def _generate_workforce(
        self,
    ) -> tuple[
        list[Employee],
        list[NurseProfile],
        list[StaffCompensationRecord],
        dict[str, float],
    ]:
        employees: list[Employee] = []
        nurses: list[NurseProfile] = []
        financials: list[StaffCompensationRecord] = []
        history_map: dict[str, float] = {}

        # Generate RNs
        self._batch_create_staff(
            "RN",
            self.workforce_cfg.count_rn,
            self.workforce_cfg.percent_agency_rn,
            employees,
            nurses,
            financials,
            history_map,
        )

        # Generate CNAs
        self._batch_create_staff(
            "CNA",
            self.workforce_cfg.count_cna,
            self.workforce_cfg.percent_agency_cna,
            employees,
            nurses,
            financials,
            history_map,
        )

        return employees, nurses, financials, history_map

    def _batch_create_staff(
        self,
        role: str,
        count: int,
        agency_pct: float,
        emps: list[Employee],
        nurses: list[NurseProfile],
        fins: list[StaffCompensationRecord],
        hist: dict[str, float],
    ) -> None:
        for i in range(count):
            is_agency = self.rng.random() < agency_pct
            emp_id = f"{role}_{'AGY' if is_agency else 'STF'}_{uuid.uuid4().hex[:6]}"

            # 1. Pay Band
            band_roll = self.rng.random()
            if band_roll < self.workforce_cfg.prob_pay_low:
                band = self.pay_bands["low"]
            elif band_roll < (
                self.workforce_cfg.prob_pay_low + self.workforce_cfg.prob_pay_med
            ):
                band = self.pay_bands["med"]
            else:
                band = self.pay_bands["high"]

            base_rate = band.base_rate_rn if role == "RN" else band.base_rate_cna
            if is_agency:
                base_rate *= band.agency_premium_multiplier

            # 2. History (OT Context)
            hist_roll = self.rng.random()
            if hist_roll < self.history_cfg.prob_zero_hours:
                hours = 0.0
            elif hist_roll < (
                self.history_cfg.prob_zero_hours + self.history_cfg.prob_half_shift
            ):
                hours = 4.0
            elif hist_roll < (
                self.history_cfg.prob_zero_hours
                + self.history_cfg.prob_half_shift
                + self.history_cfg.prob_half_way_to_ot
            ):
                hours = 20.0
            else:
                hours = 38.0  # Near OT

            hist[emp_id] = hours

            # 3. Preferences
            prefs: list[StaffShiftPreference] = []
            pref_roll = self.rng.random()
            # Logic to add specific preference objects based on config...
            # (Simplified for brevity)

            # 4. Objects
            emps.append(
                Employee(
                    employee_id=emp_id,
                    name=f"{role} User {i}",
                    job_title=role,
                    hire_date=self.time_cfg.start_date.subtract(days=100),
                )
            )

            fins.append(
                StaffCompensationRecord(
                    employee_id=emp_id,
                    base_rate_effective=base_rate,
                    ot_multiplier=1.0 if is_agency else 1.5,
                    is_agency=is_agency,
                    effective_start_date=self.time_cfg.start_date.date(),
                )
            )

            nurses.append(
                NurseProfile(
                    employee_id=emp_id,
                    available_hours_weekly=60,  # Available
                    skills=[role],
                    shift_custom_preferences=prefs,
                )
            )
