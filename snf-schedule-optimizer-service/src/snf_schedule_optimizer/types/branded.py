"""Branded types for domain identifiers to prevent accidental swapping."""
from typing import NewType

EmployeeId = NewType("EmployeeId", int)
FacilityId = NewType("FacilityId", int)
ScheduleId = NewType("ScheduleId", int)
OrgId = NewType("OrgId", int)
ShiftId = NewType("ShiftId", int)
