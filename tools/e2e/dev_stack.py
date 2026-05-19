from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "snf-schedule-optimizer-ui"
SERVICE_DIR = ROOT / "snf-schedule-optimizer-service"
LOCAL_HOST = "127.0.0.1"
DEV_DATABASE_URL = os.environ.get(
    "DATABASE_URL_LOCAL",
    "postgresql+asyncpg://snf_user:snf_password@localhost:35435/snf_optimizer_demo",
)
API_PORT_CANDIDATES = [8000, *range(8100, 8120)]
UI_PORT_CANDIDATES = [3000, *range(3100, 3120)]


@dataclass(frozen=True)
class DevStackConfig:
    run_id: str
    api_port: int
    ui_port: int
    logs_dir: Path

    @property
    def api_url(self) -> str:
        return f"http://localhost:{self.api_port}"

    @property
    def ui_url(self) -> str:
        return f"http://localhost:{self.ui_port}"


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    log_file: object


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


def choose_available_port(candidates: list[int], *, used: set[int] | None = None) -> int:
    claimed = used or set()
    for candidate in candidates:
        if candidate in claimed:
            continue
        if not port_is_open(candidate):
            return candidate
    raise RuntimeError(f"No available port found in candidate set: {candidates}")


def run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path = ROOT,
) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def ensure_playwright_browser() -> None:
    marker = Path.home() / ".cache" / "ms-playwright"
    if marker.exists() and any(marker.iterdir()):
        return
    run_command(["pnpm", "exec", "playwright", "install", "chromium"], cwd=UI_DIR)


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
    return ManagedProcess(name=name, process=process, log_file=log_file)


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


def build_dev_stack_config(run_id: str, logs_dir: Path) -> DevStackConfig:
    api_port = choose_available_port(API_PORT_CANDIDATES)
    ui_port = choose_available_port(UI_PORT_CANDIDATES, used={api_port})
    return DevStackConfig(
        run_id=run_id,
        api_port=api_port,
        ui_port=ui_port,
        logs_dir=logs_dir,
    )


class DevStack:
    def __init__(self, config: DevStackConfig):
        self.config = config
        self._managed: list[ManagedProcess] = []

    def start(self) -> None:
        env_base = os.environ.copy()
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)

        ensure_playwright_browser()
        run_command(["just", "infra-up"])
        run_command(["just", "infra-seed"])

        backend_env = env_base | {
            "PYTHONPATH": "src",
            "DATABASE_URL": DEV_DATABASE_URL,
            "PORT": str(self.config.api_port),
            "CORS_ALLOW_ORIGINS": (
                f"http://localhost:{self.config.ui_port},"
                f"http://127.0.0.1:{self.config.ui_port}"
            ),
        }
        worker_env = env_base | {
            "PYTHONPATH": "src",
            "DATABASE_URL": DEV_DATABASE_URL,
            "OPTIMIZATION_WORKER_ID": f"e2e-worker-{self.config.run_id}",
        }
        ui_env = env_base | {
            "NEXT_PUBLIC_API_BASE_URL": self.config.api_url,
            "NEXT_PUBLIC_E2E_RUN_ID": self.config.run_id,
        }

        run_command(["pnpm", "build"], env=ui_env, cwd=UI_DIR)

        self._managed.append(
            start_process(
                "backend",
                ["uv", "run", "python", "-m", "snf_schedule_optimizer.api.main"],
                env=backend_env,
                cwd=SERVICE_DIR,
                log_path=self.config.logs_dir / "backend.log",
            )
        )
        self._managed.append(
            start_process(
                "ui",
                ["pnpm", "exec", "next", "start", "--port", str(self.config.ui_port)],
                env=ui_env,
                cwd=UI_DIR,
                log_path=self.config.logs_dir / "ui.log",
            )
        )
        self._managed.append(
            start_process(
                "worker",
                ["uv", "run", "python", "-m", "snf_schedule_optimizer.api.worker_main"],
                env=worker_env,
                cwd=SERVICE_DIR,
                log_path=self.config.logs_dir / "worker.log",
            )
        )

        wait_for_url(f"{self.config.api_url}/health")
        wait_for_url(self.config.ui_url)

    def stop(self) -> None:
        for proc in reversed(self._managed):
            terminate_process_group(proc.process)
            proc.log_file.close()
        self._managed.clear()
