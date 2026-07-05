from __future__ import annotations

import os
import signal
import threading
import time
import uuid
from dataclasses import dataclass
from subprocess import DEVNULL, Popen
from typing import Any

from amp_host.config import Directory


@dataclass
class Launch:
    id: str
    directory_id: str
    directory_label: str
    prompt: str
    started_at: float
    process: Popen[bytes]
    stopping: bool = False

    def as_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "directoryId": self.directory_id,
            "directoryLabel": self.directory_label,
            "prompt": self.prompt,
            "startedAt": self.started_at,
            "pid": self.process.pid,
            "stopping": self.stopping,
        }


@dataclass(frozen=True)
class LaunchStartError(Exception):
    message: str
    status_code: int


class LaunchManager:
    def __init__(self) -> None:
        self._launches: dict[str, Launch] = {}
        self._lock = threading.Lock()

    def active_launches_json(self) -> list[dict[str, Any]]:
        self._prune_finished()
        with self._lock:
            launches = sorted(
                self._launches.values(),
                key=lambda item: item.started_at,
                reverse=True,
            )
            return [launch.as_json() for launch in launches]

    def start(self, directory: Directory, prompt: str) -> Launch:
        launch_id = uuid.uuid4().hex
        try:
            process = Popen(
                ["amp", "-x", prompt],
                cwd=directory.path,
                stdin=DEVNULL,
                stdout=DEVNULL,
                stderr=DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise LaunchStartError(
                message="Could not find `amp` on the server PATH.",
                status_code=503,
            ) from exc
        except OSError as exc:
            raise LaunchStartError(
                message=f"Could not start amp: {exc}",
                status_code=500,
            ) from exc

        launch = Launch(
            id=launch_id,
            directory_id=directory.id,
            directory_label=directory.label,
            prompt=prompt,
            started_at=time.time(),
            process=process,
        )
        with self._lock:
            self._launches[launch_id] = launch

        monitor = threading.Thread(
            target=self._monitor_launch,
            args=(launch_id, process),
            daemon=True,
        )
        monitor.start()
        return launch

    def stop(self, launch_id: str) -> Launch | None:
        with self._lock:
            launch = self._launches.get(launch_id)
            if launch is not None:
                launch.stopping = True

        if launch is None:
            return None

        killer = threading.Thread(
            target=_stop_process_group,
            args=(launch.process,),
            daemon=True,
        )
        killer.start()
        return launch

    def _monitor_launch(self, launch_id: str, process: Popen[bytes]) -> None:
        process.wait()
        with self._lock:
            self._launches.pop(launch_id, None)

    def _prune_finished(self) -> None:
        with self._lock:
            finished_ids = [
                launch_id
                for launch_id, launch in self._launches.items()
                if launch.process.poll() is not None
            ]
            for launch_id in finished_ids:
                self._launches.pop(launch_id, None)


def _stop_process_group(process: Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    _send_signal(process, signal.SIGINT)
    if _wait_until_exit(process, 3):
        return

    _send_signal(process, signal.SIGTERM)
    if _wait_until_exit(process, 3):
        return

    _send_signal(process, signal.SIGKILL)


def _send_signal(process: Popen[bytes], sig: signal.Signals) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        return


def _wait_until_exit(process: Popen[bytes], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return True
        time.sleep(0.1)
    return process.poll() is not None
