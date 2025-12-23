# import whenever
# from that_depends import BaseContainer, providers
# from that_depends.providers import Singleton
#
# from snf_schedule_optimizer.infrastructure.composition import IRetrieversContainer
# from snf_schedule_optimizer.models import FacilityConfig, ShiftSpecificRequirements
# from snf_schedule_optimizer.persistence import FakeRawHistoryRepo
# from snf_schedule_optimizer.persistence.fakes import (
#     FakeEmployeeRepo,
#     FakeFacilityRepo,
#     FakeNurseRepo,
#     FakeScheduleRepo,
#     FakeShiftRepo,
#     FakeShiftRequirementsRepo,
#     FakeStaffCompensationRepo,
# )
# from snf_schedule_optimizer.resident_acuity_repo import (
#     FakeResidentAcuityPerShiftRepo,
# )
# from snf_schedule_optimizer_tests.scenario_builder import ScenarioBuilder
# from snf_schedule_optimizer_tests.scenario_models import WorkforceConfig
#
#
# def build_fake_retrievers_container() -> type[IRetrieversContainer]:
#     # 1. Generate the Demo Data once per container lifetime
#     _scenario = (
#         ScenarioBuilder(seed=42)
#         .with_workforce(WorkforceConfig(count_rn=20, count_cna=40))
#         .build()
#     )
#
#     # 2. Define Demo-Specific Facility Metadata
#     _facility_config = FacilityConfig(
#         org_id="ORG_DEMO",
#         facility_id="FAC_DEMO",
#         shifts_per_day=3,
#         overtime_threshold_hours_per_week=40,
#         start_of_work_week_day=whenever.Weekday.MONDAY,
#         start_of_work_day_time=whenever.Time(7, 0, 0),
#         pay_period=whenever.DateTimeDelta(weeks=1),
#         weekend_multiplier=1.5,
#         night_shift_multiplier=1.2,
#         tz="America/New_York",
#     )
#
#     # 3. Override Retrievers with Pre-Seeded Fakes
#     # We use Singletons for fakes so that state (like history) persists across the demo session
#
#     class FakeRetrieversContainer(BaseContainer, IRetrieversContainer):
#         shift_retriever = Singleton(
#             FakeShiftRepo,
#             shifts=_scenario.shifts,
#         )
#
#         schedule_retriever = Singleton(
#             FakeScheduleRepo,
#             schedules=...,
#         )
#
#         facility_retriever = providers.Singleton(
#             FakeFacilityRepo,
#             configs=[_facility_config],
#         )
#
#         history_retriever = Singleton(
#             FakeRawHistoryRepo,
#             records=_scenario.history_records,
#         )
#
#         employee_retriever = Singleton(
#             FakeEmployeeRepo,
#             employees=_scenario.employees,
#         )
#         nurse_retriever = Singleton(
#             FakeNurseRepo,
#             nurses=_scenario.nurses,
#         )
#
#         compensation_retriever = Singleton(
#             FakeStaffCompensationRepo,
#             _scenario.financials,
#         )
#
#         shift_req_retriever = Singleton(
#             FakeShiftRequirementsRepo,
#             default_requirements=ShiftSpecificRequirements(
#                 target_hprd_rn=0.0,
#                 target_hprd_cna=0.0,
#                 target_total_hprd=0.0,
#             ),
#         )
#
#         acuity_retriever = Singleton(
#             FakeResidentAcuityPerShiftRepo,
#             predefined_acuity_data=_scenario.acuity_data,
#         )
#
#     return FakeRetrieversContainer
