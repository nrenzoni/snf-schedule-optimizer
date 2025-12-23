import random

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    NurseProfile,
    PreferenceType,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
    StaffShiftPreference,
)
from snf_schedule_optimizer.models.scenario_models import (
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
            start_date=whenever.ZonedDateTime(2025, 1, 1, tz="America/New_York")
        )
        self.facility_id = "FAC_1"
        self.org_id = "ORG_1"

    # --- Configuration Methods ---
    def with_workforce(self, cfg: WorkforceConfig) -> "ScenarioBuilder":
        self.workforce_cfg = cfg
        return self

    def with_time(self, cfg: TimeConfig) -> "ScenarioBuilder":
        self.time_cfg = cfg
        return self

    def with_history(self, cfg: HistoryConfig) -> "ScenarioBuilder":
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
            preference_penalties={},
            acuity_data=[],
        )

    def _generate_shifts(self) -> list[Shift]:
        shifts = []
        current_dt = self.time_cfg.start_date

        for day in range(self.time_cfg.num_days):
            for s_num in range(1, self.time_cfg.shifts_per_day + 1):
                # Simple logic to stagger start times
                start_hour = 7 + ((s_num - 1) * 8)  # 7, 15, 23
                shift_start = current_dt.add(days=day).replace(
                    hour=start_hour % 24, minute=0, second=0
                )
                shift_end = shift_start.add(hours=self.time_cfg.shift_duration_hours)

                is_day = 7 <= shift_start.hour < 15

                shifts.append(
                    Shift(
                        org_id=self.org_id,
                        shift_key=ShiftKey(
                            facility_id=self.facility_id,
                            shift_id=f"S_D{day}_N{s_num}",
                        ),
                        shift_number=s_num,
                        day_shift=is_day,
                        day_of_week=shift_start.date().day_of_week(),
                        shift_start_dt=shift_start,
                        shift_end_dt=shift_end,
                        unit_id="U1",
                        is_scheduled=True,
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

            # Use seeded RNG for ID generation instead of non-deterministic uuid.uuid4()
            rand_hex = f"{self.rng.getrandbits(24):06x}"
            emp_id = f"{role}_{'AGY' if is_agency else 'STF'}_{rand_hex}"

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

            # Check configuration probabilities

            # Chance for Specific Day Off
            if self.rng.random() < self.pref_cfg.prob_specific_day_off:
                # Pick a random day (0=Monday to 6=Sunday)
                day_off = self.rng.randint(0, 6)
                prefs.append(
                    StaffShiftPreference(
                        preference_type=PreferenceType.SPECIFIC_DAY_OFF,
                        specific_value=str(day_off),
                        penalty_weight=5.0,  # Standard weight
                        is_hard_block=False,
                    )
                )

            # Chance for No Weekends
            if self.rng.random() < self.pref_cfg.prob_no_weekends:
                prefs.append(
                    StaffShiftPreference(
                        preference_type=PreferenceType.WEEKEND_OFF,
                        specific_value=None,
                        penalty_weight=10.0,
                        is_hard_block=False,
                    )
                )

            # 4. Objects
            emps.append(
                Employee(
                    employee_id=emp_id,
                    name=f"{role} User {i}",
                    job_title=role,
                    hire_date=self.time_cfg.start_date.subtract(days=100).date(),
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


class ScenarioDebugPrinter:
    """Helper to visualize generated scenarios for debugging/demos."""

    @staticmethod
    def print_summary(result: ScenarioResult) -> None:
        print("\n" + "=" * 60)
        print("SCENARIO DEBUG SUMMARY")
        print("=" * 60)

        # 1. Shifts
        print(f"\n[SHIFTS] Total: {len(result.shifts)}")
        if result.shifts:
            sorted_shifts = sorted(result.shifts, key=lambda s: s.shift_start_dt)
            start = sorted_shifts[0].shift_start_dt
            end = sorted_shifts[-1].shift_end_dt
            print(f"  Time Range:   {start.format_iso()} to {end.format_iso()}")
            duration_days = (end - start).in_days_of_24h()
            print(f"  Duration:     {duration_days} days")

            day_shifts = sum(1 for s in result.shifts if s.day_shift)
            night_shifts = len(result.shifts) - day_shifts
            print(f"  Distribution: Day ({day_shifts}) | Night ({night_shifts})")

        # 2. Workforce
        total_emps = len(result.employees)
        print(f"\n[WORKFORCE] Total Employees: {total_emps}")

        # Build maps for lookup
        fin_map = {r.employee_id: r for r in result.financials}
        by_role: dict[str, list[Employee]] = {}
        for emp in result.employees:
            by_role.setdefault(emp.job_title, []).append(emp)

        for role, emps in by_role.items():
            count = len(emps)
            agency_count = 0
            avg_rate = 0.0

            for e in emps:
                rec = fin_map.get(e.employee_id)
                if rec:
                    if rec.is_agency:
                        agency_count += 1
                    avg_rate += rec.base_rate_effective

            if count > 0:
                avg_rate /= count

            print(f"  {role}: {count}")
            print(f"    - Staff:    {count - agency_count}")
            print(f"    - Agency:   {agency_count} ({agency_count / count * 100:.1f}%)")
            print(f"    - Avg Rate: ${avg_rate:.2f}/hr")

        # 3. History Accumulation
        print("\n[HISTORY / OT RISK STATUS]")
        ot_risk = 0
        fresh = 0
        mid = 0

        for hrs in result.history_map.values():
            if hrs == 0:
                fresh += 1
            elif hrs > 30:
                ot_risk += 1
            else:
                mid += 1

        print(f"  Fresh (0 hrs):       {fresh:<3} ({fresh / total_emps * 100:.1f}%)")
        print(f"  Mid-Week (>0, <30):  {mid:<3}")
        print(
            f"  OT Risk (>30 hrs):   {ot_risk:<3} ({ot_risk / total_emps * 100:.1f}%)"
        )

        # 4. Preferences
        print("\n[PREFERENCES]")
        pref_count = 0
        for n in result.nurses:
            if n.shift_custom_preferences:
                pref_count += 1
        pct_pref = (pref_count / total_emps * 100) if total_emps > 0 else 0
        print(f"  Nurses with Preferences: {pref_count} ({pct_pref:.1f}%)")

        print("=" * 60 + "\n")
