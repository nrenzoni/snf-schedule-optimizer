"""Tests for error handling in the scheduler handler's ID decode functions."""

import pytest
from returns.result import Failure, Success

from snf_schedule_optimizer.api.grpc._id_utils import get_internal_id
from snf_schedule_optimizer.api.grpc.scheduler_handler import (
    SchedulingServiceHandler,
)
from snf_schedule_optimizer.api.grpc.scheduler_mappers import (
    decode_patch,
    decode_staged_patches,
)
from snf_schedule_optimizer.generated.scheduling.v1 import scheduling_pb2
from snf_schedule_optimizer.infrastructure.sqid_converter import IdObfuscator


@pytest.fixture
def obfuscator() -> IdObfuscator:
    return IdObfuscator()


@pytest.fixture
def handler(obfuscator: IdObfuscator) -> SchedulingServiceHandler:
    return SchedulingServiceHandler(
        engine=None,  # type: ignore[arg-type]
        session_factory=None,  # type: ignore[arg-type]
        id_obfuscator=obfuscator,
    )


class TestDecodeOrgAndFacility:
    def test_returns_failure_for_invalid_org_id(
        self, handler: SchedulingServiceHandler
    ) -> None:
        result = handler._decode_org_and_facility("not-a-valid-id", "")
        assert isinstance(result, Failure)

    def test_returns_failure_for_invalid_facility_id(
        self, handler: SchedulingServiceHandler
    ) -> None:
        org_id = handler.id_obfuscator.encode(1)
        result = handler._decode_org_and_facility(org_id, "not-a-valid-id")
        assert isinstance(result, Failure)

    def test_returns_success_for_valid_ids(
        self, handler: SchedulingServiceHandler
    ) -> None:
        org_id = handler.id_obfuscator.encode(1)
        fac_id = handler.id_obfuscator.encode(2)
        result = handler._decode_org_and_facility(org_id, fac_id)
        assert isinstance(result, Success)
        org, fac = result.unwrap()
        assert org == 1
        assert fac == 2

    def test_returns_success_with_none_for_missing_facility(
        self, handler: SchedulingServiceHandler
    ) -> None:
        org_id = handler.id_obfuscator.encode(1)
        result = handler._decode_org_and_facility(org_id, "")
        assert isinstance(result, Success)
        org, fac = result.unwrap()
        assert org == 1
        assert fac is None

    def test_returns_failure_for_empty_org_id(
        self, handler: SchedulingServiceHandler
    ) -> None:
        result = handler._decode_org_and_facility("", "")
        assert isinstance(result, Failure)


class TestDecodePatch:
    def test_returns_failure_for_invalid_employee_id(
        self, obfuscator: IdObfuscator
    ) -> None:
        proto_patch = scheduling_pb2.StagedSchedulePatch(
            patch_id="p1",
            employee_id="not-a-valid-employee-id",
        )
        result = decode_patch(obfuscator, proto_patch)
        assert isinstance(result, Failure)
        assert "Employee" in result.failure()

    def test_returns_failure_for_invalid_from_shift_id(
        self, obfuscator: IdObfuscator
    ) -> None:
        employee_id = obfuscator.encode(100)
        proto_patch = scheduling_pb2.StagedSchedulePatch(
            patch_id="p1",
            employee_id=employee_id,
            from_shift_id="not-a-valid-shift-id",
        )
        result = decode_patch(obfuscator, proto_patch)
        assert isinstance(result, Failure)
        assert "Shift" in result.failure()

    def test_returns_success_for_valid_patch(self, obfuscator: IdObfuscator) -> None:
        employee_id = obfuscator.encode(100)
        from_shift_id = obfuscator.encode(200)
        to_shift_id = obfuscator.encode(300)
        proto_patch = scheduling_pb2.StagedSchedulePatch(
            patch_id="p1",
            employee_id=employee_id,
            employee_name="Test Nurse",
            from_shift_id=from_shift_id,
            to_shift_id=to_shift_id,
            pinned=True,
            causes_overtime=True,
            total_cost=150.0,
            created_at="2025-01-01",
        )
        result = decode_patch(obfuscator, proto_patch)
        assert isinstance(result, Success)
        patch = result.unwrap()
        assert patch.patch_id == "p1"
        assert patch.employee_id == 100
        assert patch.employee_name == "Test Nurse"
        assert patch.from_shift_id == 200
        assert patch.to_shift_id == 300
        assert patch.pinned is True
        assert patch.causes_overtime is True
        assert patch.total_cost == 150.0

    def test_returns_success_with_none_for_missing_shift_ids(
        self, obfuscator: IdObfuscator
    ) -> None:
        employee_id = obfuscator.encode(100)
        proto_patch = scheduling_pb2.StagedSchedulePatch(
            patch_id="p1",
            employee_id=employee_id,
        )
        result = decode_patch(obfuscator, proto_patch)
        assert isinstance(result, Success)
        patch = result.unwrap()
        assert patch.from_shift_id is None
        assert patch.to_shift_id is None


class TestDecodeStagedPatches:
    def test_returns_first_failure(self, obfuscator: IdObfuscator) -> None:
        employee_id = obfuscator.encode(100)
        good_patch = scheduling_pb2.StagedSchedulePatch(
            patch_id="p1",
            employee_id=employee_id,
        )
        bad_patch = scheduling_pb2.StagedSchedulePatch(
            patch_id="p2",
            employee_id="not-valid",
        )
        result = decode_staged_patches(obfuscator, [good_patch, bad_patch])
        assert isinstance(result, Failure)
        assert "Employee" in result.failure()

    def test_returns_all_decoded_on_success(self, obfuscator: IdObfuscator) -> None:
        employee_id = obfuscator.encode(100)
        p1 = scheduling_pb2.StagedSchedulePatch(
            patch_id="p1",
            employee_id=employee_id,
        )
        p2 = scheduling_pb2.StagedSchedulePatch(
            patch_id="p2",
            employee_id=employee_id,
        )
        result = decode_staged_patches(obfuscator, [p1, p2])
        assert isinstance(result, Success)
        patches = result.unwrap()
        assert len(patches) == 2
        assert patches[0].patch_id == "p1"
        assert patches[1].patch_id == "p2"

    def test_empty_list_returns_empty_tuple(self, obfuscator: IdObfuscator) -> None:
        result = decode_staged_patches(obfuscator, [])
        assert isinstance(result, Success)
        assert result.unwrap() == ()


class TestGetInternalId:
    def test_returns_failure_for_missing_required_id(
        self, obfuscator: IdObfuscator
    ) -> None:
        result = get_internal_id(obfuscator, "", "Organization")
        assert isinstance(result, Failure)
        assert "Missing" in result.failure()

    def test_returns_failure_for_invalid_format(self, obfuscator: IdObfuscator) -> None:
        result = get_internal_id(obfuscator, "!!!invalid!!!", "Employee")
        assert isinstance(result, Failure)
        assert "Invalid" in result.failure()

    def test_returns_success_with_none_for_optional_empty(
        self, obfuscator: IdObfuscator
    ) -> None:
        result = get_internal_id(obfuscator, "", "Facility", required=False)
        assert isinstance(result, Success)
        assert result.unwrap() is None

    def test_returns_success_for_valid_id(self, obfuscator: IdObfuscator) -> None:
        encoded = obfuscator.encode(42)
        result = get_internal_id(obfuscator, encoded, "Shift")
        assert isinstance(result, Success)
        assert result.unwrap() == 42
