# Amp Host

A tiny Flask web app for launching local Amp one-shot runs from a phone or laptop.

The app accepts a prompt, resolves a selected allowlisted directory from config, and starts:

```bash
amp -x "<prompt>"
```

It does not show command output or store history. It only tracks currently running local `amp` processes in memory so they can be stopped from the UI.

## Setup

```bash
mise install
uv sync
```

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
- Prompts are passed as a direct process argument, not through a shell.
- POST requests with a cross-origin `Origin` header are rejected unless explicitly listed in `allowedOrigins`.
- Stopping a launch sends `SIGINT`, then `SIGTERM`, then `SIGKILL` to the process group if needed.
