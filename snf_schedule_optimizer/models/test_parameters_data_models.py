from dataclasses import dataclass
import numpy as np
from typing import *


@dataclass(frozen=True)
class FacilityParameters:
    """Parameters that are STABLE ACROSS TIME but VARY ACROSS FACILITIES."""
    # 1. Supply/Compliance Configuration
    facility_id: str
    shift_structure: Dict[str, Tuple[str, str]]  # e.g., {'Day': ('07:00', '15:00')}
    base_cna_hprd_mandate: float = 2.5  # Minimum target HPRD for CNAs (CMS/State benchmark)
    cna_base_wage: float = 18.00
    agency_multiplier: float = 2.2  # Agency cost multiplier (220% of base)

    # 2. Staffing Constraints
    nurse_fatigue_rule: int = 10  # Max hours worked before mandatory rest
    team_consistency_weight: float = 5.0  # Weight for minimizing team changes (soft constraint)


@dataclass(frozen=True)
class PerShiftStressTestParameters:
    """each field represents a stress test variable that is known after schedule occurs, and not known at scheduling time."""
    # 1. Demand/Acuity Variability (Clinical Stress)
    admission_surge_factor: float  # Multiplier for unexpected admissions (e.g., 1.0 to 1.5)
    high_acuity_mix_increase: float  # Percentage increase in residents with high-NTA/high-GG scores
    staff_call_out_rate: float  # Probability of staff calling out on a given shift

    # 2. Financial/Operational Pressure
    # overtime_shift_count_increase: int  # How many more shifts require overtime in this scenario
    # budget_variance_max: float  # Max allowed variance before cost constraint is violated

    def __str__(self) -> str:
        fields = [
            ("admission_surge_factor", self.admission_surge_factor),
            ("high_acuity_mix_increase", self.high_acuity_mix_increase),
            ("staff_call_out_rate", self.staff_call_out_rate),
            # ("overtime_shift_count_increase", self.overtime_shift_count_increase),
            # ("budget_variance_max", self.budget_variance_max),
        ]
        return "_".join(f"{k}_{v}" for k, v in fields)


StressTestParameterName: TypeAlias = Literal[
    "admission_surge_factor",
    "high_acuity_mix_increase",
    "staff_call_out_rate",
    # "overtime_shift_count_increase",
    # "budget_variance_max"
]
