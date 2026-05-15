import random

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    EmployeeIdType,
    FacilityConfig,
    NurseProfile,
    PreferenceType,
    ResidentAcuity,
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
        self._next_employee_id = 1
        self.unit_ids = (101, 102, 103, 104)

        # Defaults
        self.workforce_cfg = WorkforceConfig(
            count_rn=42,
            count_lpn=38,
            count_cna=96,
            percent_agency_rn=0.16,
            percent_agency_lpn=0.18,
            percent_agency_cna=0.24,
        )
        self.pay_bands = {
            "low": PayBandConfig(34.0, 18.5),
            "med": PayBandConfig(42.0, 22.0),
            "high": PayBandConfig(51.0, 26.5),
        }
        self.history_cfg = HistoryConfig(
            prob_zero_hours=0.35,
            prob_half_shift=0.10,
            prob_half_way_to_ot=0.35,
            prob_near_ot=0.20,
        )
        self.pref_cfg = PreferenceConfig(
            prob_no_preference=0.35,
            prob_no_nights=0.18,
            prob_no_weekends=0.20,
            prob_specific_day_off=0.25,
        )
        self.time_cfg = TimeConfig(
            start_date=whenever.ZonedDateTime(2025, 1, 1, tz="America/New_York")
        )
        self.facility_id = 1
        self.org_id = 1

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
        # 1. Generate core scheduling rules
        facility_configs = [self._generate_facility_config()]

        # 2. Generate operational data
        shifts = self._generate_shifts()
        employees, nurses, financials, history = self._generate_workforce()
        acuity_data = self._generate_acuity_data(shifts)

        return ScenarioResult(
            shifts=shifts,
            employees=employees,
            nurses=nurses,
            financials=financials,
            history_map=history,
            facility_configs=facility_configs,
            preference_penalties={},
            acuity_data=acuity_data,
        )

    def _generate_facility_config(self) -> FacilityConfig:
        """Generates the static configuration for the demo facility."""
        return FacilityConfig(
            org_id=self.org_id,
            facility_id=self.facility_id,
            tz="America/New_York",
            shifts_per_day=self.time_cfg.shifts_per_day,
            overtime_threshold_hours_per_week=40,
            # Start week on Monday (1)
            start_of_work_week_day=whenever.Weekday(1),
            # Shifts typically start at 7 AM
            start_of_work_day_time=whenever.Time(7, 0, 0),
            # Standard 1-week pay period
            pay_period=whenever.DateDelta(weeks=1),
            weekend_multiplier=1.15,
            night_shift_multiplier=1.10,
            default_hprd_rn=0.55,
            default_hprd_cna=2.65,
            default_hprd_total=3.75,
        )

    def _generate_shifts(self) -> list[Shift]:
        shifts = []
        current_dt = self.time_cfg.start_date

        idx = 0
        for day in range(self.time_cfg.num_days):
            for unit_id in self.unit_ids:
                for s_num in range(1, self.time_cfg.shifts_per_day + 1):
                    # SNFs commonly run 7a/3p/11p eight-hour tours across care units.
                    start_hour = 7 + ((s_num - 1) * 8)  # 7, 15, 23
                    shift_start = current_dt.add(days=day).replace(
                        hour=start_hour % 24, minute=0, second=0
                    )
                    shift_end = shift_start.add(
                        hours=self.time_cfg.shift_duration_hours
                    )

                    is_day = 7 <= shift_start.hour < 15

                    shifts.append(
                        Shift(
                            org_id=self.org_id,
                            shift_key=ShiftKey(
                                facility_id=self.facility_id,
                                shift_id=idx,
                            ),
                            shift_number=s_num,
                            day_shift=is_day,
                            day_of_week=shift_start.date().day_of_week(),
                            shift_start_dt=shift_start,
                            shift_end_dt=shift_end,
                            unit_id=unit_id,
                            is_scheduled=True,
                        )
                    )
                    idx += 1
        return shifts

    def _generate_workforce(
        self,
    ) -> tuple[
        list[Employee],
        list[NurseProfile],
        list[StaffCompensationRecord],
        dict[EmployeeIdType, float],
    ]:
        employees: list[Employee] = []
        nurses: list[NurseProfile] = []
        financials: list[StaffCompensationRecord] = []
        history_map: dict[EmployeeIdType, float] = {}

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

        self._batch_create_staff(
            "LPN",
            self.workforce_cfg.count_lpn,
            self.workforce_cfg.percent_agency_lpn,
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

    def _generate_acuity_data(self, shifts: list[Shift]) -> list[ResidentAcuity]:
        day_unit_counts: dict[tuple[whenever.Date, int], int] = {}
        for shift in shifts:
            if shift.unit_id is None:
                continue
            key = (shift.shift_start_dt.date(), shift.unit_id)
            if key in day_unit_counts:
                continue
            base_by_unit = {
                101: 34,
                102: 48,
                103: 32,
                104: 24,
            }
            variance = self.rng.randint(-2, 3)
            day_unit_counts[key] = max(
                18, base_by_unit.get(shift.unit_id, 30) + variance
            )

        acuity_data: list[ResidentAcuity] = []
        resident_id = 1
        for (census_day, unit_id), census in day_unit_counts.items():
            for _ in range(census):
                high_acuity = self.rng.random() < 0.22
                acuity_data.append(
                    ResidentAcuity(
                        resident_id=(self.facility_id * 100000) + resident_id,
                        unit_id=unit_id,
                        census_day=whenever.ZonedDateTime(
                            census_day.year,
                            census_day.month,
                            census_day.day,
                            12,
                            0,
                            0,
                            tz=self.time_cfg.start_date.tz,
                        ),
                        pt_score_gg=15 if high_acuity else self.rng.randint(5, 11),
                        nta_score=8 if high_acuity else self.rng.randint(1, 5),
                        clinical_category=(
                            "High Acuity Rehab"
                            if high_acuity
                            else "Standard Skilled Nursing"
                        ),
                    )
                )
                resident_id += 1
        return acuity_data

    def _batch_create_staff(
        self,
        role: str,
        count: int,
        agency_pct: float,
        emps: list[Employee],
        nurses: list[NurseProfile],
        fins: list[StaffCompensationRecord],
        hist: dict[EmployeeIdType, float],
    ) -> None:
        for i in range(count):
            is_agency = self.rng.random() < agency_pct

            # Use seeded RNG for ID generation instead of non-deterministic uuid.uuid4()
            # rand_hex = f"{self.rng.getrandbits(24):06x}"
            emp_id = (self.facility_id * 100000) + self._next_employee_id
            self._next_employee_id += 1

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

            if role == "RN":
                base_rate = band.base_rate_rn
            elif role == "LPN":
                base_rate = round((band.base_rate_rn + band.base_rate_cna) / 2, 2)
            else:
                base_rate = band.base_rate_cna
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
                day_off = self.rng.randint(1, 7)
                prefs.append(
                    StaffShiftPreference(
                        preference_type=PreferenceType.SPECIFIC_DAY_OFF,
                        specific_value=str(day_off),
                        penalty_weight=5.0,  # Standard weight
                        is_hard_block=False,
                    )
                )

            if self.rng.random() < self.pref_cfg.prob_no_nights:
                prefs.append(
                    StaffShiftPreference(
                        preference_type=PreferenceType.DAY_SHIFT_PREFERENCE,
                        specific_value=None,
                        penalty_weight=7.0,
                        is_hard_block=False,
                    )
                )

            if self.rng.random() < 0.35:
                prefs.append(
                    StaffShiftPreference(
                        preference_type=PreferenceType.UNIT_PREFERENCE,
                        specific_value=str(self.rng.choice(self.unit_ids)),
                        penalty_weight=4.0,
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
                    name=self._staff_name(role, i, is_agency),
                    job_title=role,
                    hire_date=self.time_cfg.start_date.subtract(
                        days=self.rng.randint(45, 3650)
                    ).date(),
                )
            )

            fins.append(
                StaffCompensationRecord(
                    employee_id=emp_id,
                    base_rate_effective=base_rate,
                    ot_multiplier=1.5,
                    is_agency=is_agency,
                    effective_start_date=self.time_cfg.start_date.date(),
                )
            )

            nurses.append(
                NurseProfile(
                    employee_id=emp_id,
                    available_hours_weekly=60,  # Available
                    skills=self._skills_for_role(role),
                    shift_custom_preferences=prefs,
                )
            )

    def _staff_name(self, role: str, index: int, is_agency: bool) -> str:
        first_names = [
            "Alicia",
            "Marcus",
            "Danielle",
            "Jorge",
            "Priya",
            "Nina",
            "Caleb",
            "Monique",
            "Tessa",
            "Andre",
            "Mei",
            "Elena",
            "Samira",
            "Darius",
            "Hannah",
            "Keisha",
        ]
        last_names = [
            "Bennett",
            "Rivera",
            "Patel",
            "Thompson",
            "Nguyen",
            "Carter",
            "Brooks",
            "Santos",
            "Miller",
            "Jackson",
            "Kim",
            "Garcia",
            "Reed",
            "Morgan",
            "Owens",
            "Hayes",
        ]
        first = first_names[(index + self.rng.randint(0, 7)) % len(first_names)]
        last = last_names[(index * 3 + self.rng.randint(0, 5)) % len(last_names)]
        suffix = " Agency" if is_agency else ""
        return f"{first} {last}, {role}{suffix}"

    @staticmethod
    def _skills_for_role(role: str) -> list[str]:
        if role == "RN":
            return ["RN", "Charge", "IV Therapy", "Wound Care"]
        if role == "LPN":
            return ["LPN", "Medication Pass", "Wound Care"]
        return ["CNA", "Restorative", "Memory Care"]


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
