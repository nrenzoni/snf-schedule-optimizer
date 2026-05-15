"""Tests that optimization snapshots include history data, locks, and domain sections."""

from snf_schedule_optimizer.service.scheduling.optimization_run_worker import (
    _serialize_config,
    _serialize_employee,
    _serialize_shift,
)

from ..support.factories import make_employee, make_facility_config, make_shift


def test_serialize_shift_includes_all_required_keys() -> None:
    shift = make_shift(facility_id=1, shift_id=101)
    serialized = _serialize_shift(shift)
    assert serialized["facility_id"] == 1
    assert serialized["shift_id"] == 101
    assert serialized["org_id"] == 1
    assert "shift_start_iso" in serialized
    assert "shift_end_iso" in serialized
    assert serialized["day_shift"] is True
    assert serialized["is_scheduled"] is True
    assert "day_of_week" in serialized
    assert serialized["unit_id"] is None


def test_serialize_employee_includes_hire_date() -> None:
    emp = make_employee(employee_id=42, job_title="RN")
    serialized = _serialize_employee(emp)
    assert serialized["employee_id"] == 42
    assert serialized["name"] == "Test RN"
    assert serialized["job_title"] == "RN"
    assert "hire_date" in serialized


def test_serialize_config_includes_all_domain_fields() -> None:
    config = make_facility_config(facility_id=1, night_shift_multiplier=2.0)
    serialized = _serialize_config(config)
    assert serialized["facility_id"] == 1
    assert serialized["night_shift_multiplier"] == 2.0
    assert "overtime_threshold_hours_per_week" in serialized
    assert "start_of_work_week_day" in serialized
    assert "start_of_work_day_time" in serialized
    assert "max_consecutive_work_days" in serialized
    assert "min_rest_hours_between_shifts" in serialized
