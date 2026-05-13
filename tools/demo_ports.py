from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "tools" / ".demo-smoke.env"
API_ENV_KEY = "DEMO_API_PORT"
UI_ENV_KEY = "DEMO_UI_PORT"
API_CANDIDATES = [8080, *range(8180, 8200)]
UI_CANDIDATES = [3000, *range(3100, 3120)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve stable host ports for demo compose runs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("resolve", "write-env", "show", "clear"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--path", default=str(DEFAULT_STATE_PATH))

    subparsers.add_parser("state-path")

    return parser.parse_args()


def parse_port(value: str, label: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer, got: {value}") from exc

    if not 1 <= port <= 65535:
        raise ValueError(f"{label} must be between 1 and 65535, got: {value}")
    return port


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key and value:
            values[key.strip()] = value.strip()
    return values


def write_env_file(path: Path, values: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def is_url_healthy(url: str) -> bool:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def demo_stack_healthy(api_port: int, ui_port: int) -> bool:
    return is_url_healthy(f"http://localhost:{api_port}/health") and is_url_healthy(
        f"http://localhost:{ui_port}"
    )


def choose_available_port(candidates: list[int], *, used: set[int]) -> int:
    for candidate in candidates:
        if candidate in used:
            continue
        if is_port_free(candidate):
            return candidate
    raise RuntimeError(f"No free port available in candidate set: {candidates}")


def existing_state_ports(path: Path) -> tuple[int, int] | None:
    state = read_env_file(path)
    api_value = state.get(API_ENV_KEY)
    ui_value = state.get(UI_ENV_KEY)
    if not api_value or not ui_value:
        return None

    api_port = parse_port(api_value, API_ENV_KEY)
    ui_port = parse_port(ui_value, UI_ENV_KEY)
    if api_port == ui_port:
        return None
    return api_port, ui_port


def resolve_ports(path: Path) -> dict[str, int]:
    explicit_api = os.getenv(API_ENV_KEY)
    explicit_ui = os.getenv(UI_ENV_KEY)

    if explicit_api or explicit_ui:
        used: set[int] = set()
        api_port = (
            parse_port(explicit_api, API_ENV_KEY)
            if explicit_api
            else choose_available_port(API_CANDIDATES, used=used)
        )
        used.add(api_port)
        ui_port = (
            parse_port(explicit_ui, UI_ENV_KEY)
            if explicit_ui
            else choose_available_port(UI_CANDIDATES, used=used)
        )
        if api_port == ui_port:
            raise RuntimeError("DEMO_API_PORT and DEMO_UI_PORT must be different")
        return {API_ENV_KEY: api_port, UI_ENV_KEY: ui_port}

    if state_ports := existing_state_ports(path):
        api_port, ui_port = state_ports
        if demo_stack_healthy(api_port, ui_port) or (
            is_port_free(api_port) and is_port_free(ui_port)
        ):
            return {API_ENV_KEY: api_port, UI_ENV_KEY: ui_port}

    api_port = choose_available_port(API_CANDIDATES, used=set())
    ui_port = choose_available_port(UI_CANDIDATES, used={api_port})
    return {API_ENV_KEY: api_port, UI_ENV_KEY: ui_port}


def print_env(values: dict[str, int]) -> None:
    for key, value in values.items():
        print(f"{key}={value}")


def print_show(path: Path, values: dict[str, int]) -> None:
    payload = {
        "statePath": str(path.relative_to(ROOT)),
        "apiPort": values[API_ENV_KEY],
        "uiPort": values[UI_ENV_KEY],
        "apiUrl": f"http://localhost:{values[API_ENV_KEY]}",
        "uiUrl": f"http://localhost:{values[UI_ENV_KEY]}",
    }
    print(json.dumps(payload, indent=2))


def main() -> int:
    args = parse_args()

    if args.command == "state-path":
        print(DEFAULT_STATE_PATH.relative_to(ROOT))
        return 0

    path = Path(args.path)

    if args.command == "clear":
        path.unlink(missing_ok=True)
        return 0

    values = resolve_ports(path)

    if args.command == "resolve":
        print_env(values)
        return 0

    if args.command == "write-env":
        write_env_file(path, values)
        print_env(values)
        return 0

    if args.command == "show":
        print_show(path, values)
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
