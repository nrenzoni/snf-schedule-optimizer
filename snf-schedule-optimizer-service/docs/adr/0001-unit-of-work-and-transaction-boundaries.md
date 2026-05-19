# ADR-0001: Unit of Work and Transaction Boundaries

- **Status**: Accepted
- **Date**: 2026-05-19
- **Author**: Architecture Team

## Context

The backend currently lacks clear transaction ownership boundaries. Several patterns
undermine consistency and testability:

1. **Unused UnitOfWork infrastructure.** `persistence/unit_of_work.py` defines
   `IUnitOfWork` and `SqlAlchemyUnitOfWork` with full async context-manager support,
   proper repo-wiring on session creation, and commit/rollback/close semantics.
   No command handler or worker calls this class.

2. **Repository-level transaction control.** `domain/scheduling/interfaces.py:202-208`
   declares `commit()` and `rollback()` on `IScheduleRepo`, and
   `persistence/schedule_repo.py:763-767` implements them by delegating directly to
   the underlying `AsyncSession`. This leaks transaction control into every component
   that holds a reference to the repo.

3. **Mixed session ownership in the facade.**
   `service/scheduling/scheduler_facade.py` (`WorkforceSchedulerFacade`) receives an
   `IScheduleRepo` injected at construction (line 116). It performs reads (e.g.
   `get_schedule_for_month` on line 206) and writes (e.g. `save_schedule` on line 238
   followed by `commit()` on line 239) through the same injected repository.
   The facade itself calls `schedule_retriever.commit()`, meaning it owns the
   transaction — but it does not own (create) the session, which was provided by the
   DI container and is shared across the entire request scope.

4. **Worker ad-hoc sessions.** `service/scheduling/optimization_worker_store.py`
   (`SqlOptimizationWorkerStore`) opens a new session per method (e.g. `claim_next`,
   `publish_progress`, `complete_run`) using `async with self._session_factory()`.
   Each method instantiates a `SQLScheduleRepo` on the fly and calls `session.commit()`
   directly (lines 87, 106, 118, 129, 152, 188). There is no shared UnitOfWork.

5. **Long-running compute holds open sessions.** The worker
   (`optimization_run_worker.py`) receives an `IScheduleRepo` injected at construction
   and uses it to read the base schedule (line 129) and reapply patches (line 442).
   Because the repo's session is kept alive across the entire `_do_execute_claimed_run`
   lifecycle — including snapshot building and solver execution — an implicit write
   session can outlive the durable state transitions.

## Decision

The following architectural rules apply to all new and migrated code:

### 1. Command handlers own transaction boundaries

Each write use case opens a `UnitOfWork`, performs all work through
repositories wired by that UoW, and calls `commit()` exactly once at the
handler level. No component deeper in the call stack commits.

```
async def handle(self, command: StartOptimizationRun) -> OptimizationRun:
    async with self._uow_factory() as uow:
        schedule = await uow.schedule_repo.get_schedule(...)
        run = create_run_from(command, schedule)
        uow.schedule_repo.save_optimization_run(run)
        await uow.commit()
        return run
```

### 2. Query handlers / query services are read-only

Query handlers never open write transactions, never call `commit()`, and
never hold open sessions across business logic. They may use read-optimised
repositories (e.g. `persistence/read_repo/schedule_read_repo.py`) or a
read-only session. If a query handler needs a live `AsyncSession`, it must
obtain a read-only session that is closed after the query completes.

### 3. Repositories are pure persistence components

Repositories never expose `commit()` or `rollback()` methods. They may call
`flush()` internally when strictly required (e.g. to obtain a generated ID
for a subsequent write in the same method). The `IScheduleRepo.commit()` and
`IScheduleRepo.rollback()` methods must be removed from the domain interface
and all implementations.

### 4. UnitOfWork is the sole transaction manager

The `UnitOfWork` (built from `persistence/unit_of_work.py`) is responsible for:
- Creating the `AsyncSession`
- Beginning the implicit transaction (SQLAlchemy auto-begin)
- Wiring all concrete repositories into the session
- Exposing `commit()`, `rollback()`, and `close()`
- Auto-rollback on uncommitted exception exit (via `__aexit__`)

### 5. Long-running compute MUST happen outside any open UoW transaction

Solver execution (`optimizer.engine.NurseShiftScheduleOptimizer.solve()`)
must not run inside a UnitOfWork context manager. The UoW must be committed
and closed before the solver is invoked, and a new UoW must be opened
afterwards to persist results. No write session may be held across
computation that does not require database access.

### 6. Worker persistence uses multiple short-lived UoWs

The worker must use one UnitOfWork per durable state transition:
- **Claim**: Open UoW → `claim_next_queued_optimization_run` → commit → close
- **Progress**: Open UoW → `save_optimization_run` + `append_event` → commit → close
- **Snapshot**: Open UoW → `save_optimization_snapshot` + `save_optimization_run` → commit → close
- **Complete/Fail**: Open UoW → `save_optimization_run` + `append_event` +
  `release_claim` (+ `save_schedule` on complete) → commit → close

No write session is held across snapshot building, solver execution, or
heartbeat loops.

## Naming Conventions

| Pattern | Examples |
|---|---|
| Command handlers: `<Verb><Noun>Handler` | `StartOptimizationRunHandler`, `CompleteOptimizationRunHandler`, `ClaimNextRunHandler` |
| Query handlers: `<Noun>Query` or `<Verb><Noun>Query` | `GetMonthlyScheduleQuery`, `GetOptimizationRunQuery` |
| Unit of Work classes: `AsyncUnitOfWork`, `UnitOfWorkFactory` | `AsyncUnitOfWork`, `UnitOfWorkFactory` |
| Repository classes: `<Aggregate>Repository` | `OptimizationRunRepository`, `ScheduleRepository`, `FacilityRepository` |

## Consequences

### Positive

- **Clear transaction boundaries.** Every developer can identify where commits
  happen by locating the single command handler.
- **No accidental cross-repo commits.** Because repositories no longer expose
  `commit()`, it is impossible for one component to commit another
  component's unvalidated writes.
- **Testable command handlers.** Handlers accept a `UnitOfWorkFactory`
  (or an explicit `IUnitOfWork` stub), making it straightforward to test
  with in-memory fakes.
- **Solver isolation.** Solvers never hold database sessions, eliminating
  idle-in-transaction connections and reducing connection pool pressure.
- **Worker durability.** Short-lived UoWs per state transition mean that a
  worker crash mid-solve does not leave an open transaction or stale claim.

### Negative

- **Migration cost.** The current codebase has ~20 methods across the
  facade, worker store, and worker that directly commit. Each must be
  refactored into a command handler.
- **More files.** Separating commands and queries into handlers will
  increase the number of modules, though each module remains small.
- **Team consistency.** All contributors must internalize the rule
  “repositories must not commit” and the command/query separation.

## Implementation Phases

The migration is planned across 11 blocks:

1. **ADR** — This document.
2. **Remove `commit()`/`rollback()` from `IScheduleRepo`** — Update the domain
   interface and all callers.
3. **Add `UnitOfWorkFactory`** — Wrap `sqlalchemy.ext.asyncio.async_sessionmaker`
   in a factory that produces `SqlAlchemyUnitOfWork` instances.
4. **`StartOptimizationRunHandler`** — Extract the write path from
   `WorkforceSchedulerFacade.start_optimization_run()` into a command handler.
5. **`OptimizeScheduleHandler`** — Extract the synchronous optimize+persist path
   from `WorkforceSchedulerFacade.optimize_schedule_for_facility()`.
6. **`ValidateShiftMoveHandler`** — Extract the read-validate path (declared
   non-write; migrate to a query handler if no writes are needed).
7. **Worker claim/progress/snapshot/complete handlers** — Replace the 6 methods
   in `SqlOptimizationWorkerStore` with UoW-backed command handlers.
8. **Rewrite `OptimizationRunWorker._do_execute_claimed_run()`** — Use the new
   handlers instead of direct repo access. Close all UoWs before solver
   execution.
9. **Extract query handlers** — `GetMonthlyScheduleQuery`, `GetScheduleStatusQuery`,
   etc. from the facade read paths.
10. **Remove `IScheduleRepo` from `WorkforceSchedulerFacade`** — Wire command
    and query handlers directly into the API layer.
11. **Finalise repository naming** — Rename `SQLScheduleRepo` to
    `OptimizationRunRepository` (or split into aggregate-scoped repos) and
    align all DI wiring.

