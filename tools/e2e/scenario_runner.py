from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from tools.demo_ports import DEFAULT_STATE_PATH, resolve_ports, write_env_file
from tools.e2e.dev_stack import (
    DevStack,
    build_dev_stack_config,
    ensure_playwright_browser,
    wait_for_url,
)


ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "snf-schedule-optimizer-ui"
ARTIFACTS_DIR = ROOT / "tools" / "e2e" / "artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-stack E2E scenario orchestration.")
    parser.add_argument("--mode", choices=["dev", "demo"], required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--artifacts-root", default=str(ARTIFACTS_DIR))
    return parser.parse_args()


def run_command(command: list[str], *, env: dict[str, str] | None = None, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def run_dev_mode(run_id: str, run_dir: Path, scenario_path: Path) -> int:
    logs_dir = run_dir / "logs"
    browser_dir = run_dir / "browser"
    logs_dir.mkdir(parents=True, exist_ok=True)
    browser_dir.mkdir(parents=True, exist_ok=True)

    env_base = os.environ.copy()
    stack = DevStack(build_dev_stack_config(run_id, logs_dir))
    driver_env = env_base | {
        "E2E_RUN_ID": run_id,
        "E2E_API_BASE_URL": stack.config.api_url,
        "E2E_BASE_URL": stack.config.ui_url,
        "E2E_ARTIFACTS_DIR": str(browser_dir),
        "E2E_SCENARIO_PATH": str(scenario_path),
    }

    try:
        stack.start()
        return subprocess.run(
            ["pnpm", "exec", "tsx", "tests/e2e/scenario-driver.ts"],
            cwd=UI_DIR,
            env=driver_env,
            check=False,
        ).returncode
    finally:
        stack.stop()


def run_demo_mode(run_id: str, run_dir: Path, scenario_path: Path) -> int:
    logs_dir = run_dir / "logs"
    browser_dir = run_dir / "browser"
    logs_dir.mkdir(parents=True, exist_ok=True)
    browser_dir.mkdir(parents=True, exist_ok=True)

    env_base = os.environ.copy()
    state_path = run_dir / DEFAULT_STATE_PATH.name
    ports = resolve_ports(state_path)
    write_env_file(state_path, ports)
    api_port = ports["DEMO_API_PORT"]
    ui_port = ports["DEMO_UI_PORT"]
    api_url = f"http://localhost:{api_port}"
    ui_url = f"http://localhost:{ui_port}"
    ensure_playwright_browser()
    driver_env = env_base | {
        "E2E_RUN_ID": run_id,
        "E2E_API_BASE_URL": api_url,
        "E2E_BASE_URL": ui_url,
        "E2E_ARTIFACTS_DIR": str(browser_dir),
        "E2E_SCENARIO_PATH": str(scenario_path),
    }
    compose_env = env_base | {
        "DEMO_API_PORT": str(api_port),
        "DEMO_UI_PORT": str(ui_port),
    }

    compose_log = (logs_dir / "compose.log").open("w", encoding="utf-8")
    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(state_path),
            "-f",
            "compose.demo.yml",
            "down",
            "-v",
        ],
        cwd=ROOT,
        env=compose_env,
        stdout=compose_log,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    up = subprocess.Popen(
        [
            "docker",
            "compose",
            "--env-file",
            str(state_path),
            "-f",
            "compose.demo.yml",
            "up",
            "--build",
            "-d",
        ],
        cwd=ROOT,
        env=compose_env,
        stdout=compose_log,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    up.wait(timeout=600)
    if up.returncode != 0:
        compose_log.close()
        return up.returncode

    try:
        wait_for_url(f"{api_url}/health", timeout_seconds=180)
        wait_for_url(ui_url, timeout_seconds=180)

        return subprocess.run(
            ["pnpm", "exec", "tsx", "tests/e2e/scenario-driver.ts"],
            cwd=UI_DIR,
            env=driver_env,
            check=False,
        ).returncode
    finally:
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(state_path),
                "-f",
                "compose.demo.yml",
                "logs",
                "app",
                "ui",
                "db",
            ],
            cwd=ROOT,
            env=compose_env,
            stdout=compose_log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(state_path),
                "-f",
                "compose.demo.yml",
                "down",
                "-v",
            ],
            cwd=ROOT,
            env=compose_env,
            stdout=compose_log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
        compose_log.close()
        state_path.unlink(missing_ok=True)


def classify_findings(summary: dict) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    failures = summary.get("failures", [])
    for failure in failures:
        severity = "medium"
        failure_type = failure.get("type", "failure")
        if failure_type in {
            "pageerror",
            "requestfailure",
            "assertion",
            "step_failure",
            "response",
        }:
            severity = "high"
        findings.append(
            {
                "severity": severity,
                "type": failure_type,
                "message": failure.get("message", "Unknown failure"),
            }
        )
    return findings


def write_run_summary(
    run_dir: Path,
    run_id: str,
    mode: str,
    scenario: str,
    runner_error: str | None = None,
) -> None:
    summary_path = run_dir / "browser" / "summary.json"
    if not summary_path.exists():
        summary = {
            "status": "failed",
            "runId": run_id,
            "mode": mode,
            "scenario": scenario,
            "failures": [
                {
                    "type": "runner",
                    "message": runner_error or "Browser summary.json was not produced.",
                }
            ],
        }
    else:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    result = {
        "runId": run_id,
        "runDir": str(run_dir.relative_to(ROOT)),
        "mode": mode,
        "scenario": scenario,
        "status": summary.get("status", "failed"),
        "browserSummary": str(summary_path.relative_to(run_dir)),
        "events": "browser/events.jsonl",
        "logs": {
            "backend": "logs/backend.log",
            "ui": "logs/ui.log",
            "compose": "logs/compose.log",
        },
        "findings": classify_findings(summary),
        "failures": summary.get("failures", []),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    run_id = f"{args.scenario}-{uuid.uuid4().hex[:8]}"
    run_dir = Path(args.artifacts_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = ROOT / "tools" / "e2e" / "scenarios" / f"{args.scenario}.json"
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")

    exit_code = 1
    runner_error = None
    try:
        if args.mode == "dev":
            exit_code = run_dev_mode(run_id, run_dir, scenario_path)
        else:
            exit_code = run_demo_mode(run_id, run_dir, scenario_path)
    except Exception as error:
        runner_error = f"{type(error).__name__}: {error}"
        print(runner_error, file=sys.stderr)

    write_run_summary(run_dir, run_id, args.mode, args.scenario, runner_error)
    print(str(run_dir))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
