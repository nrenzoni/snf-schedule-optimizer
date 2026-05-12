# SNF Schedule Optimizer

SNF Schedule Optimizer is a product demo exploring how constraint programming can help skilled nursing facilities make better staffing decisions.

The project is aimed at a hard tradeoff: maximize business performance without sacrificing staffing quality, while also respecting nurse and staff preferences enough to reduce burnout pressure.

In practical terms, the demo is built around three competing goals:

- improve labor efficiency and business profitability
- maintain staffing quality and CMS-related compliance outcomes
- maximize nurse and staff preference satisfaction subject to the other constraints

This repository now includes a full demo stack that runs the UI, API, database, and deterministic demo seed together.

## Why This Exists

Staffing in skilled nursing is not just a scheduling problem.

It is a constrained optimization problem shaped by:

- staffing coverage requirements
- HPRD and minimum-role compliance
- overtime and agency cost pressure
- shift preferences and quality-of-life tradeoffs
- operational what-if decisions from managers

This demo is meant to show what a product could look like when those concerns are modeled together instead of handled through spreadsheets and manual adjustment.

## Demo Goals

- run the full stack with one command
- load schedule data in the UI from the real backend, not a frontend-only mock
- seed deterministic demo data so the product walkthrough is reproducible
- keep protobuf code generation aligned across frontend and backend
- demonstrate a real optimization-oriented backend shape, even where some product surfaces are still in progress

## Quick Start

Start the full product demo:

```bash
docker compose -f compose.demo.yml up --build -d
```

For day-to-day development, prefer the faster host-dev workflow described in `AGENTS.md` and exposed via `just`.

Stop the demo:

```bash
docker compose -f compose.demo.yml down
```

Reset the demo database and start fresh:

```bash
docker compose -f compose.demo.yml down -v
docker compose -f compose.demo.yml up --build -d
```

Check service status:

```bash
docker compose -f compose.demo.yml ps -a
```

Stream logs:

```bash
docker compose -f compose.demo.yml logs -f app ui db
```

## Demo URLs

- UI: `http://localhost:3000`
- API health: `http://localhost:8080/health`
- API browser-facing base URL: `http://localhost:8080`

The Postgres database stays on the internal Docker network for this demo.

## What The Demo Currently Proves

- the full stack can be booted from a clean checkout with one compose file
- the backend seeds deterministic schedule data into Postgres
- the UI loads monthly schedules from the real backend API
- the backend exposes ConnectRPC scheduling endpoints plus a health endpoint
- the backend includes what-if validation logic for shift moves, including analysis and financial reporting paths

## What Is Still Demo-Oriented

- the scenario analyzer dashboard in the UI is still mock-driven today
- the ML forecasts area is presentation-oriented rather than a production forecasting pipeline
- the monthly schedule endpoint is real, but some values in the response are still shaped for demo purposes
- CMS star rating is part of the product direction, but there is not yet a direct end-to-end star-rating computation surfaced in the demo

## Architecture

```text
Browser
  -> Next.js UI (localhost:3000)
  -> Python API (localhost:8080)
  -> Postgres (internal Docker network only)
```

Startup flow:

1. `db` starts and becomes healthy.
2. `seeder` creates schema and loads deterministic demo data.
3. `app` starts after seeding completes.
4. `ui` starts after the API passes health checks.

## Repo Structure

- `snf-schedule-optimizer-ui`: Next.js frontend for scheduling, scenario analysis, and demo dashboards
- `snf-schedule-optimizer-service`: Python backend with optimization, persistence, API, and demo seeding
- `proto`: shared protobuf and ConnectRPC contract used by both sides

## Current Backend Capabilities

The backend already has more than just CRUD/demo scaffolding.

It includes:

- a scheduling API contract defined in protobuf
- monthly schedule retrieval for the demo UI
- shift-move validation as a what-if feasibility check
- schedule analysis reporting for preference conflicts and staffing violations
- financial reporting over evaluated schedules
- deterministic scenario generation and seeding for repeatable demos

That means the repo can already demonstrate the shape of a serious optimization service, even though not every product module is wired to live backend logic yet.

## Design Decisions In This Demo

### Root-Level Compose

The main demo entry point is the repo-root `compose.demo.yml` because the stack spans multiple sibling projects.

### Real UI To Backend Schedule Loading

The UI now loads the monthly schedule from the backend instead of only generating schedule state inside the frontend.

### Deterministic Demo Seed

The seeder persists a stable baseline schedule so each demo starts with meaningful data and predictable visuals.

### Proto Codegen During Docker Build

The demo build path generates protobuf and Connect code inside Docker to reduce local assumptions and keep both sides aligned to the same source contract.

### Internal-Only Database Exposure

Postgres is not published to the host because the product demo only needs the UI and API exposed.

### API Published On Port 8080

The backend listens on port `8000` inside the container and is published as `localhost:8080` outside Docker to avoid common local conflicts.

## Solver Note

This codebase currently uses a PuLP/CBC-style optimization path in the active engine.

I did not complete runtime benchmarking or quality comparisons against commercial optimizers such as Gurobi or Hexaly. Due to personal time limits and licensing cost constraints, that comparison work is intentionally out of scope for this demo.

## Seeded Demo Data

The seeded demo includes:

- facility configuration
- employees and nurse profiles
- shifts
- compensation records
- persisted schedule assignments

The seeded schedule is deterministic, which makes stakeholder demos and repeated resets much more stable.

## Local Development

This root README is primarily for the product-demo path.

For the lowest-friction local dev loop:

```bash
just infra-up
just infra-seed
just dev-be
just dev-ui
```

That keeps Postgres in Docker while running the backend and Next.js dev server on the host for faster iteration.

The infra-first dev database is published on host port `35435` to avoid common local Postgres conflicts.

Common local commands:

```bash
just check-ui
just check-be
just proto
just smoke-demo
```

For project-level development details, see:

- `snf-schedule-optimizer-ui/README.md`
- `snf-schedule-optimizer-service/README.md`

## Troubleshooting

If you want a clean restart of demo data:

```bash
docker compose -f compose.demo.yml down -v
docker compose -f compose.demo.yml up --build -d
```

If the UI loads before fresh schedule data appears, give the stack a few seconds after startup for seeding and health checks to complete.

One service is expected to exit successfully:

- `seeder`

That is normal. It is a one-shot bootstrap job, not a long-running service.
