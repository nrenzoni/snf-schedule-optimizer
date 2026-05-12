# Tools

This directory contains repo-level automation that supports full-stack browser validation and autonomous fix loops.

## E2E Harness

The `tools/e2e` workflow is split into deterministic layers:

- `orchestrator.py`: starts the stack, captures logs, waits for health, runs a browser scenario, and writes artifacts.
- `autofix.py`: reruns the orchestrator until the scenario passes, invoking OpenCode CLI between failed runs.
- `scenarios/*.json`: declarative browser scenarios for agent mode.
- `schemas/scenario.schema.json`: schema for scenario manifests.

The Playwright browser driver lives under `snf-schedule-optimizer-ui/tests/e2e` so it can use the UI package's existing Playwright and TypeScript toolchain without creating a second Node environment.

## Artifact Layout

Each run writes into `tools/e2e/artifacts/<run-id>/`.

- `summary.json`: machine-readable run outcome and findings.
- `events.jsonl`: one JSON event per browser step.
- `logs/`: backend, UI, and optional compose logs.
- `browser/`: screenshots and trace output.

OpenCode should inspect `summary.json` first, then `events.jsonl`, then the relevant logs and browser artifacts.

## Recommended Commands

Run a single scenario against the host-dev stack:

```bash
just e2e-agent-dev scenario=dashboard_smoke
```

Run a single scenario against the demo compose stack:

```bash
just e2e-agent-demo scenario=dashboard_smoke
```

Run the autonomous fix loop:

```bash
just e2e-agent-autofix scenario=full_navigation mode=dev
```

## Agent Policy

The harness classifies findings conservatively:

- high: crashes, page errors, failed API requests, assertion failures
- medium: app console errors and visible degraded states
- low: warnings and other likely noise

The autonomous loop keeps retrying until the scenario passes or it hits the configured iteration cap.

## LAN-Origin Scope

Agent E2E runs use localhost origins and intentionally do not validate arbitrary LAN browser origins. For manual LAN-origin development, configure `EXTRA_DEV_ORIGINS` for backend CORS and `NEXT_ALLOWED_DEV_ORIGINS` for Next.js dev origins as documented in the root README.
