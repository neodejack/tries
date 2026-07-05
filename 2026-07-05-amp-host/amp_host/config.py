from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_ENV_VAR = "AMP_HOST_CONFIG"


@dataclass(frozen=True)
class Directory:
    id: str
    label: str
    path: Path

    def as_json(self) -> dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
            "path": str(self.path),
        }


@dataclass(frozen=True)
class Settings:
    config_path: Path
    directories: list[Directory]
    allowed_origins: set[str]


def load_settings() -> Settings:
    config_path = _config_path()
    raw_config = _load_config(config_path)
    return Settings(
        config_path=config_path,
        directories=_load_directories(raw_config),
        allowed_origins=_load_allowed_origins(raw_config),
    )


def _config_path() -> Path:
    configured_path = os.environ.get(CONFIG_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return Path.cwd() / "amp-host.config.json"


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(
            f"Missing config file: {path}. Copy amp-host.config.example.json "
            "to amp-host.config.json and edit the directory list."
        )
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RuntimeError("Config root must be a JSON object.")
    return data


def _load_directories(config: dict[str, Any]) -> list[Directory]:
    raw_directories = config.get("allowedDirectories")
    if not isinstance(raw_directories, list) or not raw_directories:
        raise RuntimeError("Config must include a non-empty allowedDirectories list.")

    directories: list[Directory] = []
    seen_ids: set[str] = set()
    for index, raw_directory in enumerate(raw_directories):
        if not isinstance(raw_directory, dict):
            raise RuntimeError("Each allowed directory must be an object.")

        label = raw_directory.get("label")
        raw_path = raw_directory.get("path")
        if not isinstance(label, str) or not label.strip():
            raise RuntimeError("Each allowed directory needs a label.")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise RuntimeError(f"Directory {label!r} needs a path.")

        directory_id = raw_directory.get("id")
        if not isinstance(directory_id, str) or not directory_id.strip():
            directory_id = f"dir-{index + 1}"
        if directory_id in seen_ids:
            raise RuntimeError(f"Duplicate directory id in config: {directory_id}")
        seen_ids.add(directory_id)

        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise RuntimeError(f"Allowed directory does not exist: {path}")

        directories.append(Directory(id=directory_id, label=label.strip(), path=path))

    return directories


def _load_allowed_origins(config: dict[str, Any]) -> set[str]:
    raw_allowed_origins = config.get("allowedOrigins", [])
    if not isinstance(raw_allowed_origins, list):
        raise RuntimeError("allowedOrigins must be a list when provided.")

    allowed_origins: set[str] = set()
    for origin in raw_allowed_origins:
        if not isinstance(origin, str) or not origin.strip():
            raise RuntimeError("Every allowed origin must be a non-empty string.")
        allowed_origins.add(origin.strip())
    return allowed_origins
