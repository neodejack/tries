# Amp Host package instructions

## Scope

This directory contains the Flask backend, Herdr integration, templates, and static frontend files for Amp Host.

## Commands

Compile-check Python changes with:

```bash
uv run python -m compileall amp_host
```

Run the app from the project root with:

```bash
just run
```

## Module map

- `app.py` - Flask app factory and HTTP routes.
- `config.py` - `amp-host.config.json` loading and validation.
- `herdr.py` - Herdr CLI adapter, Amp agent lifecycle, workspace resolution, and active-agent filtering.
- `templates/index.html` - single-page launcher markup.
- `static/app.js` - frontend state, API calls, polling, and stop action.
- `static/styles.css` - responsive mobile-first styling.

## Backend conventions

- Keep route handlers thin. Put Herdr process behavior in `herdr.py`, not directly in `app.py`.
- Convert `HerdrError` into HTTP errors at route boundaries so users see useful setup/status messages.
- Keep `MAX_PROMPT_CHARS` in `app.py` and the frontend character limit in sync through `/api/config`.
- Keep same-origin write protection for POST, PUT, PATCH, and DELETE routes.
- When adding config fields, validate them in `config.py` and update `amp-host.config.example.json`.

## Herdr conventions

- Start agents with Herdr in the `remote` workspace and Amp deep mode:

```bash
herdr agent start <name> --cwd <allowed-dir> --workspace <remote-workspace-id> --no-focus -- amp --mode deep
```

- Submit the initial prompt with `herdr pane run <pane_id> <prompt>`.
- Close panes with `herdr pane close <pane_id>` for the stop action.
- Clean up a newly created pane if Amp detection or prompt submission fails.
- Filter active agents by both the `amp-host-` name prefix and allowlisted cwd values.
- Do not manage Herdr panes created outside this app.

## Frontend conventions

- Keep the frontend dependency-free: plain HTML, CSS, and JavaScript.
- Preserve mobile-first layout and responsive controls because the primary use case is phone access over Tailscale.
- Keep visible labels focused on the launcher workflow. Avoid adding explanatory product copy inside the app UI.
- Use the existing polling model unless replacing it with a complete, tested status mechanism.

## Launch lifecycle smoke test

For Herdr launch changes, verify the actual command shape and clean up the smoke pane:

```bash
workspace_id=$(herdr workspace list | jq -r '.result.workspaces[] | select(.label == "remote") | .workspace_id' | head -1)
name="amp-host-smoke-$(date +%s)"
started=$(herdr agent start "$name" --cwd "$PWD" --workspace "$workspace_id" --no-focus -- amp --mode deep)
pane_id=$(echo "$started" | jq -r '.result.agent.pane_id')
herdr agent get "$name"
herdr pane close "$pane_id"
herdr agent list
```

Confirm `herdr agent list` does not contain the smoke agent afterward.
