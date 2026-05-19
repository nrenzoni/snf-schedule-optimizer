# Agent Workflow

## Justfile Hierarchy

- `justfile`: Thin orchestrator and cross-cutting recipes (infra, demo, e2e, codegen).
- `snf-schedule-optimizer-ui/justfile`: UI install, lint, typecheck, test, build, dev, check.
- `snf-schedule-optimizer-service/justfile`: Backend install, lint, format, typecheck, test, dev, dev-worker, check.
- `proto/justfile`: Protobuf code generation.

Child justfiles are self-contained. Use `just <recipe>` from within a subdirectory or use root-level prefixed commands (`just lint-ui`, `just check-be`) from anywhere.

## Default Local Dev Loop

- Use `just` as the source of truth for local commands.
- Use `compose.dev.yml` for local infra only.
- Use `compose.demo.yml` only for full-stack smoke validation.

Recommended local loop:

```bash
just infra-up
just infra-seed
just dev-be
just dev-ui
```

The dev database is published on host port `35435` to avoid common local Postgres conflicts.

## LAN-Origin Development

- Agent/browser E2E uses localhost origins by design and should not include generic CORS probes.
- If debugging a browser opened through a LAN origin, check `EXTRA_DEV_ORIGINS` for backend CORS and `NEXT_ALLOWED_DEV_ORIGINS` for Next.js dev asset origins.
- `EXTRA_DEV_ORIGINS` values are full origins, such as `http://192.168.5.101:3000`.
- `NEXT_ALLOWED_DEV_ORIGINS` values are hostnames or host:port entries without protocol, such as `192.168.5.101`.

## Repo Areas

- `snf-schedule-optimizer-ui/`: Next.js frontend
- `snf-schedule-optimizer-service/`: Python backend
- `proto/`: shared protobuf schema and generated code inputs
- `compose.dev.yml`: infra-first local development
- `compose.demo.yml`: full demo stack smoke validation

## Validation Rules

- If `snf-schedule-optimizer-ui/**` changes:
  - Run `just check-ui`
- If `snf-schedule-optimizer-service/**` changes:
  - Run `just auto-fix-format-be`
  - Run `just check-be`
- If `proto/**` changes:
  - Run `just proto`
  - Then run `just check-ui`
  - Then run `just check-be`
- If `compose*.yml`, `Dockerfile*`, `justfile`, or CI config changes:
  - Run the relevant fast checks
  - Run `just smoke-demo` if container/demo behavior may be affected
- If `snf-schedule-optimizer-ui/tests/e2e/**` changes or the user-facing workflow changes:
  - Run `just test-e2e`

## Validate Then Fix

1. Detect which repo areas changed.
2. Run the narrowest relevant validation first.
3. If a command fails, fix the failure before expanding scope.
4. Re-run the failing command until it passes.
5. Run broader checks only after targeted checks pass.
6. Before handoff, summarize what was validated and anything not fully verified.

## Compose Rules

- Do not use `compose.demo.yml` as the default coding loop.
- Prefer host dev servers for UI and backend iteration speed.
- Use `compose.dev.yml` for Postgres and bootstrap helpers.
- Use `compose.demo.yml` for manual smoke validation, especially after Docker or compose changes.

## Proto Rules

- `proto` changes affect both frontend and backend.
- Regenerate code before linting or testing dependents.
- Treat generated diffs as part of the change and validate both sides.

## Handoff Expectations

- Report which `just` commands were run.
- Report any skipped validation and why.
- Keep edits minimal and aligned with existing architecture.
