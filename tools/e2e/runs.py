from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "tools" / "e2e" / "artifacts"
STATE_DIR = ARTIFACTS_DIR / ".state"
RESOLUTIONS_PATH = STATE_DIR / "resolutions.jsonl"
SCENARIOS_DIR = ROOT / "tools" / "e2e" / "scenarios"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect and run E2E scenario artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Run one scenario and print the artifact directory."
    )
    run_parser.add_argument("--mode", choices=["dev", "demo"], required=True)
    run_parser.add_argument("--scenario", required=True)

    run_all_parser = subparsers.add_parser(
        "run-all", help="Run every scenario and print a JSON summary."
    )
    run_all_parser.add_argument("--mode", choices=["dev", "demo"], required=True)

    subparsers.add_parser(
        "latest-failed", help="Print the latest unresolved failed artifact directory."
    )
    subparsers.add_parser(
        "latest-unresolved-failed",
        help="Print the latest unresolved failed artifact directory.",
    )
    subparsers.add_parser("unresolved-failed", help="Print unresolved failed runs as JSON.")
    subparsers.add_parser("list-scenarios", help="Print available scenario names.")

    resolve_parser = subparsers.add_parser(
        "resolve", help="Resolve a scenario, run id, or artifact path."
    )
    resolve_parser.add_argument("target")
    resolve_parser.add_argument("--mode", choices=["dev", "demo"], default="dev")

    mark_parser = subparsers.add_parser(
        "mark-resolved", help="Mark a failed run as resolved by a passing run."
    )
    mark_parser.add_argument("--failed-run", required=True)
    mark_parser.add_argument("--resolved-by", required=True)

    return parser.parse_args()


def scenario_names() -> list[str]:
    if not SCENARIOS_DIR.exists():
        return []
    return sorted(path.stem for path in SCENARIOS_DIR.glob("*.json"))


def artifact_dirs() -> list[Path]:
    if not ARTIFACTS_DIR.exists():
        return []
    return sorted(
        (path for path in ARTIFACTS_DIR.iterdir() if path.is_dir() and not path.name.startswith(".")),
        key=lambda path: path.stat().st_mtime,
    )


def read_summary(run_dir: Path) -> dict:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Run summary not found: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def relative_path(path: Path) -> str:
    resolved = path.resolve()
    return str(resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else resolved)


def load_resolutions() -> list[dict]:
    if not RESOLUTIONS_PATH.exists():
        return []

    resolutions = []
    for line in RESOLUTIONS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        resolutions.append(json.loads(line))
    return resolutions


def resolved_run_ids() -> set[str]:
    return {
        resolution["failedRunId"]
        for resolution in load_resolutions()
        if "failedRunId" in resolution
    }


def failed_run_payload(run_dir: Path, summary: dict) -> dict:
    return {
        "runId": summary.get("runId", run_dir.name),
        "runDir": relative_path(run_dir),
        "mode": summary.get("mode"),
        "scenario": summary.get("scenario"),
        "status": summary.get("status"),
        "findings": summary.get("findings", []),
    }


def unresolved_failed_runs() -> list[dict]:
    resolved = resolved_run_ids()
    runs = []
    for run_dir in reversed(artifact_dirs()):
        try:
            summary = read_summary(run_dir)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        run_id = summary.get("runId", run_dir.name)
        if summary.get("status") == "failed" and run_id not in resolved:
            runs.append(failed_run_payload(run_dir, summary))
    return runs


def latest_failed() -> Path:
    runs = unresolved_failed_runs()
    if runs:
        return (ROOT / runs[0]["runDir"]).resolve()
    raise FileNotFoundError("No failed E2E artifact run was found.")


def resolve_run_dir(target: str) -> Path | None:
    target_path = Path(target)
    if target_path.exists() and target_path.is_dir():
        return target_path.resolve()

    run_dir = ARTIFACTS_DIR / target
    if run_dir.exists() and run_dir.is_dir():
        return run_dir

    return None


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def run_scenario(mode: str, scenario: str) -> int:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "snf-schedule-optimizer-service",
            "python",
            "tools/e2e/scenario_runner.py",
            "--mode",
            mode,
            "--scenario",
            scenario,
        ],
        cwd=ROOT,
        check=False,
        text=True,
    ).returncode


def run_scenario_capture(mode: str, scenario: str) -> dict:
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "snf-schedule-optimizer-service",
            "python",
            "tools/e2e/scenario_runner.py",
            "--mode",
            mode,
            "--scenario",
            scenario,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="", file=sys.stderr)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    run_dir = None
    for line in reversed(result.stdout.splitlines()):
        candidate = Path(line.strip())
        if candidate.exists() and candidate.is_dir():
            run_dir = candidate.resolve()
            break

    if run_dir is None:
        return {
            "scenario": scenario,
            "mode": mode,
            "status": "failed",
            "exitCode": result.returncode,
            "error": "Scenario runner did not print an artifact directory.",
        }

    summary = read_summary(run_dir)
    return {
        "scenario": summary.get("scenario", scenario),
        "mode": summary.get("mode", mode),
        "runId": summary.get("runId", run_dir.name),
        "runDir": relative_path(run_dir),
        "status": summary.get("status", "failed"),
        "exitCode": result.returncode,
        "findings": summary.get("findings", []),
    }


def run_all(mode: str) -> dict:
    runs = [run_scenario_capture(mode, scenario) for scenario in scenario_names()]
    return {
        "mode": mode,
        "status": "passed"
        if all(run.get("status") == "passed" for run in runs)
        else "failed",
        "runs": runs,
    }


def mark_resolved(failed_run: str, resolved_by: str) -> dict:
    failed_dir = resolve_run_dir(failed_run)
    resolved_dir = resolve_run_dir(resolved_by)
    if failed_dir is None:
        raise FileNotFoundError(f"Failed run not found: {failed_run}")
    if resolved_dir is None:
        raise FileNotFoundError(f"Resolving run not found: {resolved_by}")

    failed_summary = read_summary(failed_dir)
    resolved_summary = read_summary(resolved_dir)
    if resolved_summary.get("status") != "passed":
        raise ValueError(
            f"Resolving run must have status 'passed': {relative_path(resolved_dir)}"
        )
    payload = {
        "failedRunId": failed_summary.get("runId", failed_dir.name),
        "failedRunDir": relative_path(failed_dir),
        "resolvedByRunId": resolved_summary.get("runId", resolved_dir.name),
        "resolvedByRunDir": relative_path(resolved_dir),
        "scenario": failed_summary.get("scenario"),
        "resolvedAt": datetime.now(UTC).isoformat(),
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with RESOLUTIONS_PATH.open("a", encoding="utf-8") as resolutions_file:
        resolutions_file.write(json.dumps(payload) + "\n")
    return payload


def resolve_target(target: str, mode: str) -> dict:
    names = scenario_names()
    if target in names:
        return {
            "kind": "scenario",
            "mode": mode,
            "scenario": target,
            "runDir": None,
        }

    run_dir = resolve_run_dir(target)
    if run_dir is None:
        raise FileNotFoundError(
            f"Target is not a scenario, run id, or artifact path: {target}"
        )

    summary = read_summary(run_dir)
    return {
        "kind": "run",
        "mode": summary.get("mode", mode),
        "scenario": summary.get("scenario"),
        "runId": summary.get("runId", run_dir.name),
        "runDir": relative_path(run_dir),
        "status": summary.get("status"),
    }


def main() -> int:
    args = parse_args()

    if args.command == "run":
        return run_scenario(args.mode, args.scenario)

    if args.command == "run-all":
        payload = run_all(args.mode)
        print_json(payload)
        return 0 if payload["status"] == "passed" else 1

    if args.command in {"latest-failed", "latest-unresolved-failed"}:
        print(relative_path(latest_failed()))
        return 0

    if args.command == "unresolved-failed":
        print_json({"runs": unresolved_failed_runs()})
        return 0

    if args.command == "list-scenarios":
        for name in scenario_names():
            print(name)
        return 0

    if args.command == "resolve":
        print_json(resolve_target(args.target, args.mode))
        return 0

    if args.command == "mark-resolved":
        print_json(mark_resolved(args.failed_run, args.resolved_by))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
