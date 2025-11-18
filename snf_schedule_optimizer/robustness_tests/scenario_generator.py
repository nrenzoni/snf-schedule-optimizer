import abc
import dataclasses
import random
from dataclasses import dataclass
from typing import *

import pendulum

from snf_schedule_optimizer.data_models import *


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
    def generate_nurse_profiles(self, simulation_params: SimulateFacilityScenarioParams) -> List[NurseProfile]:
        pass


class DefaultNurseSimulateGenerator(INurseSimulateGenerator):
    def __init__(
            self,
            n_nurses: int,
            seed: int,
    ):
        self.n_nurses = n_nurses
        self.rng = random.Random(seed)

    def generate_nurse_profiles(self, simulation_params: SimulateFacilityScenarioParams) -> List[NurseProfile]:
        """Creates a mock staff roster reflecting the facility's profile and turnover risk."""
        roster = []
        for i in range(self.n_nurses):
            is_ot_risk = self.rng.random() < simulation_params.turnover_rate  # Higher turnover means more unstable staff

            role = self.rng.choice([NurseRole.RN, NurseRole.LPN, NurseRole.CNA])
            is_agency = self.rng.random() < 0.10

            if role == NurseRole.RN:
                cost_base = simulation_params.rn_base_wage
            elif role == NurseRole.LPN:
                cost_base = simulation_params.lpn_base_wage
            elif role == NurseRole.CNA:
                cost_base = simulation_params.cna_base_wage
            else:
                raise ValueError(f"Unknown NurseRole: {role}")

            if is_agency:
                cost_base *= simulation_params.agency_multiplier

            roster.append(
                NurseProfile(
                    employee_id=f"N_{i}",
                    role=role,
                    hourly_cost_base=cost_base,
                    ot_multiplier=simulation_params.agency_multiplier if is_ot_risk else 1.5,
                    available_hours_weekly=40,
                    is_agency=is_agency,
                    skills=['Wound Care'] if self.rng.random() < 0.3 else []
                )
            )

        return roster


class WrappedWithPreferencesNurseSimulateGenerator(INurseSimulateGenerator):
    def __init__(
            self,
            inner_simulator: INurseSimulateGenerator,
            rng_seed: int,
    ):
        self.inner_simulator = inner_simulator
        self.rng = random.Random(rng_seed)

    def generate_nurse_profiles(self, simulation_params: SimulateFacilityScenarioParams) -> List[NurseProfile]:
        """Creates a mock staff roster reflecting the facility's profile and turnover risk, with preferences."""
        roster = []
        for i, nurse_profile in enumerate(self.inner_simulator.generate_nurse_profiles(simulation_params)):
            preferences = []
            if self.rng.random() < 0.5:
                preferences.append(
                    StaffPreference(
                        preference_type=PreferenceType.SPECIFIC_DAY_OFF,
                        specific_day=pendulum.WeekDay.MONDAY,
                        penalty_weight=2.0,
                        is_hard_block=False
                    )
                )
                nurse_profile_updated = dataclasses.replace(nurse_profile, custom_preferences=preferences)
                roster.append(nurse_profile_updated)

        return roster


def generate_simulated_acuity(
        stress_params: PerShiftStressTestParameters,
        rng: random.Random,
) -> List[ResidentAcuity]:
    """Creates acuity records reflecting a stressed clinical demand."""
    residents = []
    # Base population size
    base_count = 100 * (1.0 + stress_params.admission_surge_factor)

    for i in range(int(base_count)):
        # Stress Test: Increase the likelihood of high-cost residents
        high_acuity_prob = 0.15 * (1.0 + stress_params.high_acuity_mix_increase)

        acuity = 15 if rng.random() < high_acuity_prob else 5  # High vs Low score

        residents.append(
            ResidentAcuity(
                resident_id=f"R_{i}",
                unit_id=rng.choice(['A', 'B']),
                census_day=pendulum.now(pendulum.UTC),
                pt_score_gg=acuity,
                nta_score=rng.randint(1, 10),
                clinical_category=rng.choice(['Rehab', 'LTC'])
            )
        )
    return residents
