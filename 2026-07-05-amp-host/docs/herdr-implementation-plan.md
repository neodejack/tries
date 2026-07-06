# Implementation Plan: Herdr-Backed Amp Host

## Overview

Replace Amp Host's local `amp -x` process launcher with a Herdr-backed long-lived agent launcher. The Flask app remains a mobile-friendly allowlisted launcher, but Herdr owns the terminal pane, PTY, Amp process lifetime, and restart-resilient agent listing.

## Architecture Decisions

- Use Herdr CLI wrappers first, not the raw socket API. The validated CLI is sufficient for start, prompt submission, list, read, and close.
- Use the `herdr` binary from `PATH`. The current laptop resolves this to `/Users/zili/.local/bin/herdr`, installed by the official curl installer.
- Keep the existing `/api/launches` route names for the first implementation to avoid unnecessary frontend churn. Internally, rename the backend manager from launches to Herdr agents.
- Use `herdr agent start <name> --cwd <dir> --no-focus -- amp` to create the long-lived Amp process.
- Use `herdr pane run <pane_id> <prompt>` to submit the initial prompt. This validated with both single-line and multiline prompts.
- Use `herdr pane close <pane_id>` for the v1 stop action.
- Filter Herdr agents by a generated `amp-host-` name prefix and by allowlisted cwd so the app does not manage unrelated Herdr panes.

## Task List

### Phase 1: Herdr Adapter Foundation

## Task 1: Add Herdr Command Adapter

**Description:** Create a small Python adapter that runs `herdr` commands, parses JSON responses, and converts failures into app-level errors.

**Acceptance criteria:**
- [ ] Adapter can run `herdr status server` and parse success/failure.
- [ ] Adapter exposes a helper for JSON commands and a helper for text/read commands.
- [ ] Missing `herdr` returns a clear setup error instead of a stack trace.

**Verification:**
- [ ] Unit-style smoke script can call adapter status successfully.
- [ ] Temporarily overriding the Herdr command to a missing binary produces a controlled error.

**Dependencies:** None

**Files likely touched:**
- `amp_host/herdr.py`
- `amp_host/app.py`

**Estimated scope:** Small: 1-2 files

## Task 2: Model Herdr Agent Records

**Description:** Add dataclasses or typed helpers that map Herdr JSON into the shape the frontend already expects.

**Acceptance criteria:**
- [ ] Herdr agent records include id/name, directory id, directory label, prompt preview, started timestamp if available, pane id, workspace id, and status.
- [ ] Records from unrelated Herdr panes are ignored.
- [ ] Records whose cwd is outside the allowlist are ignored even if their name matches the prefix.

**Verification:**
- [ ] Fixture-based parser test covers matching agent, unrelated name, and disallowed cwd.

**Dependencies:** Task 1

**Files likely touched:**
- `amp_host/herdr.py`
- `amp_host/config.py`

**Estimated scope:** Small: 1-2 files

### Checkpoint: Adapter Foundation

- [ ] `uv run python -m compileall amp_host`
- [ ] `herdr status server` works through the adapter
- [ ] No frontend behavior changed yet

### Phase 2: Backend Replacement

## Task 3: Replace Local LaunchManager With HerdrAgentManager

**Description:** Replace `LaunchManager` usage with a manager that starts Herdr-backed Amp agents and submits the prompt through `pane run`.

**Acceptance criteria:**
- [ ] `POST /api/launches` validates the same payload as before.
- [ ] It starts a Herdr agent with a unique `amp-host-` name.
- [ ] It extracts `pane_id` from `agent start`.
- [ ] It submits the prompt via `herdr pane run <pane_id> <prompt>`.
- [ ] It returns a launch-shaped JSON object the current frontend can render.

**Verification:**
- [ ] Manual local POST starts an Amp agent visible in `herdr agent list`.
- [ ] Multiline prompt is submitted and visible in `herdr agent read`.
- [ ] Browser launch adds an active row.

**Dependencies:** Tasks 1-2

**Files likely touched:**
- `amp_host/app.py`
- `amp_host/herdr.py`
- `amp_host/launches.py`

**Estimated scope:** Medium: 3 files

## Task 4: List Active Herdr Agents

**Description:** Make `GET /api/launches` query Herdr instead of in-memory local process state.

**Acceptance criteria:**
- [ ] Active agents survive Flask server restart because listing comes from Herdr.
- [ ] Only agents with the Amp Host prefix and allowlisted cwd are returned.
- [ ] Herdr unavailable returns a useful API error.

**Verification:**
- [ ] Start an agent, restart Flask, refresh UI, and confirm the active row remains.
- [ ] Create or observe an unrelated Herdr pane and confirm it does not appear.

**Dependencies:** Task 3

**Files likely touched:**
- `amp_host/app.py`
- `amp_host/herdr.py`

**Estimated scope:** Small: 1-2 files

## Task 5: Stop Herdr Agents

**Description:** Make the kill endpoint close the Herdr pane for a managed agent.

**Acceptance criteria:**
- [ ] `POST /api/launches/<id>/kill` closes the matching Herdr pane.
- [ ] It refuses to close agents outside the Amp Host prefix/allowlist.
- [ ] The UI removes the row after refresh.

**Verification:**
- [ ] Start an agent, stop it from the UI, confirm `herdr agent list` no longer includes it.
- [ ] Stop endpoint returns 404 for unknown or unmanaged ids.

**Dependencies:** Task 4

**Files likely touched:**
- `amp_host/app.py`
- `amp_host/herdr.py`

**Estimated scope:** Small: 1-2 files

### Checkpoint: Backend Flow

- [ ] `uv run python -m compileall amp_host`
- [ ] End-to-end browser flow starts a Herdr-backed Amp agent
- [ ] Flask restart does not lose active agent visibility
- [ ] Stop button closes the Herdr pane

### Phase 3: UI and Docs Alignment

## Task 6: Rename UI Copy From Launches to Agents

**Description:** Update frontend labels to describe long-lived agents instead of one-shot launches.

**Acceptance criteria:**
- [ ] Button says "Start Agent".
- [ ] Active section says "Active agents".
- [ ] Empty state refers to Amp agents, not local one-shot processes.
- [ ] Mobile layout remains clean.

**Verification:**
- [ ] Browser visual check at phone width.
- [ ] No horizontal overflow.

**Dependencies:** Tasks 3-5

**Files likely touched:**
- `amp_host/templates/index.html`
- `amp_host/static/app.js`
- `amp_host/static/styles.css`

**Estimated scope:** Small: 2-3 files

## Task 7: Update README and Config Notes

**Description:** Update project docs to explain Herdr as a runtime dependency and document the new launch behavior.

**Acceptance criteria:**
- [ ] README says Herdr must be installed and on PATH.
- [ ] README describes `herdr agent start` plus `pane run` behavior at a high level.
- [ ] README no longer claims the app runs `amp -x`.
- [ ] Existing `just run` and `just tailscale` commands remain documented.

**Verification:**
- [ ] README setup flow works from a clean shell with `command -v herdr`.

**Dependencies:** Tasks 3-6

**Files likely touched:**
- `README.md`
- `docs/herdr-integration-design.md`

**Estimated scope:** Small: 1-2 files

### Checkpoint: Complete

- [ ] `uv run python -m compileall amp_host`
- [ ] `just run` starts the app
- [ ] Browser can start an Amp agent
- [ ] Herdr shows the agent with `agent_status`
- [ ] Browser can stop the agent
- [ ] Multiline prompt works
- [ ] Existing local `amp-host.config.json` stays ignored

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Herdr server is not running | High | Adapter reports a setup error and README documents `herdr` startup. |
| `herdr` is missing from PATH | High | Adapter checks command availability and returns a clear error. |
| Herdr CLI JSON changes | Medium | Keep parsing localized in `amp_host/herdr.py`. |
| `pane run` behavior changes for Amp | Medium | Keep validation notes and add a fallback to `agent send` + `pane send-keys enter`. |
| Accidentally managing unrelated Herdr panes | High | Require both `amp-host-` name prefix and allowlisted cwd. |
| Flask restart loses prompt previews | Low | Store preview in Herdr agent name is too cramped; accept missing preview in v1 or keep an optional in-memory preview cache. |

## Open Questions

- Should Amp Host preserve prompt previews across Flask restarts? Herdr listing gives process metadata, not our original prompt.
- Should the stop action first send `ctrl+c` before `pane close`, or is close sufficient for v1?
- Should the UI expose an "Open Herdr" or "Focus Agent" action later?
- Should we keep `/api/launches` compatibility forever or rename to `/api/agents` after the backend migration?
