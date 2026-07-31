import type {
  Theme,
  ToolDefinition,
  ToolRenderResultOptions,
} from "@earendil-works/pi-coding-agent";
import { Container, Text, type Component } from "@earendil-works/pi-tui";
import {
  advanceBrailleSpinner,
  brailleGlyph,
  createBrailleSpinner,
  type BrailleSpinnerState,
} from "./braille-spinner.js";
import { StatusPrefixComponent } from "./status-component.js";

export type ToolFamily = "bash" | "standard";
export type ToolPhase = "running" | "succeeded" | "failed";
export type TimerRegistry = Set<ReturnType<typeof setInterval>>;

export interface ToolRowState {
  phase: ToolPhase;
  spinner: BrailleSpinnerState;
  timer?: ReturnType<typeof setInterval>;
  nativeCallComponent?: Component;
  nativeResultComponent?: Component;
  wrappedCallComponent?: StatusPrefixComponent;
}

const ROW_STATE = Symbol("pi-amp-tool-renderer.row-state");

type SharedRendererState = Record<PropertyKey, unknown> & {
  [ROW_STATE]?: ToolRowState;
};

type AnyToolDefinition = ToolDefinition<any, any, any>;
type RenderContext = Parameters<NonNullable<AnyToolDefinition["renderCall"]>>[2];

function getRowState(state: SharedRendererState): ToolRowState {
  state[ROW_STATE] ??= {
    phase: "running",
    spinner: createBrailleSpinner(),
  };
  return state[ROW_STATE];
}

function nativeContext(
  context: RenderContext,
  lastComponent: Component | undefined,
): RenderContext {
  return {
    ...context,
    lastComponent,
  };
}

export function renderStatusIndicator(
  family: ToolFamily,
  phase: ToolPhase,
  glyph: string,
  theme: Theme,
): string {
  if (phase === "running") {
    return theme.fg("accent", glyph);
  }

  const marker = family === "bash" ? "$" : phase === "succeeded" ? "✓" : "×";
  return theme.fg(phase === "succeeded" ? "success" : "error", marker);
}

export function startSpinner(
  state: ToolRowState,
  invalidate: () => void,
  timers: TimerRegistry,
  intervalMs = 200,
): void {
  if (state.timer) {
    return;
  }

  const timer = setInterval(() => {
    state.spinner = advanceBrailleSpinner(state.spinner);
    invalidate();
  }, intervalMs);
  timer.unref?.();
  state.timer = timer;
  timers.add(timer);
}

export function stopSpinner(
  state: ToolRowState,
  timers: TimerRegistry,
): void {
  if (!state.timer) {
    return;
  }

  clearInterval(state.timer);
  timers.delete(state.timer);
  state.timer = undefined;
}

export function settleRow(
  state: ToolRowState,
  isError: boolean,
  timers: TimerRegistry,
): void {
  state.phase = isError ? "failed" : "succeeded";
  stopSpinner(state, timers);
}

export function stopAllSpinners(timers: TimerRegistry): void {
  for (const timer of timers) {
    clearInterval(timer);
  }
  timers.clear();
}

function syncRowPhase(
  row: ToolRowState,
  context: RenderContext,
  timers: TimerRegistry,
): void {
  if (context.isPartial) {
    row.phase = "running";
    startSpinner(row, context.invalidate, timers);
    return;
  }

  settleRow(row, context.isError, timers);
}

function callNativeRenderer(
  original: AnyToolDefinition,
  args: unknown,
  theme: Theme,
  context: RenderContext,
  row: ToolRowState,
): Component {
  if (!original.renderCall) {
    return new Text(theme.fg("toolTitle", theme.bold(original.label)), 0, 0);
  }

  const component = original.renderCall(
    args,
    theme,
    nativeContext(context, row.nativeCallComponent),
  );
  row.nativeCallComponent = component;
  return component;
}

function callNativeResultRenderer(
  original: AnyToolDefinition,
  result: Parameters<NonNullable<AnyToolDefinition["renderResult"]>>[0],
  options: ToolRenderResultOptions,
  theme: Theme,
  context: RenderContext,
  row: ToolRowState,
): Component {
  if (!original.renderResult) {
    return new Container();
  }

  const component = original.renderResult(
    result,
    options,
    theme,
    nativeContext(context, row.nativeResultComponent),
  );
  row.nativeResultComponent = component;
  return component;
}

export function wrapToolDefinition(
  original: AnyToolDefinition,
  family: ToolFamily,
  timers: TimerRegistry,
): ToolDefinition<any, any, SharedRendererState> {
  return {
    ...original,
    renderShell: "self",
    renderCall(args, theme, context) {
      const row = getRowState(context.state);
      syncRowPhase(row, context, timers);
      const nativeComponent = callNativeRenderer(original, args, theme, context, row);
      const getPrefix = () =>
        renderStatusIndicator(
          family,
          row.phase,
          brailleGlyph(row.spinner),
          theme,
        );

      if (!row.wrappedCallComponent) {
        row.wrappedCallComponent = new StatusPrefixComponent(
          nativeComponent,
          getPrefix,
          family === "bash" ? { stripFirstLinePrefix: "$ " } : {},
        );
      } else {
        row.wrappedCallComponent.setInner(nativeComponent);
      }

      return row.wrappedCallComponent;
    },
    renderResult(result, options, theme, context) {
      const row = getRowState(context.state);
      if (!options.isPartial) {
        settleRow(row, context.isError, timers);
      }
      return callNativeResultRenderer(
        original,
        result,
        options,
        theme,
        context,
        row,
      );
    },
  };
}
