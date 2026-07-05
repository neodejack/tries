from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, render_template, request

from amp_host.config import Directory, load_settings
from amp_host.launches import LaunchManager, LaunchStartError


MAX_PROMPT_CHARS = 20_000
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app() -> Flask:
    app = Flask(__name__)
    settings = load_settings()
    launch_manager = LaunchManager()

    app.config["AMP_HOST_SETTINGS"] = settings
    app.config["AMP_HOST_LAUNCH_MANAGER"] = launch_manager

    @app.before_request
    def protect_write_routes() -> None:
        if request.method in WRITE_METHODS:
            _require_same_origin(app)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/config")
    def api_config() -> Any:
        return jsonify(
            {
                "directories": [
                    directory.as_json() for directory in settings.directories
                ],
                "maxPromptChars": MAX_PROMPT_CHARS,
                "ampUrl": "https://ampcode.com/",
            }
        )

    @app.get("/api/launches")
    def api_launches() -> Any:
        return jsonify({"launches": launch_manager.active_launches_json()})

    @app.post("/api/launches")
    def api_create_launch() -> Any:
        payload = request.get_json(silent=True) or {}
        directory_id = payload.get("directoryId")
        prompt = payload.get("prompt")

        if not isinstance(directory_id, str):
            abort(400, "Missing directory id.")
        if not isinstance(prompt, str) or not prompt.strip():
            abort(400, "Prompt cannot be empty.")
        if len(prompt) > MAX_PROMPT_CHARS:
            abort(400, f"Prompt must be {MAX_PROMPT_CHARS:,} characters or less.")

        directory = _directory_by_id(settings.directories, directory_id)
        if directory is None:
            abort(400, "Directory is not allowed.")

        try:
            launch = launch_manager.start(directory=directory, prompt=prompt)
        except LaunchStartError as exc:
            abort(exc.status_code, exc.message)

        return jsonify({"launch": launch.as_json()}), 201

    @app.post("/api/launches/<launch_id>/kill")
    def api_kill_launch(launch_id: str) -> Any:
        launch = launch_manager.stop(launch_id)
        if launch is None:
            abort(404, "Launch is not active.")

        return jsonify({"ok": True, "launch": launch.as_json()})

    return app


def _directory_by_id(
    directories: list[Directory], directory_id: str
) -> Directory | None:
    for directory in directories:
        if directory.id == directory_id:
            return directory
    return None


def _require_same_origin(app: Flask) -> None:
    origin = request.headers.get("Origin")
    if not origin:
        return

    settings = app.config["AMP_HOST_SETTINGS"]
    if origin in settings.allowed_origins:
        return

    parsed_origin = urlparse(origin)
    if parsed_origin.netloc == request.host:
        return

    abort(403, "Cross-origin write requests are not allowed.")
