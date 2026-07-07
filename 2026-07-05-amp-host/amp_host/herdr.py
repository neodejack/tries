from __future__ import annotations

import json
import random
import shutil
import string
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amp_host.config import Directory


AGENT_NAME_PREFIX = "amp-host-"
HERDR_COMMAND = "herdr"
HERDR_WORKSPACE_LABEL = "remote"


@dataclass(frozen=True)
class HerdrError(Exception):
    message: str
    status_code: int = 502


@dataclass(frozen=True)
class HerdrAgent:
    id: str
    directory_id: str
    directory_label: str
    prompt: str
    started_at: float
    pane_id: str
    workspace_id: str
    status: str
    stopping: bool = False

    def as_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "directoryId": self.directory_id,
            "directoryLabel": self.directory_label,
            "prompt": self.prompt,
            "startedAt": self.started_at,
            "paneId": self.pane_id,
            "workspaceId": self.workspace_id,
            "status": self.status,
            "stopping": self.stopping,
        }


class HerdrAgentManager:
    def __init__(self, directories: list[Directory]) -> None:
        self._directories = directories
        self._prompt_cache: dict[str, str] = {}
        self._started_at_cache: dict[str, float] = {}

    def active_launches_json(self) -> list[dict[str, Any]]:
        agents = [
            agent.as_json()
            for agent in self._managed_agents()
        ]
        return sorted(agents, key=lambda item: item["startedAt"], reverse=True)

    def start(self, directory: Directory, prompt: str) -> HerdrAgent:
        _ensure_herdr_available()
        _run(["status", "server"])

        name = _agent_name()
        started_at = time.time()
        workspace_id = _ensure_workspace(HERDR_WORKSPACE_LABEL)
        started = _run_json(
            [
                "agent",
                "start",
                name,
                "--cwd",
                str(directory.path),
                "--workspace",
                workspace_id,
                "--no-focus",
                "--",
                "amp",
                "--mode",
                "deep",
            ]
        )
        raw_agent = _result(started).get("agent")
        if not isinstance(raw_agent, dict):
            raise HerdrError("Herdr did not return an agent record.")

        pane_id = _required_str(raw_agent, "pane_id")
        workspace_id = _required_str(raw_agent, "workspace_id")

        try:
            raw_agent = self._wait_for_amp_agent(name)
            _run_json(["pane", "run", pane_id, prompt])
        except HerdrError:
            _close_pane_best_effort(pane_id)
            raise

        self._prompt_cache[name] = prompt
        self._started_at_cache[name] = started_at
        return self._agent_from_raw(
            raw_agent,
            fallback_directory=directory,
            fallback_prompt=prompt,
            fallback_started_at=started_at,
            fallback_pane_id=pane_id,
            fallback_workspace_id=workspace_id,
        )

    def stop(self, launch_id: str) -> HerdrAgent | None:
        agent = self._managed_agent_by_name(launch_id)
        if agent is None:
            return None

        _run_json(["pane", "close", agent.pane_id])
        self._prompt_cache.pop(launch_id, None)
        self._started_at_cache.pop(launch_id, None)
        return HerdrAgent(
            id=agent.id,
            directory_id=agent.directory_id,
            directory_label=agent.directory_label,
            prompt=agent.prompt,
            started_at=agent.started_at,
            pane_id=agent.pane_id,
            workspace_id=agent.workspace_id,
            status=agent.status,
            stopping=True,
        )

    def _managed_agents(self) -> list[HerdrAgent]:
        _ensure_herdr_available()
        listed = _run_json(["agent", "list"])
        raw_agents = _result(listed).get("agents", [])
        if not isinstance(raw_agents, list):
            raise HerdrError("Herdr returned an invalid agent list.")

        agents: list[HerdrAgent] = []
        for raw_agent in raw_agents:
            if not isinstance(raw_agent, dict):
                continue
            agent = self._agent_from_raw(raw_agent)
            if agent is not None:
                agents.append(agent)
        return agents

    def _managed_agent_by_name(self, name: str) -> HerdrAgent | None:
        if not name.startswith(AGENT_NAME_PREFIX):
            return None
        try:
            raw = _run_json(["agent", "get", name])
        except HerdrError as exc:
            if "not found" in exc.message:
                return None
            raise
        raw_agent = _result(raw).get("agent")
        if not isinstance(raw_agent, dict):
            return None
        return self._agent_from_raw(raw_agent)

    def _wait_for_amp_agent(self, name: str) -> dict[str, Any]:
        deadline = time.monotonic() + 15
        last_agent: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            raw = _run_json(["agent", "get", name])
            raw_agent = _result(raw).get("agent")
            if isinstance(raw_agent, dict):
                last_agent = raw_agent
                if raw_agent.get("agent") == "amp":
                    return raw_agent
            time.sleep(0.5)

        if last_agent is not None:
            status = _optional_str(last_agent, "agent_status") or "unknown"
            raise HerdrError(
                f"Herdr started the pane, but Amp was not detected. Last status: {status}."
            )
        raise HerdrError("Herdr started the pane, but the Amp agent was not detected.")

    def _agent_from_raw(
        self,
        raw_agent: dict[str, Any],
        *,
        fallback_directory: Directory | None = None,
        fallback_prompt: str | None = None,
        fallback_started_at: float | None = None,
        fallback_pane_id: str | None = None,
        fallback_workspace_id: str | None = None,
    ) -> HerdrAgent | None:
        name = raw_agent.get("name")
        if not isinstance(name, str) or not name.startswith(AGENT_NAME_PREFIX):
            return None

        directory = fallback_directory or self._directory_for_raw_agent(raw_agent)
        if directory is None:
            return None

        pane_id = _optional_str(raw_agent, "pane_id") or fallback_pane_id
        workspace_id = _optional_str(raw_agent, "workspace_id") or fallback_workspace_id
        if pane_id is None or workspace_id is None:
            return None

        status = _optional_str(raw_agent, "agent_status") or "unknown"
        started_at = (
            fallback_started_at
            if fallback_started_at is not None
            else self._started_at_cache.get(name) or _started_at_from_name(name)
        )
        return HerdrAgent(
            id=name,
            directory_id=directory.id,
            directory_label=directory.label,
            prompt=fallback_prompt or self._prompt_cache.get(name, "Herdr-managed Amp agent"),
            started_at=started_at,
            pane_id=pane_id,
            workspace_id=workspace_id,
            status=status,
        )

    def _directory_for_raw_agent(self, raw_agent: dict[str, Any]) -> Directory | None:
        raw_cwd = raw_agent.get("cwd")
        raw_foreground_cwd = raw_agent.get("foreground_cwd")
        candidate_paths = [
            Path(path).expanduser().resolve()
            for path in (raw_foreground_cwd, raw_cwd)
            if isinstance(path, str) and path.strip()
        ]

        for directory in self._directories:
            directory_path = directory.path.resolve()
            if any(path == directory_path for path in candidate_paths):
                return directory
        return None


def _agent_name() -> str:
    timestamp = time.strftime("%Y%m%d%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{AGENT_NAME_PREFIX}{timestamp}-{suffix}"


def _ensure_workspace(label: str) -> str:
    existing_workspace_id = _workspace_id_by_label(label)
    if existing_workspace_id is not None:
        return existing_workspace_id

    created = _run_json(
        [
            "workspace",
            "create",
            "--label",
            label,
            "--no-focus",
        ]
    )
    raw_workspace = _result(created).get("workspace")
    if not isinstance(raw_workspace, dict):
        raise HerdrError("Herdr did not return a workspace record.")
    return _required_str(raw_workspace, "workspace_id")


def _workspace_id_by_label(label: str) -> str | None:
    listed = _run_json(["workspace", "list"])
    raw_workspaces = _result(listed).get("workspaces", [])
    if not isinstance(raw_workspaces, list):
        raise HerdrError("Herdr returned an invalid workspace list.")

    for raw_workspace in raw_workspaces:
        if not isinstance(raw_workspace, dict):
            continue
        if raw_workspace.get("label") == label:
            return _optional_str(raw_workspace, "workspace_id")
    return None


def _started_at_from_name(name: str) -> float:
    raw_timestamp = name.removeprefix(AGENT_NAME_PREFIX).split("-", 1)[0]
    try:
        return time.mktime(time.strptime(raw_timestamp, "%Y%m%d%H%M%S"))
    except ValueError:
        return 0


def _close_pane_best_effort(pane_id: str) -> None:
    try:
        _run_json(["pane", "close", pane_id])
    except HerdrError:
        pass


def _ensure_herdr_available() -> None:
    if shutil.which(HERDR_COMMAND) is None:
        raise HerdrError("Could not find `herdr` on the server PATH.", status_code=503)


def _run_json(args: list[str]) -> dict[str, Any]:
    completed = _run(args)
    if not completed.stdout.strip():
        return {"result": {"type": "ok"}}
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HerdrError(
            f"Herdr returned non-JSON output: {completed.stdout.strip()}"
        ) from exc
    if isinstance(data, dict) and "error" in data:
        error = data["error"]
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                raise HerdrError(message)
        raise HerdrError("Herdr returned an error.")
    if not isinstance(data, dict):
        raise HerdrError("Herdr returned an invalid JSON response.")
    return data


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            [HERDR_COMMAND, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise HerdrError("Could not find `herdr` on the server PATH.", 503) from exc
    except subprocess.TimeoutExpired as exc:
        raise HerdrError("Timed out waiting for Herdr.") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        if not message:
            message = f"Herdr exited with status {completed.returncode}."
        raise HerdrError(message)
    return completed


def _result(data: dict[str, Any]) -> dict[str, Any]:
    result = data.get("result")
    if not isinstance(result, dict):
        raise HerdrError("Herdr response did not include a result object.")
    return result


def _required_str(data: dict[str, Any], key: str) -> str:
    value = _optional_str(data, key)
    if value is None:
        raise HerdrError(f"Herdr response did not include {key}.")
    return value


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if isinstance(value, str) and value:
        return value
    return None
