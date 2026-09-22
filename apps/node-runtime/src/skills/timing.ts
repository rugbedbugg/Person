import type { ItemStack, Position } from "#protocol";
import type {
  ContainerView,
  CraftResult,
  Embodiment,
  MoveOptions,
  PhysicalGuard,
  WorldSnapshot,
  BlockView,
  EntityView,
  FindBlocksQuery,
} from "../embodiment/types.ts";
import type { GazeDirection } from "../embodiment/gaze.ts";

export type TimedPhase = "navigation" | "interaction" | "waiting";

export interface SkillTimings {
  navigationTicks: number;
  interactionTicks: number;
  waitingTicks: number;
  calls: Record<string, { count: number; ticks: number }>;
}

export const emptyTimings = (): SkillTimings => ({
  navigationTicks: 0,
  interactionTicks: 0,
  waitingTicks: 0,
  calls: {},
});

const PHASES: Record<string, TimedPhase> = {
  moveTo: "navigation",
  waitTicks: "waiting",
  dig: "interaction",
  place: "interaction",
  craft: "interaction",
  smelt: "interaction",
  consume: "interaction",
  attack: "interaction",
  deposit: "interaction",
  withdraw: "interaction",
  inspectContainer: "interaction",
};

/**
 * Wraps a body and measures where its time actually goes.
 *
 * The previous milestone flagged the tick budgets in the skill specs as the
 * numbers most likely to be wrong, and a single elapsed total cannot tell you
 * whether a skill is slow because the walk was long or because the server was.
 * Measuring at the port means every skill is instrumented without any skill
 * having to remember to be.
 */
export function instrument(embodiment: Embodiment): {
  embodiment: Embodiment;
  timings: SkillTimings;
  reset: () => void;
} {
  let timings = emptyTimings();

  const record = (name: string, ticks: number): void => {
    const phase = PHASES[name];
    const spent = Math.max(0, ticks);
    const entry = (timings.calls[name] ??= { count: 0, ticks: 0 });
    entry.count += 1;
    entry.ticks += spent;
    if (phase === "navigation") timings.navigationTicks += spent;
    else if (phase === "interaction") timings.interactionTicks += spent;
    else if (phase === "waiting") timings.waitingTicks += spent;
  };

  async function timed<T>(name: string, run: () => Promise<T>): Promise<T> {
    const before = embodiment.snapshot().tick;
    try {
      return await run();
    } finally {
      record(name, embodiment.snapshot().tick - before);
    }
  }

  const proxy: Embodiment = {
    kind: embodiment.kind,
    setGuard: (guard: PhysicalGuard) => embodiment.setGuard(guard),
    connect: () => embodiment.connect(),
    disconnect: () => embodiment.disconnect(),
    snapshot: (): WorldSnapshot => embodiment.snapshot(),
    blockAt: (position: Position): BlockView | null =>
      embodiment.blockAt(position),
    findBlocks: (query: FindBlocksQuery): BlockView[] =>
      embodiment.findBlocks(query),
    findEntities: (): EntityView[] => embodiment.findEntities(),
    containerAt: (position: Position): ContainerView | null =>
      embodiment.containerAt(position),
    inspectContainer: (position: Position): Promise<ContainerView | null> =>
      timed("inspectContainer", () => embodiment.inspectContainer(position)),
    look: (direction: GazeDirection): Promise<void> =>
      timed("look", () => embodiment.look(direction)),
    moveTo: (position: Position, options?: MoveOptions): Promise<void> =>
      timed("moveTo", () => embodiment.moveTo(position, options)),
    dig: (position: Position): Promise<ItemStack[]> =>
      timed("dig", () => embodiment.dig(position)),
    place: (position: Position, item: string): Promise<void> =>
      timed("place", () => embodiment.place(position, item)),
    craft: (
      item: string,
      times: number,
      table: Position | null,
    ): Promise<CraftResult> =>
      timed("craft", () => embodiment.craft(item, times, table)),
    smelt: (
      input: string,
      times: number,
      furnace: Position,
    ): Promise<CraftResult> =>
      timed("smelt", () => embodiment.smelt(input, times, furnace)),
    consume: (item: string): Promise<void> =>
      timed("consume", () => embodiment.consume(item)),
    attack: (entityId: number): Promise<void> =>
      timed("attack", () => embodiment.attack(entityId)),
    deposit: (position: Position, items: ItemStack[]): Promise<ItemStack[]> =>
      timed("deposit", () => embodiment.deposit(position, items)),
    withdraw: (position: Position, items: ItemStack[]): Promise<ItemStack[]> =>
      timed("withdraw", () => embodiment.withdraw(position, items)),
    waitTicks: (ticks: number): Promise<void> =>
      timed("waitTicks", () => embodiment.waitTicks(ticks)),
    registerOwnedStorage: (position: Position, storageId: string): void =>
      embodiment.registerOwnedStorage(position, storageId),
  };

  return {
    embodiment: proxy,
    get timings() {
      return timings;
    },
    reset: () => {
      timings = emptyTimings();
    },
  };
}

/** How the measured time compares with the budget the skill was given. */
export function budgetPressure(elapsedTicks: number, maxTicks: number): number {
  if (maxTicks <= 0) return 0;
  return Number((elapsedTicks / maxTicks).toFixed(4));
}
