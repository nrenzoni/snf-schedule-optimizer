# Tools

This directory contains repo-level automation that supports full-stack browser validation and OpenCode-driven fix loops.

## E2E Harness

The `tools/e2e` workflow is split into deterministic layers:

- `scenario_runner.py`: starts the stack, captures logs, waits for health, runs a browser scenario, and writes artifacts.
- `runs.py`: lists scenarios, resolves prior runs, finds the latest failed run, and delegates single scenario runs. It never invokes OpenCode.
- `.opencode/command/e2e-autofix.md`: OpenCode-owned command for diagnosing a failed run, changing code, validating, and rerunning scenarios until the issue is fixed.
- `scenarios/*.json`: declarative browser scenarios for agent mode.
- `schemas/scenario.schema.json`: schema for scenario manifests.

The Playwright browser driver lives under `snf-schedule-optimizer-ui/tests/e2e` so it can use the UI package's existing Playwright and TypeScript toolchain without creating a second Node environment.

## Artifact Layout

Each run writes into `tools/e2e/artifacts/<run-id>/`.

- `summary.json`: machine-readable run outcome and findings.
- `logs/`: backend, UI, and optional compose logs.
- `browser/`: browser summary, events, screenshots, and trace output.

Shared E2E state writes into `tools/e2e/artifacts/.state/`.

- `resolutions.jsonl`: append-only registry mapping failed runs to later passing runs that resolved them.

OpenCode should inspect `summary.json` first, then `events.jsonl`, then the relevant logs and browser artifacts.

The top-level `summary.json` includes the stable handoff fields `runId`, `runDir`, `mode`, `scenario`, and `status`. Pass either `runId` or `runDir` to `/e2e-autofix` to continue from a previous run. Artifact directories are immutable; resolved failures are recorded in `.state/resolutions.jsonl` instead of moved.

## Recommended Commands

Run a single JSON scenario against the host-dev stack:

```bash
just e2e-scenarios dashboard_smoke dev
```

Run a single JSON scenario against the demo compose stack:

```bash
just e2e-scenarios dashboard_smoke demo
```

List supported JSON scenarios:

```bash
just e2e-scenarios-list
```

Run all JSON scenarios:

```bash
just e2e-scenarios-all dev
```

Inspect unresolved failures:

```bash
just e2e-scenarios-unresolved
just e2e-scenarios-latest-failed
```

Mark a failed run as resolved by a later passing run:

```bash
just e2e-scenarios-mark-resolved dashboard_smoke-a1b2c3d4 dashboard_smoke-e5f6a7b8
```

Trigger the OpenCode-owned autofix loop from inside OpenCode:

```text
/e2e-autofix full_navigation --mode dev
/e2e-autofix full_navigation-a1b2c3d4
/e2e-autofix tools/e2e/artifacts/full_navigation-a1b2c3d4
/e2e-autofix --all --mode dev
/e2e-autofix
```

## Agent Policy

The harness classifies findings conservatively:

- high: crashes, page errors, failed API requests, assertion failures
- medium: app console errors and visible degraded states
- low: warnings and other likely noise

The OpenCode slash-command keeps retrying until the scenario passes or it hits the configured iteration cap.

## LAN-Origin Scope

Agent E2E runs use localhost origins and intentionally do not validate arbitrary LAN browser origins. For manual LAN-origin development, configure `EXTRA_DEV_ORIGINS` for backend CORS and `NEXT_ALLOWED_DEV_ORIGINS` for Next.js dev origins as documented in the root README.

Managed Playwright and scenario runs start their own isolated local stack, inject explicit UI/API base URLs, and should not depend on a separately running `just dev-be` or `just dev-ui` session.
