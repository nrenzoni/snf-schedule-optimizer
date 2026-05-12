from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import IO


ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "snf-schedule-optimizer-ui"
SERVICE_DIR = ROOT / "snf-schedule-optimizer-service"
ARTIFACTS_DIR = ROOT / "tools" / "e2e" / "artifacts"
LOCAL_HOST = "127.0.0.1"


class ManagedProcess:
    def __init__(self, name: str, process: subprocess.Popen[str], log_file: IO[str]):
        self.name = name
        self.process = process
        self.log_file = log_file

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.log_file.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-stack E2E scenario orchestration.")
    parser.add_argument("--mode", choices=["dev", "demo"], required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--artifacts-root", default=str(ARTIFACTS_DIR))
    parser.add_argument("--reuse-stack", action="store_true")
    return parser.parse_args()


def run_command(command: list[str], *, env: dict[str, str] | None = None, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def ensure_playwright_browser() -> None:
    marker = Path.home() / ".cache" / "ms-playwright"
    if marker.exists() and any(marker.iterdir()):
        return
    run_command(["pnpm", "exec", "playwright", "install", "chromium"], cwd=UI_DIR)


def start_process(
    name: str,
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    log_path: Path,
) -> ManagedProcess:
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    return ManagedProcess(name, process, log_file)


def port_is_open(port: int, host: str = LOCAL_HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def choose_port(preferred: int, fallback: int) -> int:
    if not port_is_open(preferred):
        return preferred
    if not port_is_open(fallback):
        return fallback
    raise RuntimeError(
        f"Neither preferred port {preferred} nor fallback port {fallback} is available."
    )


def wait_for_url(url: str, timeout_seconds: int = 120) -> None:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if 200 <= response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}")


def terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=5)


def run_dev_mode(run_id: str, run_dir: Path, scenario_path: Path) -> int:
    logs_dir = run_dir / "logs"
    browser_dir = run_dir / "browser"
    logs_dir.mkdir(parents=True, exist_ok=True)
    browser_dir.mkdir(parents=True, exist_ok=True)

    env_base = os.environ.copy()
    api_port = choose_port(8000, 8100)
    ui_port = choose_port(3000, 3100)
    api_url = f"http://localhost:{api_port}"
    ui_url = f"http://localhost:{ui_port}"

    ensure_playwright_browser()

    run_command(["just", "infra-up"])
    run_command(["just", "infra-seed"])

    backend_env = env_base | {
        "PYTHONPATH": "src",
        "DATABASE_URL": "postgresql+asyncpg://snf_user:snf_password@localhost:35435/snf_optimizer_demo",
        "PORT": str(api_port),
        "CORS_ALLOW_ORIGINS": f"http://localhost:{ui_port},http://127.0.0.1:{ui_port}",
    }
    ui_env = env_base | {
        "NEXT_PUBLIC_API_BASE_URL": api_url,
        "NEXT_PUBLIC_E2E_RUN_ID": run_id,
    }
    driver_env = env_base | {
        "E2E_RUN_ID": run_id,
        "E2E_API_BASE_URL": api_url,
        "E2E_BASE_URL": ui_url,
        "E2E_ARTIFACTS_DIR": str(browser_dir),
        "E2E_SCENARIO_PATH": str(scenario_path),
    }

    managed: list[ManagedProcess] = []
    try:
        managed.append(
            start_process(
                "backend",
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "snf_schedule_optimizer.api.main",
                ],
                env=backend_env,
                cwd=SERVICE_DIR,
                log_path=logs_dir / "backend.log",
            )
        )
        managed.append(
            start_process(
                "ui",
                ["pnpm", "dev", "--port", str(ui_port)],
                env=ui_env,
                cwd=UI_DIR,
                log_path=logs_dir / "ui.log",
            )
        )

        wait_for_url(f"{api_url}/health")
        wait_for_url(ui_url)

        return subprocess.run(
            ["pnpm", "exec", "tsx", "tests/e2e/scenario-driver.ts"],
            cwd=UI_DIR,
            env=driver_env,
            check=False,
        ).returncode
    finally:
        for proc in reversed(managed):
            terminate_process_group(proc.process)
            proc.log_file.close()


def run_demo_mode(run_id: str, run_dir: Path, scenario_path: Path) -> int:
    logs_dir = run_dir / "logs"
    browser_dir = run_dir / "browser"
    logs_dir.mkdir(parents=True, exist_ok=True)
    browser_dir.mkdir(parents=True, exist_ok=True)

    env_base = os.environ.copy()
    api_port = choose_port(8080, 8180)
    ui_port = choose_port(3000, 3100)
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
    up = subprocess.Popen(
        ["docker", "compose", "-f", "compose.demo.yml", "up", "--build", "-d"],
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
            ["docker", "compose", "-f", "compose.demo.yml", "logs", "app", "ui", "db"],
            cwd=ROOT,
            env=compose_env,
            stdout=compose_log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
        compose_log.close()
        subprocess.run(
            ["docker", "compose", "-f", "compose.demo.yml", "down", "-v"],
            cwd=ROOT,
            env=compose_env,
            check=False,
            text=True,
        )


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
