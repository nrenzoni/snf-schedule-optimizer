import enum
from dataclasses import dataclass
from typing import Dict, List, Optional

from snf_schedule_optimizer.models import FacilityConfig, MinMandates, Schedule, Shift


class InfeasibilityReason(enum.StrEnum):
    NO_AVAILABLE_NURSES = (
        "No available nurses to cover required role"  # includes hard blocks
    )
    OTHER = "Other infeasibility reason"


@dataclass(frozen=True)
class ShiftCostBreakdown:
    base_wage: float  # Hourly Rate * Hours
    overtime_premium: float  # The extra 0.5x portion
    statutory_burden: float  # Taxes (FICA, SUI, FUTA)
    benefits_burden: float  # Health, 401k, PTO Accrual
    shift_differentials: float  # NOC, Weekend
    incentive_bonuses: float  # Pick-up, Holiday, Sign-on

    @property
    def total_optimization_cost(self) -> float:
        """The single number the solver uses to minimize cost."""
        return (
            self.base_wage
            + self.overtime_premium
            + self.statutory_burden
            + self.benefits_burden
            + self.shift_differentials
            + self.incentive_bonuses
        )


@dataclass(frozen=True)
class InfeasibilityReasonResult:
    reason: InfeasibilityReason
    details: Optional[str] = None


@dataclass(frozen=True)
class ScheduleOptimizationResults:
    success: bool
    optimal_schedule: Optional[Schedule]
    constraint_slacks: Optional[Dict[str, float]]
    infeasibility_reason: Optional[InfeasibilityReasonResult]
