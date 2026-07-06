# Herdr Integration Design

## Summary

Herdr looks like a strong fit for Amp Host's revised goal: the web app should launch long-lived Amp agents without owning PTYs itself.

Instead of spawning `amp` directly, Amp Host can ask Herdr to start an Amp agent in a Herdr-managed terminal pane. Herdr owns the PTY, process lifetime, agent detection, attach/read/send controls, and session persistence. Amp Host remains a small mobile launcher and process list.

## Evidence From Herdr Docs

- Herdr agents stay in real terminal panes with shell, logs, prompts, and running processes intact.
  Source: https://herdr.dev/docs/agents/
- Herdr supports Amp via screen-manifest detection.
  Source: https://herdr.dev/docs/agents/
- `herdr agent start <name> --cwd PATH -- <argv...>` starts an agent from scripts.
  Source: https://herdr.dev/docs/agents/
- The CLI talks to the same local socket API used by integrations and agents.
  Source: https://herdr.dev/docs/cli-reference/
- Herdr exposes commands to list/get/read/send/focus/wait/attach/start agents.
  Source: https://herdr.dev/docs/cli-reference/
- Herdr's local socket API can create/list/control panes and agents, read output, send input, and subscribe to pane/agent events.
  Source: https://herdr.dev/docs/socket-api/
- Detaching keeps the Herdr server and every agent running.
  Source: https://herdr.dev/docs/quick-start/
- Herdr's own architecture is explicitly about server-owned PTYs and preserving pane processes.
  Source: https://herdr.dev/blog/live-updates-without-killing-your-terminal-processes/

## Proposed Architecture

```mermaid
flowchart LR
    Phone["Phone browser"] --> Flask["Amp Host Flask app"]
    Flask --> HerdrCLI["herdr CLI wrappers"]
    HerdrCLI --> HerdrServer["Herdr server"]
    HerdrServer --> AmpPane["Herdr pane: amp"]
    AmpPane --> Amp["Amp agent process"]
```

Amp Host no longer tracks `Popen` handles. It tracks Herdr agent targets.

## Validation Results

Validated locally with Herdr `0.7.1`. The active binary after cleanup is:

```bash
/Users/zili/.local/bin/herdr
```

The temporary Homebrew install used during validation has been removed.

Results:

- `herdr status server` showed a running compatible server.
- `herdr agent start <name> --cwd <dir> --no-focus -- amp` successfully created a Herdr pane running Amp.
- After a short startup delay, Herdr detected the pane as `agent: "amp"` and `agent_status: "idle"`.
- `herdr agent list` and `herdr agent get <name>` returned enough metadata for Amp Host: agent name, status, cwd, foreground cwd, pane id, tab id, terminal id, and workspace id.
- `herdr agent send <name> <prompt>` typed literal text into Amp but did not submit it.
- `herdr pane send-keys <pane_id> enter` submitted text previously typed by `agent send`.
- `herdr pane run <pane_id> <prompt>` was the best prompt-submission primitive. It submits text plus Enter atomically.
- `herdr pane run` successfully submitted a multiline prompt to Amp.
- `herdr pane close <pane_id>` removed the validation agent and pane from Herdr's list.

Conclusion: use `agent start` to create the Amp process and `pane run` to send the initial prompt.

## Launch Flow

1. User selects an allowlisted directory and submits a prompt.
2. Flask validates the directory id and prompt size.
3. Flask creates a unique Herdr agent name, for example:

   ```text
   amp-host-20260705-abc123
   ```

4. Flask starts Amp inside Herdr:

   ```bash
   herdr agent start amp-host-20260705-abc123 \
     --cwd /absolute/allowed/dir \
     --no-focus \
     -- amp
   ```

5. Flask sends the prompt to the Herdr terminal.

   Use `pane run`, not `agent send`, because `pane run` submits text plus Enter atomically and validated successfully with multiline prompts:

   ```bash
   herdr pane run <pane_id> "$PROMPT"
   ```

   `agent send` is still useful for low-level literal input, but it only types text. To submit after `agent send`, the app would also need:

   ```bash
   herdr pane send-keys <pane_id> enter
   ```

6. Flask returns the Herdr agent record to the UI.

## Listing Active Agents

Amp Host can list active agents by querying Herdr:

```bash
herdr agent list --json
```

Filter to agent names with the `amp-host-` prefix and directories in the configured allowlist.

This means Amp Host can recover active launched agents after a Flask restart, as long as Herdr is still running.

## Stopping Agents

Preferred stop behavior:

1. Close the Herdr pane.
2. Refresh the Herdr agent list to confirm the agent disappeared.

CLI shape:

```bash
herdr pane close <pane_id>
```

This validated for the Herdr-owned test Amp panes. If we later want gentler shutdown, add `pane send-keys <pane_id> ctrl+c` before close.

## API Changes In Amp Host

Keep the current frontend mostly intact, but rename the backend concept:

- `LaunchManager` becomes `HerdrAgentManager`
- `GET /api/launches` becomes either:
  - keep `/api/launches` for minimal frontend churn, or
  - rename to `/api/agents`
- `POST /api/launches` starts a Herdr-managed Amp agent
- `POST /api/launches/<id>/kill` stops/closes the Herdr pane

Returned records should include:

```json
{
  "id": "amp-host-20260705-abc123",
  "directoryId": "dotfiles",
  "directoryLabel": "Dotfiles",
  "prompt": "Initial prompt preview",
  "startedAt": 1783240000,
  "herdrPaneId": "w1:p3",
  "herdrWorkspaceId": "w1",
  "status": "working"
}
```

## CLI Wrapper vs Raw Socket API

Use CLI wrappers first.

Reasons:

- Herdr docs recommend CLI wrappers for shell scripts, simple orchestration, and human debugging.
- CLI output is intended to be deterministic for scripts.
- This keeps Amp Host small and avoids implementing a JSON-over-Unix-socket client immediately.

Use raw socket API later if we need:

- long-lived event subscriptions for live status updates,
- lower latency,
- richer pane metadata without shelling out.

## Setup Requirements

Herdr is installed on this laptop via the official curl installer:

```bash
/Users/zili/.local/bin/herdr --version
```

Use `herdr` from `PATH` in application code, and fail with a clear setup error if it is missing. The current PATH resolves to `/Users/zili/.local/bin/herdr`.

The docs list other install options:

```bash
brew install herdr
```

The local mise registry did not expose Herdr during validation, so do not add it to `mise.toml` yet.

## Remaining Implementation Tasks

1. Replace `LaunchManager` with a `HerdrAgentManager`.
2. Start agents with:

   ```bash
   herdr agent start <name> --cwd <dir> --no-focus -- amp
   ```

3. Extract `pane_id` from the JSON result.
4. Wait briefly until `agent get <name>` reports `agent: "amp"` or return a startup error.
5. Submit prompts with:

   ```bash
   herdr pane run <pane_id> "$PROMPT"
   ```

6. List active agents with `agent list` filtered to the `amp-host-` prefix and allowlisted directories.
7. Stop agents with `pane close <pane_id>`.
8. Surface Herdr CLI errors in the UI toast.

## Recommendation

Adopt Herdr if the validation tasks pass.

This shifts the hardest part of the redesign, reliable PTY ownership and long-lived agent sessions, to a tool whose core purpose is exactly that. Amp Host stays small: config allowlist, mobile form, Herdr command adapter, and a filtered active-agent list.
