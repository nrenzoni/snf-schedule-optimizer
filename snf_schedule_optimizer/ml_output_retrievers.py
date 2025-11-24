import abc

from snf_schedule_optimizer.models import Shift
from snf_schedule_optimizer.optimization_engine import MlModelOutputs


class IMLModelOutputsRetriever(abc.ABC):
    @abc.abstractmethod
    def get_model_outputs(
            self,
            shift: Shift,
    ) -> MlModelOutputs:
        pass


class MLModelOutputsRetrieverImpl(IMLModelOutputsRetriever):
    def get_model_outputs(
            self,
            shift: Shift,
    ) -> MlModelOutputs:
        return MlModelOutputs(
            turnover_risk_scores={},
            shift_call_out_forecast=0.0,
            unit_acuity_stress={},
            team_compatibility_scores={}
        )
