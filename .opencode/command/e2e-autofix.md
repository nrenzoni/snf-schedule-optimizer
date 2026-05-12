# E2E Autofix

Diagnose and fix a full-stack browser scenario failure using the repository E2E artifact harness.

## Arguments

Usage:

```text
/e2e-autofix [target|--all|help] [--mode dev|demo] [--max-iterations N]
```

Defaults:

- `target`: latest failed E2E run if omitted
- `mode`: `dev`
- `max-iterations`: `5`

`target` can be:

- a scenario name from `tools/e2e/scenarios/*.json`
- a run id under `tools/e2e/artifacts/`
- an artifact directory path

Use `--all` to run every scenario and fix any failures one scenario at a time.

## Help

Print help and stop when:

- the argument is `help`, `--help`, or `-h`
- no target was provided and there are no unresolved failed runs
- the target is not a scenario, run id, or artifact path
- required run metadata is missing from `summary.json`

Help text should include:

```text
Usage:
/e2e-autofix [scenario|run-id|artifact-path] [--mode dev|demo] [--max-iterations N]
/e2e-autofix --all [--mode dev|demo] [--max-iterations N]
/e2e-autofix

Examples:
/e2e-autofix dashboard_smoke
/e2e-autofix dashboard_smoke-a1b2c3d4
/e2e-autofix tools/e2e/artifacts/dashboard_smoke-a1b2c3d4
/e2e-autofix --all --mode dev

Available scenarios:
<output of: just e2e-scenarios-list>
```

## Workflow

1. Resolve the target.
   - If no target was provided, run `just e2e-scenarios-latest-failed`.
   - If a target was provided, run `just e2e-scenarios-resolve <target> <mode>`.
   - If the resolved target is a scenario, run `just e2e-scenarios <scenario> <mode>` and use the artifact directory printed by the run.
   - If the resolved target is a run, use its `runDir`.
2. Read `<runDir>/summary.json` first.
3. If `status` is `passed`, report success and stop.
4. For failed runs, inspect only the relevant artifacts needed to identify the highest-confidence product issue:
   - `<runDir>/browser/summary.json`
   - `<runDir>/browser/events.jsonl`
   - logs under `<runDir>/logs/`
   - `<runDir>/browser/failure.png` or trace artifacts only when text artifacts are insufficient
5. Fix the real product bug with the smallest correct code change. Do not loosen scenario assertions unless the assertion is clearly wrong.
6. Run the narrowest relevant validation from `AGENTS.md` for the files changed.
7. Rerun the same scenario with `just e2e-scenarios <scenario> <mode>`.
8. Use the newly printed artifact directory for the next iteration.
9. When a rerun passes, mark the original failed run as resolved with `just e2e-scenarios-mark-resolved <failedRunIdOrDir> <passingRunIdOrDir>`.
10. Repeat until the scenario passes or `max-iterations` is reached.

## Full Suite Mode

When `--all` is passed:

1. Run `just e2e-scenarios-all <mode>`.
2. If the JSON result has `status: passed`, report success and stop.
3. If one or more scenarios failed, select the first failed run with the highest severity finding. If severities are tied, use the first failed run in the JSON result.
4. Fix that single scenario using the normal failed-run workflow.
5. When the scenario passes, mark the original failed run as resolved with `just e2e-scenarios-mark-resolved <failedRunIdOrDir> <passingRunIdOrDir>`.
6. Continue with the next failed run from the original suite result unless `max-iterations` is reached.
7. After all original failed runs are resolved, run `just e2e-scenarios-all <mode>` once more.
8. If the final suite run passes, report success. If it fails, report the remaining failed run dirs and stop unless more iterations remain.

## Policy

- OpenCode owns diagnosis, code edits, validation, and the rerun loop.
- Python tools only produce and resolve artifacts; do not invoke `opencode run` from Python.
- Preserve each run directory. Never overwrite or mutate prior artifacts.
- Do not move artifact directories after a fix. Use `just e2e-scenarios-mark-resolved` to record that a failed run was fixed by a later passing run.
- Prefer real product fixes over test-only changes.
- Treat dev-server/HMR noise as ignorable unless it is clearly user-impacting.
- Stop and report if failures appear infrastructure-only or require credentials/services unavailable locally.

## Handoff

When complete, report:

- final artifact run id or path
- changed files
- validation commands run
- any skipped validation and why
