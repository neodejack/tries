# Persistent Amp Agent Design

## Problem

The current launcher uses `amp -x "<prompt>"`, which is execute mode. Amp's help text says execute mode runs the provided prompt, prints the last assistant message, and exits. That is not the desired behavior if the goal is to keep a local Amp agent process alive after the initial prompt.

The desired behavior is closer to:

```bash
echo "<prompt>" | amp
```

or, preferably from the server, spawning `amp` directly and writing the prompt to its stdin without a shell.

## Goals

- Start an Amp agent process in a selected allowlisted directory.
- Send the initial prompt to that process.
- Keep the local Amp process alive until it exits or the user kills it.
- Show active local Amp agents in the UI.
- Let the user stop an active agent from the UI.
- Keep the directory allowlist and same-origin protections from the current app.

## Non-Goals

- Build a full Amp chat client.
- Persist sessions across Flask server restarts.
- Discover or control Amp threads after their local process exits.
- Parse or display the full assistant transcript in v1.

## Experiment Results

Tested against Amp CLI `0.0.1783228622-g9b591b` on July 5, 2026.

Plain pipes:

```python
Popen(["amp"], stdin=PIPE, stdout=PIPE, stderr=PIPE)
```

This did not produce a persistent interactive agent. Amp exited with a network timeout during the test. This shape also risks triggering execute-like behavior because Amp's help says redirecting stdout is equivalent to execute mode.

Echo-like hybrid:

```python
Popen(["amp"], stdin=PIPE, stdout=pty_slave, stderr=pty_slave)
```

The server wrote the prompt to stdin and closed stdin to mirror `echo "prompt" | amp`. From Python this failed with `Unexpected error inside Amp CLI`.

Full PTY:

```python
Popen(["amp"], stdin=pty_slave, stdout=pty_slave, stderr=pty_slave)
```

This worked after letting Amp finish initial terminal setup before typing the prompt. The test set a normal terminal size, wrote a first prompt through the PTY master, observed the assistant reply, wrote a second prompt through the same PTY, observed the second reply, and confirmed the process stayed alive after both replies.

Conclusion: the Python implementation should spawn Amp attached to a pseudoterminal for stdin, stdout, and stderr. Do not rely on `stdin=PIPE` for the persistent-agent path.

## Command Model

Do not use shell string construction.

Preferred v1 launch shape:

```python
import fcntl
import os
import pty
import struct
import termios
from subprocess import Popen

master_fd, slave_fd = pty.openpty()
fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 120, 0, 0))

process = Popen(
    ["amp"],
    cwd=directory.path,
    stdin=slave_fd,
    stdout=slave_fd,
    stderr=slave_fd,
    start_new_session=True,
    close_fds=True,
)
os.close(slave_fd)

# After Amp's terminal UI initializes:
os.write(master_fd, (prompt + "\r").encode("utf-8"))
```

Keep the PTY master open for the lifetime of the agent. Use nonblocking reads from the master fd to maintain a bounded diagnostic buffer and use writes to the master fd for the initial prompt. The experiment needed a short startup delay before writing; production code should either wait for initial terminal output or use a conservative startup delay before sending the prompt.

Avoid literal `echo "<prompt>" | amp` in the server implementation because it requires a shell and creates quoting/injection edge cases. It is useful as a behavioral reference, not as the production command.

## Backend Model

Replace `LaunchManager` with an `AgentManager`.

Tracked fields:

- `id`
- `directory_id`
- `directory_label`
- `prompt_preview`
- `started_at`
- `pid`
- `state`: `starting`, `running`, `exited`, `stopping`
- `exit_code`
- `last_error`

Internally each agent owns:

- process handle
- process group id
- PTY master fd
- PTY reader thread
- bounded output buffer for diagnostics

The output buffer can stay server-only in v1. It should be used to detect startup failures and return useful errors when Amp exits immediately.

## Startup Detection

The current bug class happened because `Popen` success was treated as launch success. Persistent mode should use a small startup window.

After spawning:

1. Attach Amp to a PTY and start a reader thread.
2. Wait for initial terminal output, or use a conservative startup delay.
3. Write the prompt plus carriage return to the PTY master fd.
4. Wait 1-2 seconds.
5. If the process exits, return an API error with the output tail.
6. If the process is still alive, report success and add it to the active agent list.

This does not prove Amp completed initialization, but it catches CLI usage errors and missing-auth failures that exit immediately.

## API Shape

`GET /api/config`

Returns directory choices and prompt limits.

`GET /api/agents`

Returns active local Amp agents:

```json
{
  "agents": [
    {
      "id": "abc",
      "directoryLabel": "Dotfiles",
      "promptPreview": "Update my zsh config...",
      "startedAt": 1783240000,
      "pid": 12345,
      "state": "running"
    }
  ]
}
```

`POST /api/agents`

Body:

```json
{
  "directoryId": "dotfiles",
  "prompt": "Update my zsh config"
}
```

Starts `amp`, writes the prompt to stdin, keeps the process alive, and returns the agent record.

`POST /api/agents/<id>/kill`

Marks the agent as stopping and sends `SIGINT`, then `SIGTERM`, then `SIGKILL` to the process group if needed.

## UI Changes

Keep the same mobile-first launcher layout, but rename concepts:

- "Launch" becomes "Start Agent".
- "Active launches" becomes "Active agents".
- Active rows show directory, elapsed time, prompt preview, and stop button.

Do not add transcript rendering in v1. If startup fails, show the backend error toast.

## Verification Plan

Use fake `amp` binaries in tests:

- Long-running fake Amp records stdin and stays alive.
- Immediate-exit fake Amp returns stderr and exits non-zero.
- Fake Amp that ignores `SIGINT` verifies `SIGTERM` fallback.
- Prompt with quotes/newlines verifies no shell parsing is involved.
- PTY integration test verifies the initial prompt is delivered through the PTY master.

Manual checks:

- `just run`
- Start an agent from the browser.
- Confirm it remains in Active agents after the initial response window.
- Stop it from the UI.
- Confirm no local test process remains.

## Open Questions

- Does Amp need a real TTY to behave correctly in persistent interactive mode?
- Should the server close stdin after the initial prompt, or keep it open?
- Does Amp expose a thread id or URL in output that should be captured later?
- Should v2 support sending follow-up prompts to the same local process?
