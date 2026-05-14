import copy
from collections import defaultdict
from typing import Protocol
from uuid import uuid4

import whenever

from snf_schedule_optimizer.api import (
    MoveEmployeeRequest,
    OptimizationOutput,
    OptimizeScheduleRequest,
    StartOptimizationRunRequest,
)
from snf_schedule_optimizer.domain.payroll.calculations.schedule_cost_evaluator import (
    ScheduleCostEvaluator,
)
from snf_schedule_optimizer.domain.repositories import IFacilityRepo, IShiftRepo
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IScheduleRepo,
    ScheduleLookupKey,
)
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    FacilityConfig,
    MinMandates,
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSettings,
    OptimizationSummary,
    PatchConflict,
    PreferenceWeights,
    Schedule,
    Shift,
    ShiftKey,
    StagedSchedulePatch,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.diagnostics import SchedulerInfeasibilityDiagnoser
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider
from snf_schedule_optimizer.optimizer.models import ScheduleOptimizationResults
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.reporting import ScheduleResultAnalyzer
from snf_schedule_optimizer.optimizer.strategies.fixing import (
    PinnedScheduleConstraintStrategy,
)


class WorkforceSchedulerFacadePort(Protocol):
    async def optimize_schedule(
        self,
        org_id: DomainPrimaryKeyType,
        facility_contexts: dict[DomainPrimaryKeyType, FacilityScenarioContext],
        preference_weights: PreferenceWeights,
        pay_period_start: whenever.Instant,
        optimization_settings: OptimizationSettings | None = None,
        optimization_start_time: whenever.Instant | None = None,
        pinned_schedule: Schedule | None = None,
    ) -> OptimizationOutput: ...

    async def optimize_schedule_for_facility(
        self,
        request: OptimizeScheduleRequest,
    ) -> OptimizationOutput: ...

    async def start_optimization_run(
        self,
        request: StartOptimizationRunRequest,
    ) -> OptimizationOutput: ...

    async def get_optimization_run(self, run_id: str) -> OptimizationRun | None: ...

    async def get_schedule_status(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        schedule_id: DomainPrimaryKeyType,
        current_schedule_version: int,
    ) -> tuple[Schedule, OptimizationRun | None, bool]: ...

    async def validate_shift_move(
        self,
        move_request: MoveEmployeeRequest,
        pay_period_start: whenever.Instant,
    ) -> OptimizationOutput: ...

    async def get_monthly_schedule(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType | None,
        start_date: str,
    ) -> tuple[Schedule, dict[ShiftKey, Shift], dict[int, Employee], FacilityConfig]: ...

    async def close(self) -> None: ...


class WorkforceSchedulerFacade(WorkforceSchedulerFacadePort):
    def __init__(
        self,
        provider_factory: ScenarioDataProviderFactory,
        optimizer: NurseShiftScheduleOptimizer,
        cost_evaluator: ScheduleCostEvaluator,
        schedule_retriever: IScheduleRepo,
        facility_repository: IFacilityRepo,
        shift_retriever: IShiftRepo,
    ):
        self.provider_factory = provider_factory
        self.optimizer = optimizer
        self.cost_evaluator = cost_evaluator
        self.schedule_retriever = schedule_retriever
        self.facility_repository = facility_repository
        self.shift_retriever = shift_retriever

    async def optimize_schedule(
        self,
        org_id: DomainPrimaryKeyType,
        facility_contexts: dict[DomainPrimaryKeyType, FacilityScenarioContext],
        preference_weights: PreferenceWeights,
        pay_period_start: whenever.Instant,
        optimization_settings: OptimizationSettings | None = None,
        optimization_start_time: whenever.Instant | None = None,
        pinned_schedule: Schedule | None = None,
    ) -> OptimizationOutput:
        optimization_start_time = optimization_start_time or whenever.Instant.now()
        optimization_settings = optimization_settings or OptimizationSettings()

        data_provider = self.provider_factory.create(
            org_id=org_id,
            facility_contexts=facility_contexts,
            pay_period_start=pay_period_start,
            optimization_start_time=optimization_start_time,
            optimization_settings=optimization_settings,
        )

        optimizer = self.optimizer
        if pinned_schedule is not None:
            pinning_strategy = PinnedScheduleConstraintStrategy(pinned_schedule)
            optimizer = NurseShiftScheduleOptimizer(
                core_variable_strategy=self.optimizer.core_variable_strategy,
                global_pay_strategies=self.optimizer.global_pay_strategies,
                facility_constraint_strategies=(
                    self.optimizer.facility_constraint_strategies + [pinning_strategy]
                ),
                facility_rule_strategies=self.optimizer.facility_rule_strategies,
                penalty_strategies=self.optimizer.penalty_strategies,
            )

        result = await optimizer.solve(
            data_provider=data_provider,
            preference_weights=preference_weights,
        )

        return await self._process_results(result, data_provider)

    async def optimize_schedule_for_facility(
        self,
        request: OptimizeScheduleRequest,
    ) -> OptimizationOutput:
        facility_context = await self._build_optimization_context(
            org_id=request.org_id,
            facility_id=request.facility_id,
            start_date=request.start_date,
            end_date=request.end_date or request.start_date,
            optimization_settings=request.settings,
        )
        result = await self.optimize_schedule(
            org_id=request.org_id,
            facility_contexts={request.facility_id: facility_context},
            preference_weights=request.settings.to_preference_weights(),
            pay_period_start=facility_context.shifts[0].shift_start_dt.start_of_day().to_instant(),
            optimization_settings=request.settings,
        )
        if request.persist_result and result.is_success and result.schedule is not None:
            base_schedule = await self.schedule_retriever.get_schedule_for_month(
                org_id=request.org_id,
                facility_id=request.facility_id,
                start_date=request.start_date,
            )
            if base_schedule is None or base_schedule.schedule_id is None:
                schedule_id = await self.schedule_retriever.next_schedule_id(request.org_id)
                version = 1
            else:
                schedule_id = base_schedule.schedule_id
                latest_version = await self.schedule_retriever.get_latest_schedule_version(
                    request.org_id,
                    schedule_id,
                )
                version = (latest_version or 0) + 1
            persisted_schedule = Schedule(
                org_id=request.org_id,
                facility_id=request.facility_id,
                schedule_id=schedule_id,
                schedule_lineage_id=schedule_id,
                schedule_version=version,
                shift_assignments=result.schedule.shift_assignments,
                start_date=request.start_date,
                end_date=request.end_date or request.start_date,
                latest_optimization=result.summary,
                latest_optimization_stats=result.stats,
                latest_optimization_financials=result.financials,
                updated_at=whenever.Instant.now().format_iso(),
            )
            await self.schedule_retriever.save_schedule(persisted_schedule)
            await self.schedule_retriever.commit()
            result = OptimizationOutput(
                is_success=True,
                schedule=persisted_schedule,
                analysis=result.analysis,
                financials=result.financials,
                stats=result.stats,
                summary=result.summary,
                error_details=result.error_details,
            )
        return result

    async def start_optimization_run(
        self,
        request: StartOptimizationRunRequest,
    ) -> OptimizationOutput:
        current_schedule = await self.schedule_retriever.get_schedule(
            ScheduleLookupKey(request.org_id, request.schedule_id)
        )
        if current_schedule is None:
            return OptimizationOutput(
                is_success=False,
                schedule=None,
                analysis=None,
                financials=None,
                stats=None,
                is_valid=False,
                error_details="Schedule not found.",
            )

        latest_version = await self.schedule_retriever.get_latest_schedule_version(
            request.org_id,
            request.schedule_id,
        )
        assert latest_version is not None

        rebased_schedule = current_schedule
        conflicts: list[PatchConflict] = []
        if request.staged_patches:
            rebased_schedule, conflicts = await self.schedule_retriever.reapply_patches(
                current_schedule,
                list(request.staged_patches),
            )

        if latest_version != request.base_schedule_version and (conflicts or not request.allow_overwrite):
            return OptimizationOutput(
                is_success=False,
                schedule=current_schedule,
                analysis=None,
                financials=None,
                stats=None,
                is_valid=False,
                validation_level="stale",
                error_details="Schedule version conflict.",
                conflicts=tuple(conflicts),
                latest_schedule_version=latest_version,
            )

        if request.client_request_id:
            existing_run = await self.schedule_retriever.get_optimization_run_by_client_request(
                request.org_id,
                request.facility_id,
                request.schedule_id,
                request.client_request_id,
            )
            if existing_run is not None and existing_run.status in {"queued", "running"}:
                return OptimizationOutput(
                    is_success=True,
                    schedule=rebased_schedule,
                    analysis=None,
                    financials=None,
                    stats=None,
                    run=existing_run,
                    latest_schedule_version=latest_version,
                    conflicts=tuple(conflicts),
                )

        run = OptimizationRun(
            run_id=uuid4().hex,
            org_id=request.org_id,
            facility_id=request.facility_id,
            schedule_id=request.schedule_id,
            schedule_lineage_id=request.schedule_id,
            base_schedule_version=request.base_schedule_version,
            status="queued",
            stage="queued",
            progress_percent=0,
            status_message="Optimization queued",
            started_at=whenever.Instant.now().format_iso(),
            patches=request.staged_patches,
            client_request_id=request.client_request_id,
            settings=request.settings,
            persist_result=request.persist_result,
            decision_start_date=request.start_date,
            decision_end_date=request.end_date,
        )
        await self.schedule_retriever.save_optimization_run(run)
        await self.schedule_retriever.append_optimization_run_event(
            OptimizationRunEvent(
                run_id=run.run_id,
                sequence=0,
                status="queued",
                stage="queued",
                progress_percent=0,
                status_message="Optimization queued",
                created_at=whenever.Instant.now().format_iso(),
            )
        )
        await self.schedule_retriever.commit()

        return OptimizationOutput(
            is_success=True,
            schedule=rebased_schedule,
            analysis=None,
            financials=None,
            stats=None,
            run=run,
            latest_schedule_version=latest_version,
            conflicts=tuple(conflicts),
        )

    async def get_optimization_run(self, run_id: str) -> OptimizationRun | None:
        return await self.schedule_retriever.get_optimization_run(run_id)

    async def get_schedule_status(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        schedule_id: DomainPrimaryKeyType,
        current_schedule_version: int,
    ) -> tuple[Schedule, OptimizationRun | None, bool]:
        schedule = await self.schedule_retriever.get_schedule(
            ScheduleLookupKey(org_id, schedule_id)
        )
        if schedule is None:
            raise ValueError("Schedule not found.")
        active_run = await self.schedule_retriever.get_active_optimization_run(
            org_id,
            facility_id,
            schedule_id,
        )
        latest_version = await self.schedule_retriever.get_latest_schedule_version(
            org_id,
            schedule_id,
        )
        has_newer_version = (latest_version or schedule.schedule_version) > current_schedule_version
        return schedule, active_run, has_newer_version

    async def validate_shift_move(
        self,
        move_request: MoveEmployeeRequest,
        pay_period_start: whenever.Instant,
    ) -> OptimizationOutput:
        current_schedule = await self.schedule_retriever.get_schedule(
            ScheduleLookupKey(move_request.org_id, move_request.schedule_id)
        )
        if current_schedule is None:
            return OptimizationOutput(
                is_success=False,
                schedule=None,
                analysis=None,
                financials=None,
                stats=None,
                is_valid=False,
                error_details="Schedule not found.",
            )

        latest_version = await self.schedule_retriever.get_latest_schedule_version(
            move_request.org_id,
            move_request.schedule_id,
        )
        assert latest_version is not None
        if latest_version != move_request.schedule_version:
            return OptimizationOutput(
                is_success=True,
                schedule=current_schedule,
                analysis=None,
                financials=None,
                stats=None,
                is_valid=False,
                validation_level="stale",
                error_details="Local draft is based on an older schedule version.",
                latest_schedule_version=latest_version,
            )

        staged_schedule = current_schedule
        conflicts: list[PatchConflict] = []
        if move_request.staged_patches:
            staged_schedule, conflicts = await self.schedule_retriever.reapply_patches(
                current_schedule,
                list(move_request.staged_patches),
            )
            if conflicts:
                return OptimizationOutput(
                    is_success=True,
                    schedule=current_schedule,
                    analysis=None,
                    financials=None,
                    stats=None,
                    is_valid=False,
                    validation_level="stale",
                    error_details="One or more staged patches no longer apply cleanly.",
                    conflicts=tuple(conflicts),
                    latest_schedule_version=latest_version,
                )

        facility_contexts = await self._rehydrate_facility_contexts(
            move_request.org_id,
            staged_schedule,
            move_request,
        )
        proposed_schedule = copy.deepcopy(staged_schedule)
        self._apply_move_to_schedule(proposed_schedule, move_request)

        result = await self.optimize_schedule(
            org_id=move_request.org_id,
            facility_contexts=facility_contexts,
            preference_weights=PreferenceWeights(),
            pay_period_start=pay_period_start,
            optimization_settings=OptimizationSettings(),
            pinned_schedule=proposed_schedule,
        )

        validation_level = "ok"
        warnings: tuple[str, ...] = ()
        if not result.is_success:
            return OptimizationOutput(
                is_success=True,
                schedule=staged_schedule,
                analysis=None,
                financials=result.financials,
                stats=result.stats,
                is_valid=False,
                validation_level="critical",
                error_details=result.error_details,
                latest_schedule_version=latest_version,
            )

        if result.analysis is not None:
            warnings_list = [
                violation.details
                for violation in result.analysis.violations
                if violation.severity == "Soft"
            ]
            if warnings_list:
                validation_level = "warning"
                warnings = tuple(warnings_list)

        patch = StagedSchedulePatch(
            patch_id=move_request.patch_id or uuid4().hex,
            employee_id=move_request.employee_id,
            employee_name=self._lookup_employee_name(result, move_request.employee_id),
            from_shift_id=move_request.from_shift_id,
            to_shift_id=move_request.to_shift_id,
            pinned=True,
            warnings=warnings,
            validation_level=validation_level,
            causes_overtime=any("overtime" in warning.lower() for warning in warnings),
            total_cost=result.financials.total_enterprise_cost if result.financials else 0.0,
            created_at=whenever.Instant.now().format_iso(),
        )

        return OptimizationOutput(
            is_success=True,
            schedule=proposed_schedule,
            analysis=result.analysis,
            financials=result.financials,
            stats=result.stats,
            is_valid=True,
            summary=result.summary,
            warnings=warnings,
            validation_level=validation_level,
            patches=(*move_request.staged_patches, patch),
            latest_schedule_version=latest_version,
        )

    async def close(self) -> None:
        return None

    async def get_monthly_schedule(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType | None,
        start_date: str,
    ) -> tuple[Schedule, dict[ShiftKey, Shift], dict[int, Employee], FacilityConfig]:
        schedule = await self.schedule_retriever.get_schedule_for_month(
            org_id=org_id,
            facility_id=facility_id,
            start_date=start_date,
        )
        if schedule is None:
            raise ValueError("No schedule found for the requested month.")

        target_facility_id = facility_id if facility_id is not None else schedule.facility_id
        if target_facility_id is None:
            raise ValueError("A facility_id is required to load a monthly schedule.")

        configs = await self.facility_repository.get_configs(org_id, [target_facility_id])
        if not configs:
            raise ValueError(f"Facility config not found for facility_id: {target_facility_id}")

        facility_config = configs[0]
        timezone_map = {facility_config.facility_id: facility_config.tz}

        shift_keys = [
            key for key in schedule.shift_assignments if key.facility_id == target_facility_id
        ]
        shifts = await self.shift_retriever.get_shifts_by_keys(
            shift_keys=shift_keys,
            facility_timezones=timezone_map,
            org_id=org_id,
        )

        employees = await self.provider_factory.employee_retriever.get_all_employees(org_id)
        employee_map = {employee.employee_id: employee for employee in employees}

        return schedule, shifts, employee_map, facility_config

    async def _process_results(
        self,
        result: ScheduleOptimizationResults,
        data_provider: IScenarioDataProvider,
    ) -> OptimizationOutput:
        if not result.success or not result.optimal_schedule:
            error_msg = str(result.infeasibility_reason)
            diagnoser = SchedulerInfeasibilityDiagnoser(data_provider)
            diagnostic_report = await diagnoser.generate_report_string()
            full_error_details = f"{error_msg}\n{diagnostic_report}"
            return OptimizationOutput(
                is_success=False,
                schedule=None,
                analysis=None,
                financials=None,
                stats=result.statistics,
                summary=None,
                error_details=full_error_details,
            )

        analyzer = ScheduleResultAnalyzer(data_provider)
        analysis_report = await analyzer.analyze(result.optimal_schedule)
        financial_report = await self.cost_evaluator.evaluate_schedule(
            result.optimal_schedule,
            data_provider,
        )
        schedule_summary = self._build_summary(result.optimal_schedule, data_provider)

        return OptimizationOutput(
            is_success=True,
            schedule=result.optimal_schedule,
            analysis=analysis_report,
            financials=financial_report,
            stats=result.statistics,
            summary=schedule_summary,
        )

    def _lookup_employee_name(
        self,
        result: OptimizationOutput,
        employee_id: DomainPrimaryKeyType,
    ) -> str | None:
        if result.analysis is None:
            return None
        for assignment in result.analysis.assignments:
            if assignment.shift_id in {
                patch.to_shift_id for patch in result.patches if patch.to_shift_id is not None
            }:
                return assignment.employee_name
        return None

    def _apply_move_to_schedule(
        self,
        schedule: Schedule,
        request: MoveEmployeeRequest,
    ) -> None:
        if request.from_shift_id == request.to_shift_id:
            return
        if not request.from_shift_id and not request.to_shift_id:
            raise ValueError("Both from_shift_id and to_shift_id cannot be None.")

        if request.from_shift_id:
            from_shift_assigned = next(
                (
                    assigned
                    for shift_assignment_key, assigned in schedule.shift_assignments.items()
                    if shift_assignment_key == ShiftKey(request.facility_id, request.from_shift_id)
                ),
                None,
            )
            if from_shift_assigned is None:
                raise ValueError(f"Shift {request.from_shift_id} not found in schedule.")
            if request.employee_id in from_shift_assigned:
                from_shift_assigned.remove(request.employee_id)

        if request.to_shift_id:
            to_shift_assigned = next(
                (
                    assigned
                    for shift_assigned_key, assigned in schedule.shift_assignments.items()
                    if shift_assigned_key.shift_id == request.to_shift_id
                ),
                None,
            )
            if to_shift_assigned is None:
                raise ValueError(f"Shift {request.to_shift_id} not found in schedule.")
            if request.employee_id not in to_shift_assigned:
                to_shift_assigned.append(request.employee_id)

    async def _rehydrate_facility_contexts(
        self,
        org_id: DomainPrimaryKeyType,
        schedule: Schedule,
        request: MoveEmployeeRequest,
    ) -> dict[DomainPrimaryKeyType, FacilityScenarioContext]:
        keys_to_fetch = set(schedule.shift_assignments.keys())
        if request.from_shift_id:
            keys_to_fetch.add(ShiftKey(request.facility_id, request.from_shift_id))
        if request.to_shift_id:
            keys_to_fetch.add(ShiftKey(request.facility_id, request.to_shift_id))
        if not keys_to_fetch:
            return {}

        facility_ids = {k.facility_id for k in keys_to_fetch}
        configs = await self.facility_repository.get_configs(org_id, list(facility_ids))
        config_map = {c.facility_id: c for c in configs}
        tz_map = {c.facility_id: c.tz for c in configs}
        shifts_map = await self.shift_retriever.get_shifts_by_keys(list(keys_to_fetch), tz_map, org_id)

        shifts_by_fac: dict[DomainPrimaryKeyType, list[Shift]] = defaultdict(list)
        for shift in shifts_map.values():
            shifts_by_fac[shift.facility_id].append(shift)

        contexts: dict[DomainPrimaryKeyType, FacilityScenarioContext] = {}
        for fac_id, shifts in shifts_by_fac.items():
            if fac_id not in config_map:
                raise ValueError(f"Facility config not found for facility_id: {fac_id}")
            contexts[fac_id] = FacilityScenarioContext(
                facility_id=fac_id,
                shifts=shifts,
                config=config_map[fac_id],
                min_mandates=self._derive_min_mandates(config_map[fac_id]),
            )

        return contexts

    async def _build_optimization_context(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        start_date: str,
        end_date: str,
        optimization_settings: OptimizationSettings,
    ) -> FacilityScenarioContext:
        configs = await self.facility_repository.get_configs(org_id, [facility_id])
        if not configs:
            raise ValueError(f"Facility config not found for facility_id: {facility_id}")
        facility_config = configs[0]
        tz_map = {facility_id: facility_config.tz}
        all_shifts = await self.shift_retriever.get_shifts_for_org(org_id, tz_map)
        relevant_shifts = [
            shift
            for shift in all_shifts
            if shift.facility_id == facility_id
            and start_date <= shift.shift_start_dt.to_tz(facility_config.tz).date().format_common_iso() <= end_date
        ]
        if not relevant_shifts:
            raise ValueError("No shifts found in the requested optimization window.")
        return FacilityScenarioContext(
            facility_id=facility_id,
            shifts=relevant_shifts,
            config=facility_config,
            min_mandates=self._derive_min_mandates(facility_config),
            optimization_settings=optimization_settings,
        )

    def _derive_min_mandates(self, config: FacilityConfig) -> MinMandates:
        return MinMandates(
            min_rn_hprd=config.default_hprd_rn,
            min_lpn_hprd=0.0,
            min_cna_hprd=config.default_hprd_cna,
            min_total_hprd=config.default_hprd_total,
            min_staff_per_shift_rn=1,
            min_staff_per_shift_lpn=0,
            min_staff_per_shift_cna=2,
        )

    def _build_summary(
        self,
        schedule: Schedule,
        data_provider: IScenarioDataProvider,
    ) -> OptimizationSummary:
        all_shifts = data_provider.get_all_shifts()
        covered_shifts = sum(
            1 for shift in all_shifts if schedule.shift_assignments.get(shift.shift_key)
        )
        total_assignments = sum(len(assignments) for assignments in schedule.shift_assignments.values())
        return OptimizationSummary(
            assignments_changed=total_assignments,
            total_assignments=total_assignments,
            covered_shifts=covered_shifts,
            uncovered_shifts=max(0, len(all_shifts) - covered_shifts),
            completed_at=whenever.Instant.now().format_iso(),
            applied_settings=data_provider.get_optimization_settings(),
        )
