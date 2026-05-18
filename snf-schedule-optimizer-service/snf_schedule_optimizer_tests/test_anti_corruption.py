from snf_schedule_optimizer.domain.anti_corruption.validators import (
    ProtoToDomainValidator,
)
from snf_schedule_optimizer.models import OptimizationSettings


def test_validates_rest_period_less_than_shift_length() -> None:
    validator_obj = ProtoToDomainValidator()
    settings = OptimizationSettings(min_rest_period=15, max_shift_length=10.0)
    result = validator_obj.validate_optimization_settings(settings)
    assert not result.is_valid
    assert any("min_rest_period" in e for e in result.errors)


def test_validates_non_negative_buffer() -> None:
    validator_obj = ProtoToDomainValidator()
    settings = OptimizationSettings(buffer_threshold=-5)
    result = validator_obj.validate_optimization_settings(settings)
    assert not result.is_valid


def test_valid_settings_pass() -> None:
    validator_obj = ProtoToDomainValidator()
    settings = OptimizationSettings(
        min_rest_period=10, max_shift_length=12.0, buffer_threshold=10
    )
    result = validator_obj.validate_optimization_settings(settings)
    assert result.is_valid
