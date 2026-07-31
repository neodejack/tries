# Pi Amp-style tool renderer

A small Pi extension that removes colored tool-call backgrounds and adds an
Amp-inspired status marker to selected built-in tools.

## Status markers

| Tools | Running | Success | Failure |
| --- | --- | --- | --- |
| `bash` | Animated accent-colored Braille | Green `$` | Red `$` |
| `read`, `write`, `grep`, `find`, `ls` | Animated accent-colored Braille | Green `✓` | Red `×` |

The extension delegates schemas and execution to Pi's public built-in tool
definitions. It leaves `edit`, apply-patch, and MCP tools unchanged.

Tested against Pi 0.83.0. The source imports only the public entry points of
`@earendil-works/pi-coding-agent` and `@earendil-works/pi-tui`.

## Development

```sh
pnpm install
pnpm check
```

## Run in a fresh Pi session

From any working directory:

```sh
pi -e /Users/zili/code/personal/tries/2026-07-31-pi-render/src/index.ts
```

The extension is loaded only into that newly started process. This command does
not alter already-running Pi sessions or permanently install the extension.

## Verification

The automated checks cover the spinner state machine, timer cleanup,
family-specific status markers, native-renderer delegation, registration scope,
and a guard against package-internal imports.

A fresh, ephemeral Pi session was also used to exercise all six overridden
tools plus an unchanged `edit` call:

- [Running state](./outputs/pi-render-running.png)
- [Completed states and unchanged edit UI](./outputs/pi-render-completed.png)

The smoke session was started with `--no-session`; it did not attach to or
modify any existing Pi session.
