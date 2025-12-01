"""
Acuity-to-Workload Conversion: Encapsulates the logic that converts raw MDS scores into required labor minutes (the "I" in HPRD). This is where you insert the GNN output later.
"""

from snf_schedule_optimizer.models import ResidentAcuity


def calculate_required_minutes(resident_acuity: ResidentAcuity) -> None:
    pass
