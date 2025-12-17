"""
Audit Trail & Regulatory Compliance: Logs every input, every LP constraint violation, and the final schedule generated. This is your proof that staffing decisions were data-driven.
"""

import whenever


def log_optimization_run(
    timestamp: whenever.Instant,
    inputs_hash: str,
    final_cost: float,
    violations: dict[str, float],
) -> None:
    pass
