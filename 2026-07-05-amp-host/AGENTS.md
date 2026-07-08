# Agent instructions

## Project overview

Amp Host is a small Flask web app that launches long-lived local Amp agents through Herdr. The UI is a mobile-friendly prompt box plus an allowlisted directory selector. The server starts Amp in Herdr's `remote` workspace with deep mode, sends the initial prompt, lists active Herdr-managed agents, and can stop them by closing their Herdr pane.

## Important directories

- `amp_host/` - Flask app, config loading, Herdr adapter, templates, and static frontend assets.
- `docs/` - design notes and implementation plans for the Amp/Herdr launcher architecture.
- `amp-host.config.example.json` - example allowlist config. The real `amp-host.config.json` is local-only and ignored.
- `justfile` - canonical setup and run commands.
- `mise.toml` - tool versions for Python, uv, and just.

## Setup

Install the pinned tools and Python dependencies with:

```bash
mise install
uv sync
```

Herdr and Amp must be available on `PATH` for launch behavior:

```bash
command -v herdr
command -v amp
herdr status server
```

Create a local config by copying `amp-host.config.example.json` to `amp-host.config.json` and editing the allowlisted directories. Do not commit `amp-host.config.json`.

## Development

Start the local Flask server with:

```bash
just run
```

Open `http://127.0.0.1:8765`.

For phone access over Tailscale, use:

```bash
just tailscale
```

This installs a Tailscale Serve mapping in the background and runs Flask on `127.0.0.1`.

## Verification

Use the narrowest relevant check:

```bash
uv run python -m compileall amp_host
curl http://127.0.0.1:8765/api/config
curl http://127.0.0.1:8765/api/launches
herdr agent list
```

Run an Amp review before committing non-trivial behavior changes:

```bash
amp review
```

There is no dedicated test suite yet. For launch lifecycle changes, perform a Herdr smoke test and confirm any temporary pane is closed afterward.

## Code conventions

- Keep the app plain Flask and vanilla frontend JavaScript unless the user explicitly asks for a larger framework.
- Preserve the existing API route names under `/api/launches`; the frontend still uses those route names even though the UI says "agents".
- Keep launch behavior shell-safe. Pass prompts and command arguments through structured subprocess argument lists, not shell strings.
- Keep changes scoped. Do not add persistence, authentication, or launch history unless requested.
- Update `README.md` and relevant `docs/` files when changing the Herdr command shape or lifecycle behavior.

## Safety rules

- Do not commit `amp-host.config.json`; it contains local allowlisted paths.
- Do not commit generated E2E screenshot artifacts such as `e2e-*.png`.
- Do not kill unrelated Herdr panes or agents. The app should manage only agents with the `amp-host-` prefix and allowlisted cwd values.
- Do not run destructive git commands or reset Herdr workspaces without explicit user confirmation.
- Do not print, store, or commit tokens, Tailscale secrets, Amp credentials, or private config.

## Known gotchas

- The git root is the parent `tries/` directory, but this app lives in the `2026-07-05-amp-host/` subtree. Keep project guidance and app changes scoped here.
- Herdr workspace labels are user-facing; the app resolves the workspace labeled `remote` to a workspace id before launching Amp.
- The selected project directory is still passed per launch with `--cwd`, even though all launches target the `remote` Herdr workspace.
- Amp launches must include `--mode deep`.
