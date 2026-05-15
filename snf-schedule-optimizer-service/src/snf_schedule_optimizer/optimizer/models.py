import enum
from dataclasses import dataclass

from snf_schedule_optimizer.models import EmployeeIdType, Schedule


class InfeasibilityReason(enum.StrEnum):
    NO_AVAILABLE_NURSES = (
        "No available nurses to cover required role"  # includes hard blocks
    )
    OTHER = "Other infeasibility reason"


@dataclass(frozen=True)
class ShiftCostBreakdown:
    """
    Represents the calculated cost components for a SINGLE shift for a specific employee.
    """

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
    details: str | None = None


@dataclass(frozen=True)
class ScheduleOptimizationStats:
    """Performance and complexity statistics for the optimization run."""

    execution_time_ms: float
    total_variables: int
    total_constraints: int
    objective_value: float | None = None


@dataclass(frozen=True)
class ScheduleOptimizationResults:
    success: bool
    optimal_schedule: Schedule | None
    constraint_slacks: dict[str, float] | None
    infeasibility_reason: InfeasibilityReasonResult | None
    statistics: ScheduleOptimizationStats | None = None
    weekend_assignment_distribution: dict[EmployeeIdType, int] | None = None
    fairness_score: float | None = None
