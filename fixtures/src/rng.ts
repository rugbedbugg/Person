/** Deterministic, seedable PRNG. Recorded seeds make fixture runs replayable. */
export class SeededRandom {
  #state: number;

  constructor(seed: number) {
    this.#state = seed >>> 0 || 0x9e3779b9;
  }

  next(): number {
    this.#state = (this.#state + 0x6d2b79f5) >>> 0;
    let t = this.#state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  int(maxExclusive: number): number {
    return Math.floor(this.next() * maxExclusive);
  }
}
