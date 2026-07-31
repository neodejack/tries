const NEIGHBORS: readonly (readonly number[])[] = [
  [1, 3, 4, 5, 7],
  [0, 2, 4, 5, 6],
  [1, 3, 5, 6, 7],
  [0, 2, 4, 6, 7],
  [0, 1, 3, 5, 7],
  [0, 1, 2, 4, 6],
  [1, 2, 3, 5, 7],
  [0, 2, 3, 4, 6],
];

const BRAILLE_BIT_ORDER = [0, 1, 2, 6, 3, 4, 5, 7] as const;
const BRAILLE_BASE = 0x2800;
const AMP_DISPLAY_MASK = 0x36;
const MAX_GENERATIONS = 15;

export interface BrailleSpinnerState {
  cells: boolean[];
  previousCells?: boolean[];
  generation: number;
}

function liveCellCount(cells: readonly boolean[]): number {
  return cells.reduce((count, cell) => count + Number(cell), 0);
}

function sameCells(left: readonly boolean[], right: readonly boolean[] | undefined): boolean {
  return right !== undefined && left.every((cell, index) => cell === right[index]);
}

function randomCells(random: () => number): boolean[] {
  let cells: boolean[];
  do {
    cells = Array.from({ length: 8 }, () => random() > 0.6);
  } while (liveCellCount(cells) < 3);
  return cells;
}

export function createBrailleSpinner(random?: () => number): BrailleSpinnerState {
  return {
    cells: random
      ? randomCells(random)
      : [true, false, true, false, true, false, true, false],
    generation: 0,
  };
}

export function advanceBrailleSpinner(
  state: BrailleSpinnerState,
  random: () => number = Math.random,
): BrailleSpinnerState {
  const nextCells = state.cells.map((alive, index) => {
    const neighbors = NEIGHBORS[index] ?? [];
    const liveNeighbors = neighbors.reduce(
      (count, neighbor) => count + Number(state.cells[neighbor]),
      0,
    );
    return alive
      ? liveNeighbors === 2 || liveNeighbors === 3
      : liveNeighbors === 3 || liveNeighbors === 6;
  });

  const nextGeneration = state.generation + 1;
  const shouldRestart =
    sameCells(nextCells, state.cells) ||
    sameCells(nextCells, state.previousCells) ||
    nextGeneration >= MAX_GENERATIONS ||
    liveCellCount(nextCells) < 2;

  if (shouldRestart) {
    return {
      cells: randomCells(random),
      generation: 0,
    };
  }

  return {
    cells: nextCells,
    previousCells: [...state.cells],
    generation: nextGeneration,
  };
}

export function brailleGlyph(state: BrailleSpinnerState): string {
  let bits = 0;
  for (let bit = 0; bit < BRAILLE_BIT_ORDER.length; bit += 1) {
    const cellIndex = BRAILLE_BIT_ORDER[bit];
    if (cellIndex !== undefined && state.cells[cellIndex]) {
      bits |= 1 << bit;
    }
  }

  return String.fromCodePoint(BRAILLE_BASE | (bits & AMP_DISPLAY_MASK));
}
