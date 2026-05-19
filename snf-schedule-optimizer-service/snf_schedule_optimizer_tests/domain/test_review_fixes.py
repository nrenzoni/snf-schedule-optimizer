"""Tests for recommended fixes and improvements."""

from __future__ import annotations

from typing import Any

from snf_schedule_optimizer.domain.exceptions import (
    DataIntegrityError,
    SecurityError,
)
from snf_schedule_optimizer.domain.hr.interfaces import IStaffCompensationRepo
from snf_schedule_optimizer.models import OptimizationRun
from snf_schedule_optimizer.optimizer.snapshot_provider import (
    _config_from_dict,
    _SnapshotCompensationService,
)


def test_optimization_run_has_cancel_requested_at() -> None:
    run = OptimizationRun(
        run_id="test-run-1",
        org_id=1,
        facility_id=1,
        schedule_id=1,
        schedule_lineage_id=1,
        base_schedule_version=1,
        cancel_requested_at="2025-01-15T00:00:00Z",
    )
    assert run.cancel_requested_at == "2025-01-15T00:00:00Z"


def test_optimization_run_cancel_requested_at_defaults_to_none() -> None:
    run = OptimizationRun(
        run_id="test-run-1",
        org_id=1,
        facility_id=1,
        schedule_id=1,
        schedule_lineage_id=1,
        base_schedule_version=1,
    )
    assert run.cancel_requested_at is None


def test_security_error_is_domain_exception() -> None:
    err = SecurityError("test message")
    assert isinstance(err, Exception)
    assert str(err) == "test message"


def test_data_integrity_error_is_domain_exception() -> None:
    err = DataIntegrityError("test message")
    assert isinstance(err, Exception)
    assert str(err) == "test message"


def test_snapshot_config_pay_period_reads_from_payload() -> None:
    payload: dict[str, Any] = {
        "org_id": 1,
        "facility_id": 2,
        "shifts_per_day": 3,
        "overtime_threshold_hours_per_week": 40,
        "start_of_work_week_day": "MONDAY",
        "start_of_work_day_time": "07:00:00",
        "pay_period": 21,
        "weekend_multiplier": 1.5,
        "night_shift_multiplier": 2.0,
        "tz": "America/New_York",
        "default_hprd_rn": 0.5,
        "default_hprd_lpn": 0.0,
        "default_hprd_cna": 2.4,
        "default_hprd_total": 3.5,
        "min_rest_hours_between_shifts": 10.0,
        "max_consecutive_work_days": 5,
        "max_total_hours_per_pay_period": 80.0,
    }
    config = _config_from_dict(payload)
    assert config.pay_period.in_months_days() == (0, 21)


def test_snapshot_config_pay_period_defaults_to_14_days() -> None:
    payload: dict[str, Any] = {
        "org_id": 1,
        "facility_id": 2,
        "shifts_per_day": 3,
        "overtime_threshold_hours_per_week": 40,
        "start_of_work_week_day": "MONDAY",
        "start_of_work_day_time": "07:00:00",
        "weekend_multiplier": 1.5,
        "night_shift_multiplier": 2.0,
        "tz": "America/New_York",
    }
    config = _config_from_dict(payload)
    assert config.pay_period.in_months_days() == (0, 14)


def test_consecutive_days_limit_strategy_is_importable() -> None:
    # Inline import intentional: this test validates the import path itself.
    from snf_schedule_optimizer.optimizer.strategies.constraints import (
        ConsecutiveDaysLimitConstraintStrategy,
    )

    strat = ConsecutiveDaysLimitConstraintStrategy()
    assert strat is not None


def test_snapshot_compensation_service_implements_interface() -> None:
    svc = _SnapshotCompensationService({})
    assert isinstance(svc, IStaffCompensationRepo)
