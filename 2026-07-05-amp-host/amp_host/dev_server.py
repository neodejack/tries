from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "dev-ports.json"
BIND_HOST = "127.0.0.1"
PUBLIC_HOST = "localhost"
HEALTH_TIMEOUT_SECONDS = 5.0
SHUTDOWN_TIMEOUT_SECONDS = 5.0


class DevServerError(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in {"run", "down"}:
        print("Usage: python -m amp_host.dev_server {run [port]|down}", file=sys.stderr)
        return 2

    command = argv.pop(0)
    try:
        if command == "run":
            port = _parse_port(argv[0] if argv else "8765")
            if len(argv) > 1:
                raise DevServerError("run accepts at most one port argument", 2)
            return run(port)
        return down(allow_missing=False)
    except DevServerError as error:
        print(error, file=sys.stderr)
        return error.exit_code


def run(port: int) -> int:
    down_result = down(allow_missing=True)
    if down_result not in {0, 1}:
        return down_result

    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "flask",
            "--app",
            "amp_host",
            "run",
            "--host",
            BIND_HOST,
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
    )

    try:
        _wait_until_healthy(child, port)
        _write_registry(port, child.pid)
        print(f"Registered dev server in {REGISTRY_PATH}", flush=True)
        return _normalize_child_exit(child.wait())
    except KeyboardInterrupt:
        _terminate_child(child)
        return 130
    except DevServerError:
        _terminate_child(child)
        raise
    finally:
        _remove_registry_if_owned(child.pid)


def down(*, allow_missing: bool) -> int:
    if not REGISTRY_PATH.exists():
        message = f"No {REGISTRY_PATH.name} found; no dev server is registered."
        if allow_missing:
            print(message, flush=True)
            return 1
        raise DevServerError(message, 1)

    registry = _read_registry()
    server = _validate_registry_shape(registry)
    pid = server["pid"]
    port = server["port"]

    command = _process_command(pid)
    if command is None:
        raise DevServerError(_stale_message(f"registered PID {pid} is not running", server), 2)
    if not _looks_like_amp_host_flask(command):
        raise DevServerError(
            _stale_message(
                f"registered PID {pid} does not look like the Amp Host Flask server:\n  {command}",
                server,
            ),
            2,
        )
    if not _pid_listens_on_port(pid, port):
        raise DevServerError(
            _stale_message(f"registered PID {pid} is not listening on port {port}", server),
            2,
        )

    if not _terminate_pid(pid):
        raise DevServerError(
            f"Found registered dev server PID {pid}, but it did not stop.\n"
            f"Left {REGISTRY_PATH} in place. Inspect it and the process manually.",
            3,
        )

    REGISTRY_PATH.unlink(missing_ok=True)
    print(f"Stopped dev server PID {pid} and removed {REGISTRY_PATH.name}.", flush=True)
    return 0


def _normalize_child_exit(return_code: int) -> int:
    if return_code in {-signal.SIGTERM, -signal.SIGINT}:
        return 0
    return return_code


def _parse_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as error:
        raise DevServerError(f"Invalid port: {raw!r}", 2) from error
    if port < 1 or port > 65535:
        raise DevServerError(f"Invalid port {port}; expected 1-65535", 2)
    return port


def _wait_until_healthy(child: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    url = f"http://{PUBLIC_HOST}:{port}/api/config"
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        return_code = child.poll()
        if return_code is not None:
            raise DevServerError(f"Flask exited before becoming healthy with code {return_code}.", return_code or 1)

        try:
            with urllib.request.urlopen(url, timeout=0.25) as response:
                if 200 <= response.status < 300 and _pid_listens_on_port(child.pid, port):
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        time.sleep(0.1)

    detail = f" Last error: {last_error}" if last_error else ""
    raise DevServerError(f"Dev server did not become healthy at {url} within 5 seconds.{detail}", 1)


def _write_registry(port: int, pid: int) -> None:
    url = f"http://{PUBLIC_HOST}:{port}"
    REGISTRY_PATH.write_text(
        json.dumps(
            {
                "dev-server": {
                    "host": PUBLIC_HOST,
                    "port": port,
                    "url": url,
                    "pid": pid,
                }
            },
            indent=2,
        )
        + "\n"
    )


def _remove_registry_if_owned(pid: int) -> None:
    if not REGISTRY_PATH.exists():
        return
    try:
        registry = json.loads(REGISTRY_PATH.read_text())
        server = registry.get("dev-server", {})
    except (OSError, json.JSONDecodeError):
        return
    if server.get("pid") == pid:
        REGISTRY_PATH.unlink(missing_ok=True)


def _read_registry() -> dict[str, Any]:
    try:
        loaded = json.loads(REGISTRY_PATH.read_text())
    except json.JSONDecodeError as error:
        raise DevServerError(
            _manual_recovery_message(f"{REGISTRY_PATH} is not valid JSON: {error}"),
            2,
        ) from error
    except OSError as error:
        raise DevServerError(f"Could not read {REGISTRY_PATH}: {error}", 2) from error
    if not isinstance(loaded, dict):
        raise DevServerError(_manual_recovery_message(f"{REGISTRY_PATH} must contain a JSON object"), 2)
    return loaded


def _validate_registry_shape(registry: dict[str, Any]) -> dict[str, Any]:
    server = registry.get("dev-server")
    if not isinstance(server, dict):
        raise DevServerError(_manual_recovery_message("dev-ports.json is missing object key 'dev-server'"), 2)
    pid = server.get("pid")
    port = server.get("port")
    if not isinstance(pid, int):
        raise DevServerError(_manual_recovery_message("dev-ports.json field dev-server.pid must be an integer"), 2)
    if not isinstance(port, int):
        raise DevServerError(_manual_recovery_message("dev-ports.json field dev-server.port must be an integer"), 2)
    return server


def _process_command(pid: int) -> str | None:
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    command = completed.stdout.strip()
    if completed.returncode != 0 or not command:
        return None
    return command


def _looks_like_amp_host_flask(command: str) -> bool:
    return "flask" in command and "amp_host" in command


def _pid_listens_on_port(pid: int, port: int) -> bool:
    completed = subprocess.run(
        ["lsof", "-nP", "-a", "-p", str(pid), f"-iTCP:{port}", "-sTCP:LISTEN"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0 and str(port) in completed.stdout


def _terminate_pid(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if _process_command(pid) is None:
            return True
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if _process_command(pid) is None:
            return True
        time.sleep(0.1)
    return _process_command(pid) is None


def _terminate_child(child: subprocess.Popen[bytes]) -> None:
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=1)


def _stale_message(reason: str, server: dict[str, Any]) -> str:
    return _manual_recovery_message(
        f"Refusing to stop dev server because {REGISTRY_PATH.name} is stale or unsafe.\n"
        f"Reason: {reason}\n"
        f"Recorded pid: {server.get('pid')}\n"
        f"Recorded port: {server.get('port')}"
    )


def _manual_recovery_message(message: str) -> str:
    return (
        f"{message}\n\n"
        "No process was killed and dev-ports.json was left in place.\n"
        "Next steps:\n"
        f"  1. Inspect {REGISTRY_PATH}\n"
        "  2. Check the recorded process, for example: ps -p <pid> -o command=\n"
        "  3. Check the recorded port, for example: lsof -nP -iTCP:<port> -sTCP:LISTEN\n"
        f"  4. If you confirm the file is stale, delete {REGISTRY_PATH.name} and rerun the command."
    )


if __name__ == "__main__":
    raise SystemExit(main())
