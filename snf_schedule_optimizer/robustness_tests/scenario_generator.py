import random
from dataclasses import dataclass
from typing import *

import pendulum

from snf_schedule_optimizer.data_models import *


@dataclass(frozen=True)
class SimulateFacilityScenarioParams:
    """Defines a simulated facility scenario for robustness testing."""
    cna_base_wage: float
    agency_multiplier: float
    turnover_rate: float  # e.g., 0.2 for 20% annual turnover


def generate_simulated_nurses(simulation_params: SimulateFacilityScenarioParams) -> List[NurseProfile]:
    """Creates a mock staff roster reflecting the facility's profile and turnover risk."""
    roster = []
    for i in range(100):  # Mock 100 nurses/CNAs
        is_ot_risk = random.random() < simulation_params.turnover_rate  # Higher turnover means more unstable staff

        roster.append(
            NurseProfile(
                employee_id=f"N_{i}",
                role=random.choice([NurseRole.RN, NurseRole.LPN, NurseRole.CNA]),
                hourly_cost_base=simulation_params.cna_base_wage,
                ot_multiplier=simulation_params.agency_multiplier if is_ot_risk else 1.5,
                available_hours_weekly=40,
                is_agency=is_ot_risk and random.random() < 0.2,  # Mock a small percent as agency
                skills=['Wound Care'] if random.random() < 0.3 else []
            )
        )
    return roster


def generate_simulated_acuity(stress_params: StressTestParameters) -> List[ResidentAcuity]:
    """Creates acuity records reflecting a stressed clinical demand."""
    residents = []
    # Base population size
    base_count = 100 * (1.0 + stress_params.admission_surge_factor)

    for i in range(int(base_count)):
        # Stress Test: Increase the likelihood of high-cost residents
        high_acuity_prob = 0.15 * (1.0 + stress_params.high_acuity_mix_increase)

        acuity = 15 if random.random() < high_acuity_prob else 5  # High vs Low score

        residents.append(
            ResidentAcuity(
                resident_id=f"R_{i}",
                unit_id=random.choice(['A', 'B']),
                census_day=pendulum.now(pendulum.UTC),
                pt_score_gg=acuity,
                nta_score=random.randint(1, 10),
                clinical_category=random.choice(['Rehab', 'LTC'])
            )
        )
    return residents
