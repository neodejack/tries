import {
  createBashToolDefinition,
  createFindToolDefinition,
  createGrepToolDefinition,
  createLsToolDefinition,
  createReadToolDefinition,
  createWriteToolDefinition,
  type ExtensionAPI,
  type ToolDefinition,
} from "@earendil-works/pi-coding-agent";
import {
  wrapToolDefinition,
  type TimerRegistry,
  type ToolFamily,
} from "./tool-renderer.js";

export function registerToolOverrides(
  pi: ExtensionAPI,
  cwd: string,
  timers: TimerRegistry,
): void {
  const definitions: Array<{
    definition: ToolDefinition<any, any, any>;
    family: ToolFamily;
  }> = [
      { definition: createBashToolDefinition(cwd), family: "bash" },
      { definition: createReadToolDefinition(cwd), family: "standard" },
      { definition: createWriteToolDefinition(cwd), family: "standard" },
      { definition: createGrepToolDefinition(cwd), family: "standard" },
      { definition: createFindToolDefinition(cwd), family: "standard" },
      { definition: createLsToolDefinition(cwd), family: "standard" },
    ];

  for (const { definition, family } of definitions) {
    pi.registerTool(wrapToolDefinition(definition, family, timers));
  }
}
