import json
from decimal import Decimal

import pytest

from snf_schedule_optimizer.utils.serialization import AppJSONEncoder


def _dumps(obj: object) -> str:
    return json.dumps(obj, cls=AppJSONEncoder)


class TestAppJSONEncoder:
    def test_decimal_converted_to_float(self) -> None:
        result = _dumps({"rate": Decimal("25.50")})
        assert result == '{"rate": 25.5}'

    def test_decimal_in_nested_dict(self) -> None:
        payload = {
            "compensation": {
                "employee_id": 1,
                "base_rate_effective": Decimal("30.00"),
            }
        }
        result = _dumps(payload)
        parsed = json.loads(result)
        assert parsed["compensation"]["base_rate_effective"] == 30.0

    def test_decimal_in_list(self) -> None:
        result = _dumps([Decimal("1.0"), Decimal("2.5")])
        assert result == "[1.0, 2.5]"

    def test_mixed_payload_with_decimal(self) -> None:
        payload = {
            "employees": [{"id": 1, "rate": Decimal("18.75")}],
            "settings": {"use_ml": True, "penalty": 2.5},
        }
        result = _dumps(payload)
        parsed = json.loads(result)
        assert parsed["employees"][0]["rate"] == 18.75
        assert parsed["settings"]["penalty"] == 2.5

    def test_normal_types_unchanged(self) -> None:
        payload = {
            "string": "hello",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
        }
        result = _dumps(payload)
        parsed = json.loads(result)
        assert parsed == payload

    def test_unknown_type_raises_type_error(self) -> None:
        class Unknown:
            pass

        with pytest.raises(TypeError):
            _dumps({"obj": Unknown()})
