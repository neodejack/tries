import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import type {
  ExtensionAPI,
  ToolDefinition,
} from "@earendil-works/pi-coding-agent";
import { registerToolOverrides } from "../src/register-tools.js";

test("registers exactly the six selected public built-ins", () => {
  const registered: ToolDefinition[] = [];
  const pi = {
    registerTool(definition: ToolDefinition) {
      registered.push(definition);
    },
  } as ExtensionAPI;

  registerToolOverrides(pi, process.cwd(), new Set());

  assert.deepEqual(
    registered.map((definition) => definition.name),
    ["bash", "read", "write", "grep", "find", "ls"],
  );
  assert.ok(registered.every((definition) => definition.renderShell === "self"));
  assert.ok(registered.every((definition) => typeof definition.execute === "function"));
  assert.ok(!registered.some((definition) => definition.name === "edit"));
});

test("source imports stay on public package entry points", async () => {
  const sourceDirectory = path.resolve("src");
  const sourceFiles = (await readdir(sourceDirectory))
    .filter((file) => file.endsWith(".ts"));

  for (const sourceFile of sourceFiles) {
    const contents = await readFile(path.join(sourceDirectory, sourceFile), "utf8");
    assert.doesNotMatch(
      contents,
      /@earendil-works\/(?:pi-coding-agent|pi-tui)\/(?:dist|src)\//,
      `${sourceFile} imports a package-internal path`,
    );
  }
});
