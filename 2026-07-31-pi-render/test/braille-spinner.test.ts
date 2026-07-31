import assert from "node:assert/strict";
import { test } from "node:test";
import {
  advanceBrailleSpinner,
  brailleGlyph,
  createBrailleSpinner,
} from "../src/braille-spinner.js";

function repeatingRandom(values: readonly number[]): () => number {
  let index = 0;
  return () => {
    const value = values[index % values.length];
    index += 1;
    return value ?? 0.9;
  };
}

test("creates an eight-cell default spinner and a Unicode Braille glyph", () => {
  const state = createBrailleSpinner();
  const glyph = brailleGlyph(state);
  const codePoint = glyph.codePointAt(0);

  assert.equal(state.cells.length, 8);
  assert.equal(state.generation, 0);
  assert.equal([...glyph].length, 1);
  assert.ok(codePoint !== undefined);
  assert.ok(codePoint >= 0x2800 && codePoint <= 0x28ff);
});

test("advances a live state deterministically", () => {
  const state = {
    cells: [true, true, true, false, false, false, false, false],
    generation: 0,
  };
  const next = advanceBrailleSpinner(
    state,
    repeatingRandom([0.9, 0.1, 0.9, 0.1]),
  );

  assert.equal(next.cells.length, 8);
  assert.equal(next.previousCells?.length, 8);
  assert.equal(next.generation, 1);
  assert.notDeepEqual(next.cells, state.cells);
});

test("restarts a dead state with at least three live cells", () => {
  const restarted = advanceBrailleSpinner(
    {
      cells: Array.from({ length: 8 }, () => false),
      generation: 3,
    },
    repeatingRandom([0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1]),
  );

  assert.equal(restarted.generation, 0);
  assert.ok(restarted.cells.filter(Boolean).length >= 3);
  assert.equal(restarted.previousCells, undefined);
});

test("masks the animation to Amp's narrow Braille presentation", () => {
  const glyph = brailleGlyph({
    cells: Array.from({ length: 8 }, () => true),
    generation: 0,
  });
  const bits = (glyph.codePointAt(0) ?? 0) - 0x2800;

  assert.equal(bits & ~0x36, 0);
  assert.equal(bits, 0x36);
});
