# class SliceReason(StrEnum):
#     OVERTIME = "OVERTIME"
#     DIFFERENTIAL = "DIFFERENTIAL"


# class NurseShiftHoursStateTracker:
#     """
#     Tracks the shift hours and their components (regular time vs. overtime) for a specific nurse.
#     """
#
#     def __init__(
#             self,
#             nurse_profile: Employee,
#             overtime_calculator: IEmployeeWorkHistoryService,
#     ):
#         self.nurse_profile = nurse_profile
#         self.nurse_shift_history: Dict[
#             Shift, List[WorkedShiftSegment]] = {}  # Maps Shift to its NurseShiftHourComponents
#         self.overtime_calculator = overtime_calculator
#
#     def record_shift_and_get_hour_components(self, shift: Shift) -> List[WorkedShiftSegment]:
#         if shift in self.nurse_shift_history:
#             return self.nurse_shift_history[shift]
#
#         self.nurse_shift_history[shift] = []
#         remaining_non_ot_hours = self.overtime_calculator.get_remaining_non_ot_hours(
#             employee=self.nurse_profile,
#             current_shift=shift,
#             history=self.nurse_shift_history,
#             ot_rules=
#         )
#
#         if remaining_non_ot_hours <= 0:
#             # Entire shift is OT
#             hour_component = WorkedShiftSegment(
#                 parent_shift=shift,
#                 start_time=shift.shift_start_dt,
#                 end_time=shift.shift_end_dt,
#                 slice_reasons=[SliceReason.OVERTIME]
#             )
#             self.nurse_shift_history[shift].append(
#                 hour_component
#             )
#             return [hour_component]
#
#         if shift.duration_hours <= remaining_non_ot_hours:
#             # Entire shift is regular time
#             component = WorkedShiftSegment(
#                 parent_shift=shift,
#                 start_time=shift.shift_start_dt,
#                 end_time=shift.shift_end_dt,
#                 slice_reasons=None
#             )
#             self.nurse_shift_history[shift].append(
#                 component
#             )
#             return [component]
#
#         remaining_non_ot_duration = pendulum.Duration(hours=remaining_non_ot_hours)
#
#         components = []
#
#         # Split shift into regular time and OT
#         regular_end_time = shift.shift_start_dt + remaining_non_ot_duration
#
#         components.append(
#             WorkedShiftSegment(
#                 parent_shift=shift,
#                 start_time=shift.shift_start_dt,
#                 end_time=regular_end_time,
#                 slice_reasons=None
#             )
#         )
#
#         components.append(
#             WorkedShiftSegment(
#                 parent_shift=shift,
#                 start_time=regular_end_time,
#                 end_time=shift.shift_end_dt,
#                 slice_reasons=[SliceReason.OVERTIME]
#             )
#         )
#
#         self.nurse_shift_history[shift].extend(components)
#
#         return components
#
#     def _get_shifts_before(self, current_shift: Shift) -> List[WorkedShiftSegment]:
#         """Get all shift components before the current shift's start time."""
#         shifts_before = []
#         for shift, components in self.nurse_shift_history.items():
#             if shift.shift_start_dt < current_shift.shift_start_dt:
#                 shifts_before.extend(components)
#             else:
#                 break
#         return shifts_before
#
#     def _calculate_all_shifts_total_hours(self) -> float:
#         """Calculate total hours worked in the last N days before current shift."""
#         total_hours = 0.0
#
#         for shift, components in self.nurse_shift_history.items():
#             total_hours += shift.duration_hours
#
#         return total_hours


# class AllNurseShiftHoursTracker:
#     def __init__(self, overtime_calculator: IOvertimeCalculator):
#         self.overtime_calculator = overtime_calculator
#         self.nurse_trackers: Dict[str, NurseShiftHoursStateTracker] = {}
#
#     def record_shift_and_get_hour_components(
#             self,
#             nurse_profile: NurseProfile,
#             shift: Shift,
#     ) -> List[WorkedShiftSegment]:
#         tracker = self._get_nurse_shift_hours_tracker(nurse_profile)
#         return tracker.record_shift_and_get_hour_components(shift)
#
#     def _get_nurse_shift_hours_tracker(
#             self,
#             nurse_profile: NurseProfile,
#     ) -> NurseShiftHoursStateTracker:
#         if nurse_profile.employee_id not in self.nurse_trackers:
#             self.nurse_trackers[nurse_profile.employee_id] = NurseShiftHoursStateTracker(
#                 nurse_profile=nurse_profile,
#                 overtime_calculator=self.overtime_calculator,
#             )
#         return self.nurse_trackers[nurse_profile.employee_id]
