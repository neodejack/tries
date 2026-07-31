import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";
import { test } from "node:test";
import type {
  Theme,
  ToolDefinition,
} from "@earendil-works/pi-coding-agent";
import { Text, type Component } from "@earendil-works/pi-tui";
import { StatusPrefixComponent } from "../src/status-component.js";
import {
  renderStatusIndicator,
  startSpinner,
  stopAllSpinners,
  stopSpinner,
  wrapToolDefinition,
  type TimerRegistry,
  type ToolRowState,
} from "../src/tool-renderer.js";
import { createBrailleSpinner } from "../src/braille-spinner.js";

const ANSI_PATTERN = /\u001B\[[0-?]*[ -/]*[@-~]/g;

function plain(value: string): string {
  return value.replace(ANSI_PATTERN, "");
}

const theme = {
  fg(color: string, value: string) {
    const codes: Record<string, number> = {
      accent: 34,
      success: 32,
      error: 31,
      toolTitle: 37,
    };
    return `\u001b[${codes[color] ?? 0}m${value}\u001b[0m`;
  },
  bold(value: string) {
    return `\u001b[1m${value}\u001b[22m`;
  },
} as Theme;

function renderFirstLine(component: Component, width = 80): string {
  return (component.render(width)[0] ?? "").trimEnd();
}

function context(
  overrides: Partial<Record<string, unknown>> = {},
): Record<string, unknown> {
  return {
    args: {},
    toolCallId: "call-1",
    invalidate() {},
    lastComponent: undefined,
    state: {},
    cwd: "/tmp",
    executionStarted: true,
    argsComplete: true,
    isPartial: true,
    expanded: false,
    showImages: true,
    isError: false,
    ...overrides,
  };
}

function fakeDefinition(
  name: "bash" | "read",
): ToolDefinition<any, any, any> {
  const execute = async () => ({
    content: [{ type: "text" as const, text: "native execution" }],
    details: { untouched: true },
  });

  return {
    name,
    label: name,
    description: `native ${name}`,
    parameters: {} as never,
    executionMode: "parallel",
    execute,
    renderCall(_args, _theme, renderContext) {
      const text = (renderContext.lastComponent as Text | undefined)
        ?? new Text("", 0, 0);
      text.setText(name === "bash" ? "$ echo native" : "read native.txt");
      return text;
    },
    renderResult(_result, _options, _theme, renderContext) {
      const text = (renderContext.lastComponent as Text | undefined)
        ?? new Text("", 0, 0);
      text.setText("native result");
      return text;
    },
  };
}

test("renders family-specific colored terminal markers", () => {
  assert.match(
    renderStatusIndicator("bash", "succeeded", "unused", theme),
    /^\u001b\[32m\$/,
  );
  assert.match(
    renderStatusIndicator("bash", "failed", "unused", theme),
    /^\u001b\[31m\$/,
  );
  assert.match(
    renderStatusIndicator("standard", "succeeded", "unused", theme),
    /^\u001b\[32m✓/,
  );
  assert.match(
    renderStatusIndicator("standard", "failed", "unused", theme),
    /^\u001b\[31m×/,
  );
  assert.match(
    renderStatusIndicator("standard", "running", "⠂", theme),
    /^\u001b\[34m⠂/,
  );
});

test("prefix component replaces bash's native prompt and aligns continuation lines", () => {
  const inner: Component = {
    invalidate() {},
    render: () => [
      "\u001b[1m$ echo native\u001b[22m",
      "wrapped continuation",
    ],
  };
  const component = new StatusPrefixComponent(
    inner,
    () => "\u001b[31m$\u001b[0m",
    { stripFirstLinePrefix: "$ " },
  );
  const lines = component.render(80);

  assert.equal(plain(lines[0] ?? ""), "$ echo native");
  assert.equal(plain(lines[1] ?? ""), "  wrapped continuation");
});

test("bash uses Braille while running and a single dollar marker when settled", () => {
  const timers: TimerRegistry = new Set();
  const wrapped = wrapToolDefinition(fakeDefinition("bash"), "bash", timers);
  const rendererState = {};
  const runningContext = context({ state: rendererState });

  const running = wrapped.renderCall?.({}, theme, runningContext as never);
  assert.ok(running);
  const runningText = plain(renderFirstLine(running));
  assert.doesNotMatch(runningText, /^\$/);
  assert.match(runningText, /echo native$/);

  const settledContext = context({
    state: rendererState,
    isPartial: false,
    isError: false,
  });
  const settled = wrapped.renderCall?.({}, theme, settledContext as never);
  assert.ok(settled);
  assert.equal(plain(renderFirstLine(settled)), "$ echo native");
  assert.equal(timers.size, 0);
});

test("standard tools use tick on success and cross on failure", () => {
  const timers: TimerRegistry = new Set();
  const success = wrapToolDefinition(fakeDefinition("read"), "standard", timers);
  const successComponent = success.renderCall?.(
    {},
    theme,
    context({ isPartial: false, isError: false }) as never,
  );
  assert.ok(successComponent);
  assert.equal(
    plain(renderFirstLine(successComponent)),
    "✓ read native.txt",
  );

  const failure = wrapToolDefinition(fakeDefinition("read"), "standard", timers);
  const failureComponent = failure.renderCall?.(
    {},
    theme,
    context({ isPartial: false, isError: true }) as never,
  );
  assert.ok(failureComponent);
  assert.equal(
    plain(renderFirstLine(failureComponent)),
    "× read native.txt",
  );
});

test("wrapper preserves execution metadata and delegates native result rendering", () => {
  const original = fakeDefinition("read");
  const timers: TimerRegistry = new Set();
  const wrapped = wrapToolDefinition(original, "standard", timers);
  const rendererContext = context({ isPartial: false });
  const result = {
    content: [{ type: "text" as const, text: "result" }],
    details: { untouched: true },
  };

  assert.equal(wrapped.execute, original.execute);
  assert.equal(wrapped.parameters, original.parameters);
  assert.equal(wrapped.description, original.description);
  assert.equal(wrapped.executionMode, original.executionMode);
  assert.equal(wrapped.renderShell, "self");

  const component = wrapped.renderResult?.(
    result,
    { expanded: false, isPartial: false },
    theme,
    rendererContext as never,
  );
  assert.ok(component);
  assert.equal(plain(renderFirstLine(component)), "native result");
});

test("spinner timer invalidates, stops, and is cleaned up idempotently", async () => {
  const timers: TimerRegistry = new Set();
  const state: ToolRowState = {
    phase: "running",
    spinner: createBrailleSpinner(),
  };
  let invalidations = 0;

  startSpinner(state, () => {
    invalidations += 1;
  }, timers, 5);
  startSpinner(state, () => {
    invalidations += 100;
  }, timers, 5);

  await delay(22);
  assert.equal(timers.size, 1);
  assert.ok(invalidations >= 2);

  stopSpinner(state, timers);
  const stoppedAt = invalidations;
  await delay(12);
  assert.equal(invalidations, stoppedAt);
  assert.equal(timers.size, 0);

  stopSpinner(state, timers);
  stopAllSpinners(timers);
  assert.equal(timers.size, 0);
});
