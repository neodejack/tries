# Pi tool-call renderer extension: implementation plan

## Objective

Build a small Pi extension that changes only the presentation of the built-in
`bash`, `read`, `write`, `grep`, `find`, and `ls` tool calls.

The implementation must use Pi's public extension API and public package
exports so that upgrading Pi requires, at most, an ordinary compatibility
update rather than a patch to Pi internals.

Baseline used for this plan: `@earendil-works/pi-coding-agent` 0.83.0.

## Rendering contract

| Tool family | Running | Success | Failure |
| --- | --- | --- | --- |
| `bash` | Blue animated Braille glyph | Green `$` | Red `$` |
| `read`, `write`, `grep`, `find`, `ls` | Blue animated Braille glyph | Green `✓` | Red `×` |

For all six tools:

- Remove the default colored tool-call background.
- Preserve the built-in tool's existing wording, arguments, output, truncation,
  and expanded rendering.
- Use the Amp-inspired animated Braille marker at approximately 200 ms per
  frame.
- Do not aggregate multiple calls or add semantic labels such as "Explored",
  "Read", "Searched", or "Ran".

Explicitly out of scope:

- `edit` and apply-patch rendering.
- MCP tool rendering.
- Changes to tool execution or parameter schemas.
- Transcript-level aggregation.
- Pi internal imports, monkey-patching, or TUI source modifications.

## Chevron decision

Do not render `▸` or `▾` in the first version.

Pi publicly exposes whether tool output is globally expanded, but it does not
expose whether a particular result has additional hidden content. A chevron
would therefore be misleading for rows whose collapsed and expanded output is
identical.

A later version may add chevrons if it can determine, through public APIs and
without double-running renderer side effects, that:

- `▸` means this row has hidden detail and is collapsed.
- `▾` means this row has hidden detail and is expanded.

## Public API boundary

Import only from:

- `@earendil-works/pi-coding-agent`
- `@earendil-works/pi-tui`
- Normal development dependencies declared by this project

Use these public Pi exports:

- `ExtensionAPI`
- `ToolDefinition`
- `createBashToolDefinition`
- `createReadToolDefinition`
- `createWriteToolDefinition`
- `createGrepToolDefinition`
- `createFindToolDefinition`
- `createLsToolDefinition`

Each factory supplies the native schema, metadata, execution function, and
renderer. The extension will spread the original definition, keep execution
unchanged, set `renderShell: "self"`, and replace only `renderCall` and
`renderResult` with delegating wrappers.

Never import from `dist/`, `src/`, or an unexported package subpath.

## Proposed project layout

```text
2026-07-31-pi-render/
├── src/
│   ├── index.ts                 # Pi extension entry point
│   ├── register-tools.ts        # Create and re-register the six definitions
│   ├── tool-renderer.ts         # Status wrapper and native-renderer delegation
│   ├── status-component.ts      # Prefix a marker without changing native text
│   └── braille-spinner.ts       # Deterministic Amp-style animation
├── test/
│   ├── braille-spinner.test.ts
│   ├── tool-renderer.test.ts
│   └── registration.test.ts
├── package.json
├── tsconfig.json
├── README.md
└── IMPLEMENTATION_PLAN.md
```

## Concise call stack

```text
Pi loads src/index.ts
└─ piRenderExtension(pi)
   └─ registerToolOverrides(pi, process.cwd(), timers)
      ├─ create*ToolDefinition(cwd)             [Pi public factory]
      └─ pi.registerTool(wrapToolDefinition(...))
         ├─ execute(...)                        [unchanged native execution]
         ├─ renderCall(...)
         │  ├─ delegate to native renderCall(...)
         │  ├─ ensure/advance Braille animation
         │  └─ StatusPrefixComponent.render(...)
         └─ renderResult(...)
            ├─ set running/success/failure phase
            ├─ stop animation after final result
            └─ delegate to native renderResult(...)
```

## Concise data flow

```text
model arguments
  → original Pi schema and execute()
  → native AgentToolResult / streaming update
  → wrapper determines row phase only
  → original renderer produces native call/result Component
  → prefix component adds Braille, ✓, ×, or $
  → renderShell: "self" prevents the colored outer Box
  → terminal
```

The wrapper must not transform parameters, results, details, exit codes, file
contents, or truncation metadata.

## Types and new function signatures

The signatures below are the intended implementation surface. Generics may be
refined during type-checking, but their responsibilities should remain stable.

```ts
import type {
  ExtensionAPI,
  ToolDefinition,
  ToolRenderResultOptions,
} from "@earendil-works/pi-coding-agent";
import type { Component } from "@earendil-works/pi-tui";

export type ToolFamily = "bash" | "standard";
export type ToolPhase = "running" | "succeeded" | "failed";

export interface BrailleSpinnerState {
  cells: boolean[];
  previousCells?: boolean[];
  generation: number;
}

export interface ToolRowState {
  phase: ToolPhase;
  spinner: BrailleSpinnerState;
  timer?: ReturnType<typeof setInterval>;
  nativeCallComponent?: Component;
  nativeResultComponent?: Component;
}

export type TimerRegistry = Set<ReturnType<typeof setInterval>>;

export default function piRenderExtension(pi: ExtensionAPI): void;

export function registerToolOverrides(
  pi: ExtensionAPI,
  cwd: string,
  timers: TimerRegistry,
): void;

export function wrapToolDefinition(
  original: ToolDefinition<any, any, any>,
  family: ToolFamily,
  timers: TimerRegistry,
): ToolDefinition<any, any, ToolRowState>;

export function renderStatusIndicator(
  family: ToolFamily,
  phase: ToolPhase,
  glyph: string,
  theme: Parameters<
    NonNullable<ToolDefinition["renderCall"]>
  >[1],
): string;

export function settleRow(
  state: ToolRowState,
  isError: boolean,
  timers: TimerRegistry,
): void;

export function startSpinner(
  state: ToolRowState,
  invalidate: () => void,
  timers: TimerRegistry,
  intervalMs?: number,
): void;

export function stopSpinner(
  state: ToolRowState,
  timers: TimerRegistry,
): void;

export function stopAllSpinners(timers: TimerRegistry): void;

export function createBrailleSpinner(
  random?: () => number,
): BrailleSpinnerState;

export function advanceBrailleSpinner(
  state: BrailleSpinnerState,
  random?: () => number,
): BrailleSpinnerState;

export function brailleGlyph(state: BrailleSpinnerState): string;

export class StatusPrefixComponent implements Component {
  constructor(
    inner: Component,
    getPrefix: () => string,
  );

  invalidate(): void;
  render(width: number): string[];
}
```

`wrapToolDefinition` will internally create a native renderer context that
preserves the built-in renderer's own state and previous component. Our
`ToolRowState` must not overwrite state expected by the native renderer.

## Implementation phases

### 1. Project scaffold

- Create the TypeScript package and scripts for type-check, tests, and a local
  Pi smoke run.
- Declare Pi and Pi TUI as peer dependencies with 0.83.0 as the tested minimum.
- Pin them as development dependencies for reproducible tests.
- Document loading the extension directly with Pi's extension flag before
  considering permanent installation.

### 2. Spinner

- Implement the eight-cell Braille state machine modeled on Amp's visual
  behavior.
- Advance it every 200 ms.
- Randomize a new viable state when it stalls, cycles, empties, or reaches its
  generation limit.
- Inject the random source in tests so frame sequences are deterministic.
- Keep the timer row-local and clear it on settlement and session shutdown.

### 3. Status-prefix component

- Render the native call component at the remaining terminal width.
- Prefix its first line with the colored status marker and a single space.
- Indent continuation lines so wrapped commands remain aligned.
- Preserve ANSI styling and calculate visible width correctly.
- Delegate invalidation to the wrapped native component.

### 4. Public tool-definition wrappers

- Create definitions for `bash`, `read`, `write`, `grep`, `find`, and `ls`
  through their public factories.
- Preserve every original field by default.
- Override only `renderShell`, `renderCall`, and `renderResult`.
- Continue delegating to the original renderers so wording and output behavior
  stay native.
- Treat partial results as running.
- On a final result, use the public `context.isError` value to select success or
  failure and stop the timer.
- Use the bash marker family only for `bash`; use the standard family for the
  other five tools.

### 5. Lifecycle cleanup

- Maintain one registry containing all active spinner timers.
- Clear the row timer immediately when its call settles.
- Register a public `session_shutdown` handler that clears any remaining
  timers.
- Make cleanup idempotent.

### 6. Automated verification

Unit tests:

- Spinner frames map to valid Unicode Braille glyphs.
- Deterministic state evolution, restart, and generation-limit behavior.
- Timers start once, invalidate at each frame, and stop exactly once.
- Bash renders blue Braille while running, green `$` on success, and red `$`
  on failure.
- Other wrapped tools render blue Braille, green `✓`, and red `×`.
- Prefixing preserves wrapped-line alignment and ANSI content.
- `renderShell` is `"self"` for precisely the six selected tools.
- Original schemas, descriptions, execution modes, and `execute` references
  remain unchanged.
- `edit` is never registered or imported.

Compatibility tests:

- Type-check against Pi 0.83.0.
- Type-check and run the renderer tests against the latest available Pi
  release before upgrading the tested range.
- Fail CI if an import resolves through an internal package path.

### 7. Isolated interactive smoke test

Load the extension in a fresh Pi process and invoke:

- Successful and failing `bash` commands.
- Successful `read`, `write`, `grep`, `find`, and `ls` calls.
- At least one sufficiently slow call to observe several Braille frames.
- An expanded/collapsed result toggle to confirm native output is preserved.
- An `edit` call to confirm its existing renderer is unchanged.

Capture screenshots of running, successful, and failed states. Do not attach
the extension to an already-running Pi session.

## Acceptance criteria

- No selected tool row has the default black, green, or red background.
- Every selected tool uses the animated blue Braille marker while running.
- `bash` settles to a green or red `$`.
- The other five tools settle to a green `✓` or red `×`.
- Native wording, output, truncation, and expansion behavior remain intact.
- `edit` and MCP rendering are unaffected.
- No chevron is displayed in v1.
- There are no Pi internal imports or modifications.
- All tests pass on the pinned baseline and the interactive screenshots match
  the rendering contract.
