# Backend Architecture

## Entity Relationship Diagram

All tables are scoped by `org_id` via PostgreSQL Row-Level Security unless noted otherwise.
Formal foreign keys exist at the SQL level for certification, compensation, preference, and time-punch
relationships. Other relationships are logical/referential (joined in application code by ID columns).

```mermaid
erDiagram
    FACILITY_CONFIG {
        int org_id PK
        int facility_id PK
        string timezone
        float default_hprd_rn
        float default_hprd_lpn
        float default_hprd_cna
        float default_hprd_total
        int max_consecutive_work_days
        float min_rest_hours_between_shifts
    }

    EMPLOYEE {
        int org_id PK
        int id PK
        string name
        string job_title
        date hire_date
        string classification
    }

    EMPLOYEE_CERTIFICATION {
        int id PK
        int org_id FK
        int employee_id FK
        string certification_name
        date expiration_date
        bool is_active
    }

    NURSE_PROFILE {
        int org_id PK
        int employee_id PK
        float available_hours_weekly
        string skills
        bool is_preceptor
        bool is_charge_nurse
    }

    STAFF_COMPENSATION_RECORD {
        int id PK
        int org_id FK
        int employee_id FK
        float base_rate_effective
        float ot_multiplier
        bool is_agency
        date effective_start_date
        date effective_end_date
    }

    STAFF_SHIFT_PREFERENCE {
        int id PK
        int org_id FK
        int employee_id FK
        string preference_type
        float penalty_weight
        bool is_hard_block
    }

    SHIFT {
        int org_id PK
        int facility_id PK
        int id PK
        datetime shift_start_dt
        datetime shift_end_dt
        int day_of_week
        int unit_id
        bool is_scheduled
    }

    SHIFT_REQUIREMENTS {
        int id PK
        int org_id
        int facility_id
        int shift_id
        float target_hprd_rn
        float target_hprd_cna
        float target_total_hprd
    }

    TIME_PUNCH_RAW_EVENT {
        int org_id FK
        int facility_id FK
        int id PK
        int employee_id
        int shift_id FK
        datetime punch_time
        string punch_type
        float rate
    }

    SCHEDULE_RECORD {
        int schedule_id PK
        int org_id
        int facility_id
        string start_date
        string end_date
        int version
    }

    SCHEDULE_VERSION {
        int schedule_version_id PK
        int schedule_id
        int org_id
        int facility_id
        int version_number
        string run_id
    }

    SCHEDULE_ASSIGNMENT {
        int schedule_id PK
        int assignment_id PK
        int org_id
        int schedule_version_id
        int facility_id
        int shift_id
        int employee_id
    }

    OPTIMIZATION_RUN {
        string run_id PK
        int org_id
        int facility_id
        int schedule_id
        int base_schedule_version
        int result_schedule_version
        string status
        string stage
        int progress_percent
        string snapshot_id
        string claimed_by
        string claim_token
        string failure_code
        json patches_json
        json settings_json
        json summary_json
        json stats_json
        json financials_json
    }

    OPTIMIZATION_RUN_EVENT {
        string run_id PK
        int sequence PK
        string status
        string stage
        int progress_percent
        string status_message
    }

    OPTIMIZATION_SNAPSHOT {
        string snapshot_id PK
        string run_id
        int org_id
        int facility_id
        int schedule_id
        json payload_json
    }

    RESIDENT_ACUITY {
        int id PK
        int org_id
        int facility_id
        int resident_id
        datetime census_day
        int pt_score_gg
        string clinical_category
    }

    OVERTIME_RULE {
        int id PK
        int org_id
        string trigger_type
        float multiplier
        float daily_threshold
        float weekly_threshold
    }

    DIFFERENTIAL_RULE {
        int id PK
        int org_id
        string rule_type
        float amount
        float multiplier
    }

    FACILITY_RULES_CONFIG {
        int id PK
        int org_id
        int facility_id
        int rounding_unit_minutes
        float meal_deduction_duration_hours
    }

    EMPLOYEE ||--o{ EMPLOYEE_CERTIFICATION : has
    EMPLOYEE ||--|| NURSE_PROFILE : profile
    NURSE_PROFILE ||--o{ STAFF_COMPENSATION_RECORD : pay_history
    NURSE_PROFILE ||--o{ STAFF_SHIFT_PREFERENCE : preferences
    SHIFT ||--o{ TIME_PUNCH_RAW_EVENT : punches
    SHIFT ||--o{ SHIFT_REQUIREMENTS : requirements
    SCHEDULE_RECORD ||--o{ SCHEDULE_VERSION : versions
    SCHEDULE_RECORD ||--o{ SCHEDULE_ASSIGNMENT : assignments
    SCHEDULE_ASSIGNMENT }o--|| SHIFT : shift
    SCHEDULE_ASSIGNMENT }o--|| EMPLOYEE : employee
    SCHEDULE_VERSION }o--|| OPTIMIZATION_RUN : produced_by
    OPTIMIZATION_RUN ||--o{ OPTIMIZATION_RUN_EVENT : events
    OPTIMIZATION_RUN ||--o| OPTIMIZATION_SNAPSHOT : snapshot
```

**Notes:**
- `FACILITY_CONFIG`, `SHIFT`, `SHIFT_REQUIREMENTS`, and `RESIDENT_ACUITY` are scoped by `(org_id, facility_id)`.
- `StagedSchedulePatch`, `OptimizationSettings`, `OptimizationSummary`, `OptimizationStats`, and
  `FinancialReport` are stored as JSON columns inside `optimization_run`, not as separate tables.
- `MinMandates` is derived dynamically from `FACILITY_CONFIG` at solve time.
- Tables without RLS: `optimization_run_event` (scoped by parent `optimization_run` which has RLS),
  `overtime_rules_config` (legacy), `idempotency_key` (global).

---

## OptimizationRun State Diagram

The optimization run is the central long-running workflow. It is created by the
`WorkforceSchedulerFacade` and executed by a pool of worker processes using a lease-based
claim mechanism to prevent duplicate execution.

### Status & Stage Enums

| Status    | Terminal? | Stage values during this status                         |
|-----------|-----------|---------------------------------------------------------|
| `queued`    | No        | `queued`                                                |
| `running`   | No        | `snapshotting` → `indexing` → `building_model` → `solving` → `analyzing` → `publishing` |
| `completed` | Yes       | `completed`                                             |
| `failed`    | Yes       | `failed`                                                |
| `cancelled` | Yes       | (defined in enum, not yet implemented)                  |

```mermaid
stateDiagram-v2
    [*] --> Queued : start_optimization_run()

    state Queued {
        [*] --> queued_stage : stage="queued" (0%)
    }

    state Running {
        [*] --> Snapshotting : stage="snapshotting" (5%)
        Snapshotting --> Indexing : stage="indexing" (15%)
        Indexing --> BuildingModel : stage="building_model" (30%)
        BuildingModel --> Solving : stage="solving" (55%)
        Solving --> Analyzing : stage="analyzing" (80%)
        Analyzing --> Publishing : stage="publishing" (92%)
    }

    Queued --> Running : worker claims run\n(status→running, lease set)
    Running --> Completed : solve feasible\n(stage→completed, 100%)
    Running --> Failed : solver infeasible\nor worker exception

    state ClaimCoordination {
        StaleLease : lease expired\n(another worker can reclaim)
        LeaseLost : heartbeat renewal fails\n(claim_token mismatch)
    }

    Running --> StaleLease : lease_expires_at < now()
    StaleLease --> Running : re-claimed by another worker

    Completed --> [*]
    Failed --> [*]

    note right of Queued
        Runs are created by
        WorkforceSchedulerFacade
        with patches_json,
        settings_json, and
        schedule version lock
    end note

    note right of Running
        Worker publishes progress
        events after each stage.
        UI polls or streams via
        StreamOptimizationRun.
    end note

    note left of ClaimCoordination
        Lease TTL: 30s
        Heartbeat: every 10s
        claim_token guards
        against split-brain
    end note
```

### Failure Codes

| Failure Code              | Trigger                                              |
|---------------------------|------------------------------------------------------|
| `snapshot_build_failed`   | Could not construct optimization snapshot            |
| `baseline_infeasible`     | Existing schedule violates hard constraints          |
| `solver_infeasible`       | CBC solver found no feasible solution                |
| `solver_timeout`          | Solver exceeded time limit                           |
| `solver_error`            | Unexpected solver failure                            |
| `publish_conflict`        | Schedule version changed during publishing           |
| `publish_failed`          | Result persistence failed                            |
| `worker_error`            | Unhandled exception in worker process                |

### Worker Claim Flow

1. Worker generates a random `claim_token` and 30-second `lease_expires_at`.
2. SQL query atomically claims the next `queued` run (or any `running` run with expired lease).
3. Worker starts a background heartbeat task (renews lease every 10 seconds).
4. Worker executes the optimization phases, publishing progress events after each stage.
5. On completion or failure, worker releases the claim (clears `claimed_by`, `claim_token`, `lease_expires_at`).
6. If heartbeat renewal fails (`claim_token` mismatch), the worker stops — another worker claimed the run.

### Solver Phases

| Phase            | What happens                                                   |
|------------------|----------------------------------------------------------------|
| **Snapshotting** | Serialize current schedule, employees, shifts, config as JSON   |
| **Indexing**     | Build lazy scenario data index (employee/shift lookups)         |
| **Building Model** | Create binary decision variables (nurse↔shift) + pay buckets |
| **Solving**      | Run CBC ILP solver with hard constraints + soft penalties       |
| **Analyzing**    | Post-solve: extract assignments, compute metrics, detect conflicts |
| **Publishing**   | Write result schedule to `schedule_record` + `schedule_version`  |
