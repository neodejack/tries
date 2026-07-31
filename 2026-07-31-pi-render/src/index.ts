import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerToolOverrides } from "./register-tools.js";
import {
  stopAllSpinners,
  type TimerRegistry,
} from "./tool-renderer.js";

export default function piRenderExtension(pi: ExtensionAPI): void {
  const timers: TimerRegistry = new Set();
  registerToolOverrides(pi, process.cwd(), timers);

  pi.on("session_shutdown", () => {
    stopAllSpinners(timers);
  });
}
