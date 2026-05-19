import datetime
from decimal import Decimal

from snf_schedule_optimizer.sqlalchemy_models.staff_compensation_model import (
    StaffCompensationModel,
)


def test_to_domain_converts_base_rate_effective_decimal_to_float() -> None:
    model = StaffCompensationModel()
    model.employee_id = 1
    model.base_rate_effective = Decimal("25.50")  # type: ignore[assignment]
    model.ot_multiplier = 1.5
    model.is_agency = False
    model.effective_start_date = datetime.date(2024, 1, 1)
    model.effective_end_date = None
    model.union_contract_id = None
    model.pay_grade_or_step = None

    result = model.to_domain()

    assert isinstance(result.base_rate_effective, float)
    assert result.base_rate_effective == 25.5
    assert not isinstance(result.base_rate_effective, Decimal)
