# Amp Host

A tiny Flask web app for starting long-lived local Amp agents from a phone or laptop.

The app accepts a prompt, resolves a selected allowlisted directory from config, and asks Herdr to start Amp in a long-lived terminal pane:

```bash
herdr agent start <name> --cwd "<directory>" --no-focus -- amp
herdr pane run <pane-id> "<prompt>"
```

It does not show command output or store history. It lists Herdr-managed Amp agents created by this app so they can be stopped from the UI.

## Setup

```bash
mise install
uv sync
command -v herdr
```

Herdr must be installed and available on `PATH`. On this machine it is installed at `/Users/zili/.local/bin/herdr`.

Edit `amp-host.config.json` to add the directories you want to launch from:

```json
{
  "allowedDirectories": [
    {
      "id": "dotfiles",
      "label": "Dotfiles",
      "path": "/Users/zili/code/personal/.dotfiles"
    }
  ],
  "allowedOrigins": []
}
```

The browser sends only the directory `id`; the server resolves the path from this file.

## Run Locally

```bash
just run
```

Open <http://127.0.0.1:8765>.

## Run For Tailscale Access

Bind to all interfaces when you want to reach the app from your phone over Tailscale:

```bash
just tailscale
```

Then open `http://<your-mac-tailscale-name-or-ip>:8765` from your phone.

## Config Path

By default, the app reads `amp-host.config.json` from the current working directory.
To use another file:

```bash
AMP_HOST_CONFIG=/path/to/config.json just run
```

## Safety Notes

- Only configured directories can be selected.
- Prompts are passed to `herdr pane run` without shell string construction.
- POST requests with a cross-origin `Origin` header are rejected unless explicitly listed in `allowedOrigins`.
- Stopping an agent closes the Herdr pane for agents created by this app.
