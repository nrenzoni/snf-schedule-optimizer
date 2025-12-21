from __future__ import annotations

import abc

import pulp
from pulp import LpProblem

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    MlModelOutputs,
    NurseProfile,
    PreferenceWeights,
    Shift,
)
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    HprdShiftNurseRequirementHolder,
    LpNurseShiftVariableHolder,
)
from snf_schedule_optimizer.optimizer.models import InfeasibilityReasonResult
from snf_schedule_optimizer.services.hr.interfaces import IStaffCompensationRetriever


class INurseHardBlockChecker(abc.ABC):
    """
    Checks if the nurse has any hard block preferences for the given shift.
    """

    @abc.abstractmethod
    def check(
        self,
        nurse: NurseProfile,
        shift: Shift,
    ) -> bool:
        """
        Checks all HARD BLOCKERS (time off requests, skill gaps, max hours).
        :return: True if the nurse cannot be assigned to this shift due to hard blocks.
        """
        pass


class IIncentiveManager(abc.ABC):
    @abc.abstractmethod
    def calculate_incentives(
        self,
        shift: Shift,
        employee: Employee,
        base_rate: float,
    ) -> float:
        pass


class IPayModelStrategy(abc.ABC):
    """
    Encapsulates HOW we pay people.
    Examples:
    - WeeklyOvertimeStrategy (Uses Buckets)
    - DailyOvertimeStrategy (Uses Shift Coefficients)
    - ExemptSalaryStrategy (Fixed cost)
    """

    @abc.abstractmethod
    async def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        """Initialize buckets (h_reg, h_ot) if needed."""
        pass

    @abc.abstractmethod
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        """Apply math: sum(shifts) == reg + ot, or similar."""
        pass

    @abc.abstractmethod
    async def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> list[pulp.LpAffineExpression]:
        """Return the cost expression (e.g., h_reg * 20 + h_ot * 30)."""
        pass


class ILaborBurdenCalculator(abc.ABC):
    @abc.abstractmethod
    def calculate_burden(
        self,
        employee: Employee,
        base_cost: float,
    ) -> tuple[float, float]:
        """Returns (statutory_burden, benefits_burden)"""
        pass


class IFacilityScopedConstraintStrategy(abc.ABC):
    """
    Encapsulates HARD constraints.
    Examples:
    - MinHprdStrategy (Regulatory compliance)
    - UnionFatigueStrategy (Max consecutive days)
    - SkillMixStrategy (Must have 1 RN on floor)
    """

    @abc.abstractmethod
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: str,  # <--- Crucial
    ) -> InfeasibilityReasonResult | None:
        """
        Applies constraints directly to the 'problem'.
        Returns a reason if immediate infeasibility is detected (optional).
        """
        pass


# 1. Global Strategies (e.g., Pay, Overtime buckets)
class IGlobalConstraintStrategy(abc.ABC):
    @abc.abstractmethod
    def apply_global_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> InfeasibilityReasonResult | None:
        pass


class IObjectivePenaltyStrategy(abc.ABC):
    """
    Encapsulates SOFT preferences.
    Examples:
    - NursePreferenceStrategy (Day vs Night)
    - ContinuityStrategy (Keep same staff on same hall)
    - TurnoverRiskStrategy (Don't burnout high-risk staff)
    """

    @abc.abstractmethod
    async def get_penalty_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        weights: PreferenceWeights,
    ) -> list[pulp.LpAffineExpression]:
        """
        Returns a list of LpAffineExpression terms to be ADDED to the objective function.
        E.g. [ (x_1 * 50), (x_2 * 100) ]
        """
        pass


class IHprdRequirementCalculator(abc.ABC):
    @abc.abstractmethod
    async def calculate_requirements(
        self,
        context: FacilityScenarioContext,
    ) -> HprdShiftNurseRequirementHolder:
        pass


class IScenarioDataProvider(abc.ABC):
    """
    Defines the contract for providing data to strategies during a single
    optimization run. Implementations must handle lazy loading and caching within the run scope.
    """

    @abc.abstractmethod
    def get_org_id(self) -> str:
        """Returns the organization ID for this optimization run."""
        pass

    # --- Global Methods (Enterprise Level) ---

    @abc.abstractmethod
    async def get_all_employees(self) -> list[Employee]:
        """Returns all employees active for this scenario horizon."""
        pass

    @abc.abstractmethod
    async def get_employee_by_id(self, employee_id: str) -> Employee | None:
        """Returns a specific employee by ID."""
        pass

    @abc.abstractmethod
    def get_compensation_service(self) -> IStaffCompensationRetriever:
        """Provides access to financial data scoped for this run."""
        pass

    @abc.abstractmethod
    def get_all_shifts(self) -> list[Shift]:
        """Returns the list of shifts in the scenario."""
        pass

    # --- Facility-Scoped Methods ---

    @abc.abstractmethod
    def get_facility_ids(self) -> list[str]:
        """Returns list of facility IDs in this run."""
        pass

    @abc.abstractmethod
    def get_shifts_for_facility(self, facility_id: str) -> list[Shift]:
        pass

    @abc.abstractmethod
    async def get_nurses_for_shift(self, shift: Shift) -> list[NurseProfile]:
        """Returns available nurses for a specific shift, cached per shift."""
        pass

    @abc.abstractmethod
    async def get_hprd_requirements_for_facility(
        self,
        facility_id: str,
    ) -> HprdShiftNurseRequirementHolder:
        """Calculates (once) and returns HPRD requirements for all shifts."""
        pass

    @abc.abstractmethod
    def get_ml_model_outputs(self, shift: Shift) -> MlModelOutputs:
        pass

    @abc.abstractmethod
    async def get_accumulated_hours_for_pay_period(self, employee_id: str) -> float:
        """
        Returns the total hours worked by the employee in the current pay week
        BEFORE the optimization window starts.
        """
        pass

    @abc.abstractmethod
    def get_facility_config(self, facility_id: str) -> FacilityConfig:
        """Returns the configuration for the given facility."""
        pass
