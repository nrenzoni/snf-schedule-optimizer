from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "tools" / "e2e" / "artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous OpenCode browser autofix loop.")
    parser.add_argument("--mode", choices=["dev", "demo"], required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--max-iterations", type=int, default=5)
    return parser.parse_args()


def latest_run_dir(previous: set[Path]) -> Path:
    candidates = sorted(ARTIFACTS_DIR.glob("*"), key=lambda path: path.stat().st_mtime)
    for candidate in reversed(candidates):
        if candidate not in previous:
            return candidate
    raise FileNotFoundError("No new artifact directory was created.")


def run_orchestrator(mode: str, scenario: str) -> tuple[int, Path]:
    previous = set(ARTIFACTS_DIR.glob("*")) if ARTIFACTS_DIR.exists() else set()
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "snf-schedule-optimizer-service",
            "python",
            "tools/e2e/orchestrator.py",
            "--mode",
            mode,
            "--scenario",
            scenario,
        ],
        cwd=ROOT,
        check=False,
        text=True,
    )
    return result.returncode, latest_run_dir(previous)


def invoke_opencode(run_dir: Path, mode: str, scenario: str) -> int:
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    prompt = f"""A full-stack browser scenario failed in this repository.

Mode: {mode}
Scenario: {scenario}
Artifact directory: {run_dir}
Summary file: {summary_path}

Task:
1. Read the run summary, browser events, and relevant logs from the artifact directory.
2. Identify the highest-confidence real bug causing the failure.
3. Fix the code in this repository.
4. Run only the narrowest relevant validation required by the repository instructions after your fix.
5. Do not stop at analysis; make the code change.

Prioritize real product fixes over loosening assertions. Ignore likely dev-server noise unless it is clearly user-impacting.
"""

    return subprocess.run(
        [
            "opencode",
            "run",
            prompt,
            "--dir",
            str(ROOT),
            "--dangerously-skip-permissions",
        ],
        cwd=ROOT,
        check=False,
        text=True,
    ).returncode


def main() -> int:
    args = parse_args()

    for _ in range(args.max_iterations):
        exit_code, run_dir = run_orchestrator(args.mode, args.scenario)
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        if exit_code == 0 and summary.get("status") == "passed":
            print(str(run_dir))
            return 0

        opencode_exit = invoke_opencode(run_dir, args.mode, args.scenario)
        if opencode_exit != 0:
            return opencode_exit

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
