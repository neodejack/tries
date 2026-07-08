# Amp Host

A tiny Flask web app for starting long-lived local Amp agents from a phone or laptop.

The app accepts a prompt, resolves a selected allowlisted directory from config, and asks Herdr to start Amp in a long-lived terminal pane:

```bash
herdr agent start <name> --cwd "<directory>" --workspace <remote-workspace-id> --no-focus -- amp --mode deep
herdr pane run <pane-id> "<prompt>"
herdr pane send-keys <pane-id> enter
```

It does not show command output or store history. It lists Herdr-managed Amp agents created by this app so they can be stopped from the UI. Herdr's reported Amp `agent_status` is not treated as authoritative because Amp currently uses screen-manifest detection without a lifecycle integration.

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
# or choose a port
just run 9000
```

Open <http://127.0.0.1:8765>.

`just run` first stops any server registered in `dev-ports.json`, then starts
the Flask dev server on the requested port. After `/api/config` is healthy it
writes local runtime state like:

```json
{
  "dev-server": {
    "host": "localhost",
    "port": 8765,
    "url": "http://localhost:8765",
    "pid": 12345
  }
}
```

Use `just down` to stop the registered dev server. Pressing Control-C in
`just run` also removes `dev-ports.json` when it still points to the server that
command started. If `dev-ports.json` is stale or unsafe, the command leaves it
in place and prints manual recovery steps; inspect it and delete it only after
confirming it no longer points to a live Amp Host dev server.

## Run For Tailscale Access

Use Tailscale Serve when you want to reach the app from your phone over Tailscale:

```bash
just tailscale
```

Then open the Tailscale Serve URL printed by the command from your phone.
By default this uses the Tailscale service name `svc:amp-host`, which serves Amp Host at `https://amp-host.<your-tailnet>.ts.net/`.
The Tailscale Serve mapping is installed in the background; `just tailscale` stays running because the local Flask server runs in the foreground.

## Config Path

By default, the app reads `amp-host.config.json` from the current working directory.
To use another file:

```bash
AMP_HOST_CONFIG=/path/to/config.json just run
```

## Safety Notes

- Only configured directories can be selected.
- Prompts are passed to `herdr pane run` without shell string construction, then submitted with `herdr pane send-keys enter`.
- POST requests with a cross-origin `Origin` header are rejected unless explicitly listed in `allowedOrigins`.
- Stopping an agent closes the Herdr pane for agents created by this app.
