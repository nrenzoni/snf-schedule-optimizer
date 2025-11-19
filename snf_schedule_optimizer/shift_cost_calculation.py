import abc
import dataclasses
from typing import List, Optional

from snf_schedule_optimizer.data_models import Differential, DifferentialType, FacilityConfig, NurseProfile, Shift
from snf_schedule_optimizer.datetime_utils import is_weekend


class INurseDifferentialRetriever(abc.ABC):
    @abc.abstractmethod
    def get_differentials(self, nurse: NurseProfile, shift: Shift) -> List[Differential]:
        pass


class NurseDifferentialRetrieverImpl(INurseDifferentialRetriever):
    def __init__(self, facility_config: FacilityConfig):
        self.facility_config = facility_config

    def get_differentials(self, nurse: NurseProfile, shift: Shift) -> List[Differential]:
        if is_weekend(shift.day_of_week):
            return [
                Differential(
                    name="Weekend Shift Differential",
                    type=DifferentialType.MULTIPLIER,
                    multiplier=self.facility_config.weekend_multiplier,
                )
            ]
        if not shift.day_shift:
            return [
                Differential(
                    name="Night Shift Differential",
                    type=DifferentialType.MULTIPLIER,
                    multiplier=self.facility_config.night_shift_multiplier,
                )
            ]
        return []


class IShiftCostCalculator(abc.ABC):
    @abc.abstractmethod
    def __call__(self, nurse: NurseProfile, shift: Shift) -> float:
        pass


class ShiftCostCalculatorImpl(IShiftCostCalculator):
    def __init__(
            self,
            nurse_differential_retriever: INurseDifferentialRetriever,
    ):
        self.nurse_differential_retriever = nurse_differential_retriever

    def __call__(self, nurse: NurseProfile, shift: Shift) -> float:
        """
        Calculates the true financial cost (Base + Premium) of assigning this nurse
        to this specific shift.
        """
        # Simplification: Assume all shifts are 8 hours.
        base_cost = nurse.hourly_cost_base * shift.duration_hours

        differentials = self.nurse_differential_retriever.get_differentials(nurse, shift)

        differential_additions = 0.0
        for differential in differentials:
            if differential.type == DifferentialType.MULTIPLIER:
                assert differential.multiplier is not None
                differential_additions += base_cost * (differential.multiplier - 1.0)
            elif differential.type == DifferentialType.FLAT:
                assert differential.flat is not None
                base_cost += differential.flat
            else:
                raise ValueError(f"Unknown DifferentialType: {differential.type}")

        return base_cost + differential_additions
