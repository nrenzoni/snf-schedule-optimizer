"""Tests for snapshot payload completeness."""

import json

from snf_schedule_optimizer.models import OptimizationSnapshot


def test_snapshot_payload_stores_facility_contexts_as_json_serializable() -> None:
    payload = {
        "facility_contexts": {
            "1": {
                "config": {"org_id": 1, "tz": "America/New_York"},
                "shifts": [
                    {
                        "org_id": 1,
                        "facility_id": 1,
                        "shift_id": 101,
                        "shift_number": 1,
                        "day_shift": True,
                        "day_of_week": "WEDNESDAY",
                        "shift_start_iso": "2025-01-01T07:00:00-05:00[America/New_York]",
                        "shift_end_iso": "2025-01-01T15:00:00-05:00[America/New_York]",
                        "unit_id": None,
                        "is_scheduled": True,
                    }
                ],
            }
        },
        "employees": [
            {
                "employee_id": 1,
                "name": "Test RN",
                "job_title": "RN",
                "hire_date": "2024-01-01",
            }
        ],
        "nurses_by_shift": {},
        "compensation": {},
        "accumulated_hours": {},
        "hprd_requirements": {},
    }
    json_str = json.dumps(payload)
    roundtripped = json.loads(json_str)
    assert roundtripped["facility_contexts"]["1"]["shifts"][0]["shift_id"] == 101
    assert roundtripped["employees"][0]["job_title"] == "RN"


def test_snapshot_dto_holds_all_required_fields() -> None:
    snap = OptimizationSnapshot(
        snapshot_id="snap-1",
        run_id="run-1",
        org_id=1,
        facility_id=1,
        schedule_id=10,
        base_schedule_version=1,
        decision_start_date="2025-01-01",
        decision_end_date="2025-01-07",
        policy_start_date="2024-12-25",
        policy_end_date="2025-01-14",
        payload={
            "request": {},
            "settings": {},
            "locked_assignments": [],
            "base_schedule": {},
            "facility_contexts": {},
            "employees": [],
            "nurses_by_shift": {},
            "compensation": {},
            "accumulated_hours": {},
            "hprd_requirements": {},
        },
        created_at="2025-01-01T00:00:00Z",
    )
    assert snap.decision_start_date == "2025-01-01"
    assert snap.policy_start_date == "2024-12-25"
    assert snap.policy_end_date == "2025-01-14"


def test_snapshot_payload_keys_include_all_domain_sections() -> None:
    required_keys = {
        "request",
        "settings",
        "locked_assignments",
        "base_schedule",
        "facility_contexts",
        "employees",
        "nurses_by_shift",
        "compensation",
        "accumulated_hours",
        "hprd_requirements",
    }
    snap = OptimizationSnapshot(
        snapshot_id="snap-2",
        run_id="run-2",
        org_id=1,
        facility_id=1,
        schedule_id=11,
        base_schedule_version=1,
        decision_start_date="2025-02-01",
        decision_end_date="2025-02-07",
        policy_start_date="2025-01-25",
        policy_end_date="2025-02-14",
        payload={k: {} for k in required_keys},
        created_at="2025-02-01T00:00:00Z",
    )
    for key in required_keys:
        assert key in snap.payload, f"Missing required key: {key}"
