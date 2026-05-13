# SNF Schedule Optimizer Service

This service is the backend for the SNF Schedule Optimizer demo.

It owns the optimization engine, persistence layer, demo seeding flow, and the ConnectRPC API consumed by the frontend.

## Responsibilities

- expose scheduling endpoints over ConnectRPC
- expose a simple FastAPI health endpoint
- seed deterministic demo data into Postgres
- evaluate and validate staffing schedules
- report financial and compliance-oriented results from evaluated schedules

## Main Areas

- `src/snf_schedule_optimizer/api`: FastAPI app and RPC handlers
- `src/snf_schedule_optimizer/service`: application facades
- `src/snf_schedule_optimizer/optimizer`: solver orchestration, constraints, penalties, reporting
- `src/snf_schedule_optimizer/persistence`: repository implementations
- `src/snf_schedule_optimizer/sqlalchemy_models`: async SQLAlchemy models
- `src/snf_schedule_optimizer/infrastructure`: DI, seeding, scenario generation
- `snf_schedule_optimizer_tests`: tests and scaling experiments

## Local Setup

The project currently targets Python `==3.13.*`.

Install dependencies with `uv`:

```bash
uv sync
```

Set the required database URL:

```bash
export DATABASE_URL=postgresql+asyncpg://snf_user:snf_password@localhost:35435/snf_optimizer_demo

```

## Demo Database Path

If you want the backend demo database without running the full stack, use the service-local compose file:

```bash
docker compose -f docker-compose-demo.yml up --build
```

For the recommended local development workflow, use the repo-root `compose.dev.yml` via `just infra-up` and `just infra-seed`, then run the backend on the host with `just dev-be`.

For the main product-demo flow, you can invoke the repo-root compose file from this directory as well:

```bash
docker compose -f ../compose.demo.yml up --build -d
```

## Run Locally

Bootstrap schema and deterministic demo data:

```bash
python -m snf_schedule_optimizer.infrastructure.demo_bootstrap
```

Start the API:

```bash
python -m snf_schedule_optimizer.api.main
```

Recommended host dev server with reload:

```bash
just dev-be
```

Health check:

```text
http://localhost:8000/health
```

That `8000` address is the current host-dev convention used by `just dev-be`, not a global requirement across demo smoke or isolated E2E workflows.

## API Surface

The protobuf contract lives under `../proto/scheduling/v1/scheduling.proto`.

Current service endpoints include:

- `GetAllOrgFacilities`
- `GetMonthlySchedule`
- `ValidateShiftMove`

`ValidateShiftMove` is the most interesting product behavior in the current backend. It builds a proposed in-memory schedule, pins the solver to that schedule state, and reports whether the move is feasible under the active rule set.

## What-If And Reporting Capabilities

The service already supports a useful backend story for demo and product iteration:

- validate drag-and-drop shift moves as what-if checks
- run schedule analysis after solver evaluation
- report preference conflicts in the resulting assignments
- report staffing and HPRD-related violations
- report financial impact using the schedule cost evaluator
- emit basic optimization stats such as execution time, variables, and constraints

## Proto And Codegen

The backend depends on generated Python protobuf and Connect code.

The shared generation config lives in `../proto/buf.gen.yaml`.

From the `proto` directory, run:

```bash
buf generate
```

The repo also includes `post_generate_fix_imports.py`, which signals that generated Python imports may need post-processing depending on the generation environment.

In the Docker demo flow, codegen happens during image build so the stack is reproducible from a clean checkout.

## Development Commands

Run tests:

```bash
pytest
```

Run Ruff:

```bash
ruff check .
ruff format .
```

Run MyPy:

```bash
mypy
```

## Known Caveats

- local startup requires `DATABASE_URL`
- solver setup is not fully polished for every local environment
- the active optimizer path currently uses a PuLP/CBC-style setup

## Solver Disclaimer

This project includes `hexaly` in dependencies, but I did not complete runtime or solution-quality benchmarking across commercial optimizers such as Gurobi and Hexaly.

Because of personal time limits and licensing cost constraints, those comparisons are not part of the current repository deliverable.
