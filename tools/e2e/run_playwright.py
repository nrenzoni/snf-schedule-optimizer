from __future__ import annotations

import argparse
import os
import subprocess
import uuid
from pathlib import Path

from tools.e2e.dev_stack import DevStack, build_dev_stack_config


ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "snf-schedule-optimizer-ui"
ARTIFACTS_DIR = ROOT / "tools" / "e2e" / "artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Playwright with a managed local E2E stack.")
    parser.add_argument("playwright_args", nargs="*", help="Arguments passed to Playwright test.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = f"playwright-{uuid.uuid4().hex[:8]}"
    run_dir = ARTIFACTS_DIR / run_id
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    stack = DevStack(build_dev_stack_config(run_id, logs_dir))
    env = os.environ.copy()

    try:
        stack.start()
        playwright_env = env | {
            "NEXT_PUBLIC_API_BASE_URL": stack.config.api_url,
            "NEXT_PUBLIC_E2E_RUN_ID": run_id,
            "PLAYWRIGHT_BASE_URL": stack.config.ui_url,
        }
        command = [
            "node",
            "node_modules/@playwright/test/cli.js",
            "test",
            "--workers=1",
            *args.playwright_args,
        ]
        return subprocess.run(
            command,
            cwd=UI_DIR,
            env=playwright_env,
            check=False,
            text=True,
        ).returncode
    finally:
        stack.stop()


if __name__ == "__main__":
    raise SystemExit(main())
