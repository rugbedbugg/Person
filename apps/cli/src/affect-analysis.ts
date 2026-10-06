/**
 * Affect analysis for research (R1.5, ADR 0013).
 *
 * Derived after a run from Person's evidence journal and from the bounds the
 * affect code itself reports (`person-cognition --affect-bounds`). None of
 * these quantities exists inside Person, and none is ever sent to it: they
 * describe decisions, they do not make them.
 *
 * Two causal channels are measured apart:
 *
 * - the priority channel, where affect adds a bounded bias to a goal's
 *   priority according to the goal's character;
 * - the exploration channel, where affect scales the evidence policy's
 *   exploration bonus and risk weight through a tolerance factor.
 *
 * For each, a decision is an *opportunity* when some state the current
 * architecture can reach would have made a different candidate win, and
 * *changed* when the affect actually present did make a different candidate
 * win than the same decision without affect.
 */

export interface AffectBounds {
  bias_limit: number;
  tolerance_range: [number, number];
  half_lives: Record<string, number>;
  ranges: Record<string, [number, number]>;
  /** The largest `bias(a) - bias(b)` for goal characters a and b. */
  swings: Record<string, Record<string, number>>;
}

export interface JournalEvent {
  type: string;
  payload: Record<string, unknown>;
}

interface GoalCandidate {
  goal_id: string;
  goal_type: string;
  character: string;
  base_priority: number;
  affect_bias: number;
  priority: number;
}

interface RoutineCandidate {
  routine_id: string;
  score: number;
  score_at_tolerance: { low: number; neutral: number; high: number } | null;
}

const ratio = (part: number, whole: number): number =>
  whole === 0 ? 0 : Number((part / whole).toFixed(4));

const mean = (values: number[]): number =>
  values.length === 0
    ? 0
    : Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(4));

/** The goal stack's own order: higher first, then goal type. */
const before = (
  a: { value: number; goal_type: string },
  b: { value: number; goal_type: string },
): boolean =>
  a.value > b.value || (a.value === b.value && a.goal_type < b.goal_type);

export function priorityChannel(
  events: JournalEvent[],
  bounds: AffectBounds,
): Record<string, number> {
  let decisions = 0;
  let multi = 0;
  let opportunities = 0;
  let changed = 0;
  let changedWithoutOpportunity = 0;
  const margins: number[] = [];
  const swings: number[] = [];
  const contributions: number[] = [];
  for (const event of events) {
    if (event.type !== "goal_selected") continue;
    const candidates = event.payload["candidates"] as
      GoalCandidate[] | undefined;
    if (!candidates || candidates.length === 0) continue;
    decisions += 1;
    contributions.push(Math.abs(Number(event.payload["affect_bias"] ?? 0)));
    const byBase = candidates
      .map((c) => ({ ...c, value: c.base_priority }))
      .sort((a, b) => (before(a, b) ? -1 : before(b, a) ? 1 : 0));
    const top = byBase[0]!;
    const chosen = String(event.payload["goal_id"]);
    if (chosen !== top.goal_id) {
      changed += 1;
    }
    if (candidates.length < 2) continue;
    multi += 1;
    margins.push(top.base_priority - byBase[1]!.base_priority);
    let possible = false;
    let largest = 0;
    for (const other of byBase.slice(1)) {
      const swing = bounds.swings[other.character]?.[top.character] ?? 0;
      largest = Math.max(largest, swing);
      if (
        before(
          { value: other.base_priority + swing, goal_type: other.goal_type },
          { value: top.base_priority, goal_type: top.goal_type },
        )
      )
        possible = true;
    }
    swings.push(largest);
    if (possible) opportunities += 1;
    if (chosen !== top.goal_id && !possible) changedWithoutOpportunity += 1;
  }
  return {
    priority_decisions: decisions,
    priority_multi_candidate: multi,
    priority_opportunities: opportunities,
    priority_opportunity_rate: ratio(opportunities, decisions),
    priority_changed: changed,
    priority_changed_given_opportunity: ratio(changed, opportunities),
    priority_changed_without_opportunity: changedWithoutOpportunity,
    priority_mean_margin: mean(margins),
    priority_mean_max_swing: mean(swings),
    priority_mean_abs_contribution: mean(contributions),
  };
}

function leader(
  candidates: RoutineCandidate[],
  key: "low" | "neutral" | "high",
): RoutineCandidate {
  // Candidates are journalled best first at the tolerance actually used, so
  // an exact tie keeps that order, as the policy's own tie-break does.
  let best = candidates[0]!;
  for (const candidate of candidates.slice(1))
    if (candidate.score_at_tolerance![key] > best.score_at_tolerance![key])
      best = candidate;
  return best;
}

export function explorationChannel(
  events: JournalEvent[],
): Record<string, number> {
  let selections = 0;
  let scored = 0;
  let multi = 0;
  let opportunities = 0;
  let changed = 0;
  let changedWithoutOpportunity = 0;
  const tolerances: number[] = [];
  const margins: number[] = [];
  for (const event of events) {
    if (event.type !== "routine_selected") continue;
    const candidates = event.payload["candidates"] as
      RoutineCandidate[] | undefined;
    if (!candidates?.length || !candidates[0]!.score_at_tolerance) continue;
    selections += 1;
    const tolerance = Number(event.payload["tolerance"] ?? 1);
    tolerances.push(tolerance);
    if (event.payload["scored_choice"] !== true) continue;
    scored += 1;
    if (candidates.length < 2) continue;
    multi += 1;
    const neutral = leader(candidates, "neutral");
    const others = candidates.filter((c) => c !== neutral);
    margins.push(
      neutral.score_at_tolerance!.neutral -
        Math.max(...others.map((c) => c.score_at_tolerance!.neutral)),
    );
    // Each score is piecewise linear in tolerance with its only bend at 1, so
    // another candidate overtakes the neutral leader somewhere in the range
    // exactly when it does so at one of the range's ends.
    const possible = others.some(
      (c) =>
        c.score_at_tolerance!.low > neutral.score_at_tolerance!.low ||
        c.score_at_tolerance!.high > neutral.score_at_tolerance!.high,
    );
    if (possible) opportunities += 1;
    const chosen = String(event.payload["routine_id"]);
    if (chosen !== neutral.routine_id) {
      changed += 1;
      if (!possible) changedWithoutOpportunity += 1;
    }
  }
  return {
    exploration_selections: selections,
    exploration_scored_choices: scored,
    exploration_multi_candidate: multi,
    exploration_opportunities: opportunities,
    exploration_opportunity_rate: ratio(opportunities, scored),
    exploration_changed: changed,
    exploration_changed_given_opportunity: ratio(changed, opportunities),
    exploration_changed_without_opportunity: changedWithoutOpportunity,
    exploration_mean_margin: mean(margins),
    exploration_mean_tolerance: mean(tolerances),
  };
}

interface Appraised {
  at: number;
  kind: "phasic" | "tonic";
  trigger: string;
  components: unknown;
  before: Record<string, number>;
  delta: Record<string, number>;
  after: Record<string, number>;
  /** The tonic offset in force from this record on (ADR 0014). */
  offset: Record<string, number>;
}

export interface SaturationOptions {
  /** How close to a bound counts as near it, as a fraction of the bound. */
  near: number;
  /** How close to baseline counts as settled. */
  settled: number;
}

export const SATURATION: SaturationOptions = { near: 0.9, settled: 0.1 };

/**
 * Where a dimension is after `t` ticks, relaxing from `x0` toward `target`
 * with half-life `h`: the exact solution affect itself integrates.
 */
const along = (x0: number, target: number, h: number, t: number): number =>
  target + (x0 - target) * 0.5 ** (t / h);

/** When the relaxation from `x0` toward `target` passes `level`, if ever. */
function crossing(
  x0: number,
  target: number,
  h: number,
  level: number,
): number | null {
  const ratio = (level - target) / (x0 - target);
  if (!(ratio > 0 && ratio <= 1)) return null;
  return h * Math.log2(1 / ratio);
}

/** Time within [0, length] that the relaxation spends at or above `level`. */
function above(
  x0: number,
  target: number,
  h: number,
  length: number,
  level: number,
): number {
  if (x0 >= level && target >= level) return length;
  const cross = crossing(x0, target, h, level);
  if (x0 >= level) return Math.min(length, cross ?? length);
  if (target > level)
    return cross === null ? 0 : Math.max(0, length - Math.min(length, cross));
  return 0;
}

/**
 * How affect moved over a run, in Person's experienced time.
 *
 * Between two records a dimension relaxes toward its baseline shifted by the
 * tonic offset in force (zero without interoception), with its half-life. So
 * its whole trajectory follows exactly from the journalled states, the
 * offsets set by `affect_tonic` records, and the half-lives.
 */
export function saturation(
  events: JournalEvent[],
  bounds: AffectBounds,
  experiencedEnd: number,
  options: SaturationOptions = SATURATION,
): {
  metrics: Record<string, number>;
  distributions: Record<string, Record<string, number>>;
} {
  let offset: Record<string, number> = {};
  const records: Appraised[] = [];
  for (const event of events) {
    if (event.type !== "affect_appraised" && event.type !== "affect_tonic")
      continue;
    if (event.type === "affect_tonic")
      offset = (event.payload["offset"] ?? {}) as Record<string, number>;
    const before = event.payload["before"] as Record<string, number>;
    const after = event.payload["after"] as Record<string, number>;
    records.push({
      at: Number(event.payload["experienced_tick"]),
      kind: event.type === "affect_tonic" ? "tonic" : "phasic",
      trigger: String(event.payload["trigger"] ?? "tonic"),
      components: event.payload["components"],
      before,
      delta:
        (event.payload["delta"] as Record<string, number> | undefined) ??
        Object.fromEntries(
          Object.keys(after).map((k) => [
            k,
            (after[k] ?? 0) - (before[k] ?? 0),
          ]),
        ),
      after,
      offset,
    });
  }
  const appraised = records.filter((record) => record.kind === "phasic");
  const metrics: Record<string, number> = {
    affect_appraisals: appraised.length,
    affect_tonic_updates: records.length - appraised.length,
  };
  const distributions: Record<string, Record<string, number>> = {};
  const end = Math.max(experiencedEnd, records.at(-1)?.at ?? 0);

  for (const dimension of Object.keys(bounds.half_lives).sort()) {
    const h = bounds.half_lives[dimension]!;
    const [low, high] = bounds.ranges[dimension]!;
    const bound = Math.max(Math.abs(low), Math.abs(high));
    const threshold = options.near * bound;
    const target = (record: Appraised) =>
      Math.max(low, Math.min(high, record.offset[dimension] ?? 0));

    let nearTime = 0;
    let episodes = 0;
    let longest = 0;
    let open = 0;
    let inEpisode = false;
    let positive = 0;
    let negative = 0;
    let pressed = 0;
    let offsetArea = 0;
    records.forEach((record, index) => {
      const change = record.delta[dimension] ?? 0;
      if (record.kind === "phasic") {
        if (change > 0) positive += change;
        if (change < 0) negative += change;
      }
      const length = Math.max(0, (records[index + 1]?.at ?? end) - record.at);
      const x0 = record.after[dimension] ?? 0;
      const goal = target(record);
      if (goal !== 0) pressed += length;
      offsetArea += goal * length;
      const near =
        above(x0, goal, h, length, threshold) +
        above(-x0, -goal, h, length, threshold);
      if (near > 0) {
        if (inEpisode && Math.abs(x0) >= threshold) open += near;
        else {
          episodes += 1;
          open = near;
        }
        nearTime += near;
        longest = Math.max(longest, open);
        inEpisode = Math.abs(along(x0, goal, h, length)) >= threshold;
      } else inEpisode = false;
    });

    const last = records.at(-1);
    const final = last
      ? along(last.after[dimension] ?? 0, target(last), h, end - last.at)
      : 0;
    // Settling after the last record that pushed this dimension away from
    // baseline: follow the trajectory from there until it is within the
    // settled band. Beyond the run's end the last offset is assumed to hold;
    // if that offset itself lies outside the band it never settles (-1).
    let recovery = 0;
    let away = -1;
    records.forEach((record, index) => {
      if (
        Math.abs(record.after[dimension] ?? 0) >
        Math.abs(record.before[dimension] ?? 0)
      )
        away = index;
    });
    if (away !== -1) {
      recovery = -1;
      for (let index = away; index < records.length; index++) {
        const record = records[index]!;
        const x0 = record.after[dimension] ?? 0;
        const goal = target(record);
        const stop = records[index + 1]?.at ?? Infinity;
        // Settled means within the band and not being pulled out of it: a
        // segment whose target lies outside the band cannot settle.
        let needed: number | null = null;
        if (Math.abs(goal) < options.settled)
          needed =
            Math.abs(x0) < options.settled
              ? 0
              : crossing(x0, goal, h, Math.sign(x0) * options.settled);
        if (needed !== null && record.at + needed <= stop) {
          recovery = record.at + needed - records[away]!.at;
          break;
        }
      }
    }

    const key = (name: string) => `affect_${dimension}_${name}`;
    metrics[key("near_bound_fraction")] = ratio(nearTime, end);
    metrics[key("saturation_episodes")] = episodes;
    metrics[key("longest_saturation_ticks")] = Math.round(longest);
    metrics[key("final")] = Number(final.toFixed(4));
    metrics[key("ticks_to_settle_after_last_push")] = Math.round(recovery);
    metrics[key("input_positive")] = Number(positive.toFixed(4));
    metrics[key("input_negative")] = Number(negative.toFixed(4));
    metrics[key("tonic_time_fraction")] = ratio(pressed, end);
    metrics[key("tonic_offset_mean")] =
      end === 0 ? 0 : Number((offsetArea / end).toFixed(4));

    const byTrigger: Record<string, number> = {};
    for (const record of appraised) {
      const trigger = family(record.trigger);
      byTrigger[trigger] = Number(
        ((byTrigger[trigger] ?? 0) + (record.delta[dimension] ?? 0)).toFixed(4),
      );
    }
    distributions[`${dimension}_input_by_trigger`] = sortKeys(byTrigger);
  }

  // Is any experience counted more than once? Two records identical in time,
  // trigger, components and prior state are either one appraisal recorded
  // twice or two appraisals of the same kind that found the state at a bound
  // (a clamped change leaves `before` unchanged); the journal must be read to
  // tell which. Several appraisals at one moment are shown apart: they may be
  // layers of one event, such as several goals that one action completes.
  const seen = new Set<string>();
  let duplicates = 0;
  const moments = new Map<number, string[]>();
  for (const record of appraised) {
    const identity = JSON.stringify([
      record.at,
      record.trigger,
      record.components,
      record.before,
    ]);
    if (seen.has(identity)) duplicates += 1;
    seen.add(identity);
    moments.set(record.at, [...(moments.get(record.at) ?? []), record.trigger]);
  }
  const together: Record<string, number> = {};
  let shared = 0;
  for (const triggers of moments.values()) {
    if (triggers.length < 2) continue;
    shared += 1;
    const name = [...triggers].sort().join("+");
    together[name] = (together[name] ?? 0) + 1;
  }
  // Threat appraisals: per observation under R1.5, onsets and escalations
  // under ADR 0014.
  const threat = appraised.filter((r) =>
    ["perceived_threat", "threat_onset", "threat_escalation"].includes(
      r.trigger,
    ),
  );
  const gaps = threat
    .slice(1)
    .map((record, index) => record.at - threat[index]!.at);
  metrics["affect_identical_appraisal_records"] = duplicates;
  metrics["affect_moments_with_several_appraisals"] = shared;
  metrics["affect_threat_appraisals"] = threat.length;
  metrics["affect_min_ticks_between_threat_appraisals"] = gaps.length
    ? Math.min(...gaps)
    : 0;
  distributions["appraisal_triggers"] = sortKeys(
    appraised.reduce<Record<string, number>>((counts, record) => {
      counts[record.trigger] = (counts[record.trigger] ?? 0) + 1;
      return counts;
    }, {}),
  );
  distributions["appraisals_at_one_moment"] = sortKeys(together);
  return { metrics, distributions };
}

/**
 * An appraisal's family: goal and project triggers name the goal type or
 * project kind after the event (`goal_blocked_secure_food`), and are grouped
 * by the event alone.
 */
export function family(trigger: string): string {
  const goal = /^goal_(complete|blocked)_/.exec(trigger);
  if (goal) return `goal_${goal[1]}`;
  const project = /^project_(progressed|completed|abandoned)_/.exec(trigger);
  if (project) return `project_${project[1]}`;
  return trigger;
}

function sortKeys(values: Record<string, number>): Record<string, number> {
  return Object.fromEntries(
    Object.entries(values).sort(([a], [b]) => a.localeCompare(b)),
  );
}
