import abc
import random
from uuid import uuid4
import pendulum
import dataclasses
from dataclasses import dataclass

from snf_schedule_optimizer.models import *


@dataclass(frozen=True)
class SimulateFacilityScenarioParams:
    """Defines a simulated facility scenario for robustness testing."""
    rn_base_wage: float
    lpn_base_wage: float
    cna_base_wage: float
    agency_multiplier: float
    turnover_rate: float  # e.g., 0.2 for 20% annual turnover


class INurseSimulateGenerator(abc.ABC):
    @abc.abstractmethod
    def generate_nurse_profiles(self) -> List[NurseProfile]:
        pass


class HardcodedNurseSimulateGenerator(INurseSimulateGenerator):
    def __init__(self, nurse_profiles: List[NurseProfile]):
        self.nurse_profiles = nurse_profiles

    def generate_nurse_profiles(self) -> List[NurseProfile]:
        """Returns the predefined list of nurse profiles."""
        return self.nurse_profiles


class DefaultNurseSimulateGenerator(INurseSimulateGenerator):
    def __init__(
            self,
            n_employees: int,
            simulation_params: SimulateFacilityScenarioParams,
            rng: random.Random,
    ):
        self.n_employees = n_employees
        self.simulation_params = simulation_params
        self.rng = rng

    def generate_nurse_profiles(self) -> List[NurseProfile]:
        """Creates a mock staff roster reflecting the facility's profile and turnover risk."""
        employees_compensation = self.generate_employees_and_compensation()
        return self._generate_nurse_profiles(employees_compensation)

    def generate_employees_and_compensation(self) -> List[Tuple[Employee, StaffCompensationRecord]]:
        """
        Creates base Employee records and their current StaffCompensationRecords.
        Replaces the old generate_nurse_profiles logic.
        """
        roster_data = []
        now = pendulum.now()

        for i in range(self.n_employees):
            employee_id = str(uuid4())
            is_ot_risk = self.rng.random() < self.simulation_params.turnover_rate

            # Map NurseRole choices to Job Titles
            job_title = self.rng.choice(["RN", "LPN", "CNA"])
            is_agency = self.rng.random() < 0.10

            if job_title == "RN":
                cost_base = self.simulation_params.rn_base_wage
            elif job_title == "LPN":
                cost_base = self.simulation_params.lpn_base_wage
            else:  # CNA
                cost_base = self.simulation_params.cna_base_wage

            if is_agency:
                cost_base *= self.simulation_params.agency_multiplier

            # 1. Create Employee (HR Identity)
            employee = Employee(
                employee_id=employee_id,
                name=f"Nurse {i}",
                job_title=job_title,
                hire_date=now.subtract(days=self.rng.randint(30, 1000)),
            )

            # 2. Create StaffCompensationRecord (Cost Data)
            compensation = StaffCompensationRecord(
                employee_id=employee_id,
                base_rate_effective=cost_base,
                # Use a specific multiplier, 1.5 is standard FLSA
                ot_multiplier=1.5,
                effective_start_date=now.date(),
                is_agency=is_agency,
            )

            roster_data.append((employee, compensation))

        return roster_data

    def _generate_nurse_profiles(
            self,
            employee_compensation_data:
            List[Tuple[Employee, StaffCompensationRecord]],
    ) -> List[NurseProfile]:
        """
        Generates scheduling-specific NurseProfiles using the base cost data.
        """
        profiles = []
        for employee, compensation in employee_compensation_data:
            profiles.append(
                NurseProfile(
                    employee_id=employee.employee_id,
                    # base_rate=compensation.base_rate_effective,  # Copy rate
                    # ot_multiplier=compensation.ot_multiplier,
                    available_hours_weekly=40,  # Assuming standard availability
                    # is_agency=compensation.is_agency,
                    skills=['Wound Care'] if self.rng.random() < 0.3 else [],
                    shift_custom_preferences=[],
                )
            )
        return profiles


class WrappedWithPreferencesNurseSimulateGenerator(INurseSimulateGenerator):
    def __init__(
            self,
            inner_simulator: INurseSimulateGenerator,
            simulation_params: SimulateFacilityScenarioParams,
            rng_seed: int,
    ):
        self.inner_simulator = inner_simulator
        self.simulation_params = simulation_params
        self.rng = random.Random(rng_seed)

    def generate_nurse_profiles(self) -> List[NurseProfile]:
        """Creates a mock staff roster reflecting the facility's profile and turnover risk, with preferences."""
        roster = []
        for i, nurse_profile in enumerate(self.inner_simulator.generate_nurse_profiles()):
            preferences = []
            if self.rng.random() < 0.5:
                preferences.append(
                    StaffShiftPreference(
                        preference_type=PreferenceType.SPECIFIC_DAY_OFF,
                        specific_value=str(pendulum.WeekDay.MONDAY),
                        penalty_weight=2.0,
                        is_hard_block=False
                    )
                )
                nurse_profile_updated = dataclasses.replace(nurse_profile, shift_custom_preferences=preferences)
                roster.append(nurse_profile_updated)

        return roster
