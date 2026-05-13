import abc

from snf_schedule_optimizer.models import MlModelOutputs, Shift


class IMLModelOutputsRepo(abc.ABC):
    @abc.abstractmethod
    def get_model_outputs(
        self,
        shift: Shift,
    ) -> MlModelOutputs:
        pass


class MLModelOutputsRepo(IMLModelOutputsRepo):
    def get_model_outputs(
        self,
        shift: Shift,
    ) -> MlModelOutputs:
        stressed_unit = shift.unit_id or 0
        shift_risk = 0.2 if not shift.day_shift else 0.05
        return MlModelOutputs(
            turnover_risk_scores={},
            shift_call_out_forecast=shift_risk,
            unit_acuity_stress={stressed_unit: 0.15 if shift.day_shift else 0.25},
            team_compatibility_scores={},
        )
