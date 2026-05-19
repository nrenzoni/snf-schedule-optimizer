"""Shared ID decoding utilities used by both handler and mapper modules."""

from returns.result import Failure, Result, Success, safe

from snf_schedule_optimizer.infrastructure.sqid_converter import IIdObfuscator


@safe
def _decode(obfuscator: IIdObfuscator, val: str) -> int:
    return int(obfuscator.decode(val))


def get_internal_id(
    obfuscator: IIdObfuscator,
    val: str,
    label: str,
    required: bool = True,
) -> Result[int | None, str]:
    if not val:
        return Success(None) if not required else Failure(f"Missing {label} ID.")
    return _decode(obfuscator, val).alt(lambda _: f"Invalid {label} ID format.")
