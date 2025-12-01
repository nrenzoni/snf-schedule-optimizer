from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostBreakdown:
    """
    Accumulator class for reporting aggregated costs (e.g., per facility or per role).
    """

    regular_cost: float = 0.0
    overtime_cost: float = 0.0
    agency_spend: float = 0.0
    bonuses: float = 0.0
    total_hours: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.regular_cost + self.overtime_cost + self.agency_spend + self.bonuses

    def __add__(self, other: CostBreakdown) -> CostBreakdown:
        return CostBreakdown(
            self.regular_cost + other.regular_cost,
            self.overtime_cost + other.overtime_cost,
            self.agency_spend + other.agency_spend,
            self.bonuses + other.bonuses,
            self.total_hours + other.total_hours,
        )


@dataclass
class ScheduleFinancialReport:
    """The final report structure."""

    total_enterprise_cost: float
    breakdown_per_facility: dict[str, CostBreakdown]
    breakdown_per_role: dict[str, CostBreakdown]

    # Helpful for debugging solver results
    infeasibility_reason: str | None = None
