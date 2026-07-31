import {
  sliceByColumn,
  visibleWidth,
  type Component,
} from "@earendil-works/pi-tui";

const ANSI_PATTERN = /\u001B(?:\[[0-?]*[ -/]*[@-~]|\][^\u0007]*(?:\u0007|\u001B\\))/g;

export interface StatusPrefixOptions {
  stripFirstLinePrefix?: string;
}

function plainText(value: string): string {
  return value.replace(ANSI_PATTERN, "");
}

function stripVisiblePrefix(line: string, expectedPrefix: string): string {
  if (!plainText(line).startsWith(expectedPrefix)) {
    return line;
  }

  const lineWidth = visibleWidth(line);
  return sliceByColumn(
    line,
    visibleWidth(expectedPrefix),
    Math.max(0, lineWidth - visibleWidth(expectedPrefix)),
  );
}

export class StatusPrefixComponent implements Component {
  constructor(
    private inner: Component,
    private readonly getPrefix: () => string,
    private readonly options: StatusPrefixOptions = {},
  ) {}

  setInner(inner: Component): void {
    this.inner = inner;
  }

  invalidate(): void {
    this.inner.invalidate?.();
  }

  render(width: number): string[] {
    const prefix = `${this.getPrefix()} `;
    const prefixWidth = visibleWidth(prefix);
    const innerWidth = Math.max(1, width - prefixWidth);
    const lines = this.inner.render(innerWidth);

    return lines.map((line, index) => {
      if (index === 0) {
        const content = this.options.stripFirstLinePrefix
          ? stripVisiblePrefix(line, this.options.stripFirstLinePrefix)
          : line;
        return `${prefix}${content}`;
      }
      return `${" ".repeat(prefixWidth)}${line}`;
    });
  }
}
