import test from "node:test";
import assert from "node:assert/strict";
import {
  explorationChannel,
  family,
  priorityChannel,
  saturation,
  type AffectBounds,
  type JournalEvent,
} from "../../apps/cli/src/affect-analysis.ts";

/**
 * The research analysis of affect's opportunity and dynamics (R1.5), on
 * hand-built journals whose answers are known. Nothing here runs Person.
 */

const BOUNDS: AffectBounds = {
  bias_limit: 25,
  tolerance_range: [0.5, 1.25],
  half_lives: { valence: 6000, unease: 1200, control: 12000 },
  ranges: { valence: [-1, 1], unease: [0, 1], control: [-1, 1] },
  swings: {
    protective: { protective: 0, outgoing: 50, fixed: 25 },
    outgoing: { protective: 37.5, outgoing: 0, fixed: 25 },
    fixed: { protective: 12.5, outgoing: 25, fixed: 0 },
  },
};

const goal = (
  goal_type: string,
  character: string,
  base: number,
  bias = 0,
) => ({
  goal_id: `goal_${goal_type.toLowerCase()}`,
  goal_type,
  source: character === "fixed" ? "emergency" : "homeostasis",
  character,
  base_priority: base,
  affect_bias: bias,
  priority: base + bias,
});

const selected = (
  chosen: string,
  candidates: ReturnType<typeof goal>[],
): JournalEvent => ({
  type: "goal_selected",
  payload: {
    goal_id: `goal_${chosen.toLowerCase()}`,
    affect_bias: candidates.find((c) => c.goal_type === chosen)?.affect_bias,
    candidates,
  },
});

test("a near tie is an opportunity for affect and a wide margin is not", () => {
  const events = [
    // 300 protective against 290 outgoing: the outgoing goal can gain 37.5.
    selected("ESTABLISH_STORAGE", [
      goal("ESTABLISH_STORAGE", "protective", 300),
      goal("ESTABLISH_TOOLS", "outgoing", 290),
    ]),
    // 320 outgoing against 220 protective: 50 is not enough.
    selected("ESTABLISH_TOOLS", [
      goal("ESTABLISH_TOOLS", "outgoing", 320),
      goal("ESTABLISH_STORAGE", "protective", 220),
    ]),
    // Two protective goals: one state biases both alike.
    selected("ESTABLISH_STORAGE", [
      goal("ESTABLISH_STORAGE", "protective", 300),
      goal("MAINTAIN_RESERVES", "protective", 299),
    ]),
    // One candidate: nothing to reorder.
    selected("SECURE_FOOD", [goal("SECURE_FOOD", "outgoing", 600)]),
  ];
  const metrics = priorityChannel(events, BOUNDS);
  assert.equal(metrics["priority_decisions"], 4);
  assert.equal(metrics["priority_multi_candidate"], 3);
  assert.equal(metrics["priority_opportunities"], 1);
  assert.equal(metrics["priority_opportunity_rate"], 0.25);
  assert.equal(metrics["priority_changed"], 0);
});

test("affect changing a choice is counted, and only where it could", () => {
  const events = [
    selected("ESTABLISH_TOOLS", [
      goal("ESTABLISH_STORAGE", "protective", 300, -10),
      goal("ESTABLISH_TOOLS", "outgoing", 290, 20),
    ]),
    selected("ESTABLISH_STORAGE", [
      goal("ESTABLISH_STORAGE", "protective", 300, 10),
      goal("ESTABLISH_TOOLS", "outgoing", 290, -5),
    ]),
  ];
  const metrics = priorityChannel(events, BOUNDS);
  assert.equal(metrics["priority_opportunities"], 2);
  assert.equal(metrics["priority_changed"], 1);
  assert.equal(metrics["priority_changed_given_opportunity"], 0.5);
  assert.equal(metrics["priority_changed_without_opportunity"], 0);
});

const routine = (
  routine_id: string,
  low: number,
  neutral: number,
  high: number,
) => ({
  routine_id,
  score: neutral,
  score_at_tolerance: { low, neutral, high },
});

test("the exploration channel is measured apart from the priority channel", () => {
  const events: JournalEvent[] = [
    // The untried routine leads at neutral tolerance and loses at low.
    {
      type: "routine_selected",
      payload: {
        routine_id: "r_known",
        tolerance: 0.6,
        scored_choice: true,
        candidates: [
          routine("r_known", 0.5, 0.5, 0.5),
          routine("r_untried", 0.2, 0.7, 0.9),
        ],
      },
    },
    // The fallback decided: no opportunity whatever the scores.
    {
      type: "routine_selected",
      payload: {
        routine_id: "r_a",
        tolerance: 0.6,
        scored_choice: false,
        candidates: [routine("r_a", 0, 1, 2), routine("r_b", 3, 3, 3)],
      },
    },
    // One routine dominates across the whole range.
    {
      type: "routine_selected",
      payload: {
        routine_id: "r_a",
        tolerance: 1,
        scored_choice: true,
        candidates: [routine("r_a", 1, 1.2, 1.3), routine("r_b", 0, 0.1, 0.2)],
      },
    },
  ];
  const metrics = explorationChannel(events);
  assert.equal(metrics["exploration_selections"], 3);
  assert.equal(metrics["exploration_scored_choices"], 2);
  assert.equal(metrics["exploration_opportunities"], 1);
  assert.equal(metrics["exploration_changed"], 1);
  assert.equal(metrics["exploration_changed_without_opportunity"], 0);
  assert.deepEqual(priorityChannel(events, BOUNDS)["priority_decisions"], 0);
});

const appraisal = (
  at: number,
  trigger: string,
  before: Record<string, number>,
  after: Record<string, number>,
): JournalEvent => ({
  type: "affect_appraised",
  payload: {
    experienced_tick: at,
    trigger,
    components: {},
    before,
    after,
    delta: Object.fromEntries(
      Object.keys(after).map((k) => [k, (after[k] ?? 0) - (before[k] ?? 0)]),
    ),
  },
});

test("time near a bound and time to settle follow from half-lives", () => {
  const zero = { valence: 0, unease: 0, control: 0 };
  const events = [
    appraisal(0, "goal_blocked_secure_food", zero, {
      valence: -1,
      unease: 0,
      control: 0,
    }),
  ];
  const { metrics, distributions } = saturation(events, BOUNDS, 6000);
  // |valence| decays from 1 past 0.9 after 6000 * log2(1 / 0.9) ticks.
  const near = 6000 * Math.log2(1 / 0.9);
  assert.equal(
    metrics["affect_valence_near_bound_fraction"],
    Number((near / 6000).toFixed(4)),
  );
  assert.equal(metrics["affect_valence_saturation_episodes"], 1);
  assert.equal(metrics["affect_valence_final"], -0.5);
  assert.equal(
    metrics["affect_valence_ticks_to_settle_after_last_push"],
    Math.round(6000 * Math.log2(1 / 0.1)),
  );
  assert.equal(metrics["affect_valence_input_negative"], -1);
  assert.equal(metrics["affect_unease_saturation_episodes"], 0);
  assert.deepEqual(distributions["valence_input_by_trigger"], {
    goal_blocked: -1,
  });
});

test("a saturation episode continues across appraisals that keep it there", () => {
  const events = [
    appraisal(0, "harm", { valence: 0 }, { valence: -1 }),
    appraisal(10, "harm", { valence: -0.999 }, { valence: -1 }),
    appraisal(20, "harm", { valence: -0.999 }, { valence: -1 }),
  ];
  const { metrics } = saturation(
    events,
    { ...BOUNDS, half_lives: { valence: 6000 } },
    20,
  );
  assert.equal(metrics["affect_valence_saturation_episodes"], 1);
  assert.equal(metrics["affect_valence_longest_saturation_ticks"], 20);
});

test("repeated experience is told apart from one experience counted twice", () => {
  const zero = { valence: 0 };
  const events = [
    appraisal(5, "action_failed", zero, { valence: -0.08 }),
    appraisal(5, "action_failed", zero, { valence: -0.08 }),
    appraisal(
      5,
      "goal_blocked_secure_food",
      { valence: -0.08 },
      { valence: -0.18 },
    ),
    appraisal(9, "perceived_threat", zero, zero),
    appraisal(11, "perceived_threat", zero, zero),
  ];
  const { metrics, distributions } = saturation(
    events,
    { ...BOUNDS, half_lives: { valence: 6000 } },
    20,
  );
  assert.equal(metrics["affect_identical_appraisal_records"], 1);
  assert.equal(metrics["affect_moments_with_several_appraisals"], 1);
  assert.equal(metrics["affect_min_ticks_between_threat_appraisals"], 2);
  assert.deepEqual(distributions["appraisals_at_one_moment"], {
    "action_failed+action_failed+goal_blocked_secure_food": 1,
  });
});

test("appraisal families group goal and project events by what happened", () => {
  assert.equal(family("goal_blocked_establish_tools"), "goal_blocked");
  assert.equal(family("goal_complete_secure_food"), "goal_complete");
  assert.equal(family("project_abandoned_improve_home"), "project_abandoned");
  assert.equal(family("perceived_threat"), "perceived_threat");
});

const tonic = (
  at: number,
  before: Record<string, number>,
  after: Record<string, number>,
  offset: Record<string, number>,
): JournalEvent => ({
  type: "affect_tonic",
  payload: { experienced_tick: at, before, after, offset, pressures: {} },
});

test("a held tonic offset is followed exactly between records", () => {
  const zero = { valence: 0 };
  const events = [tonic(0, zero, zero, { valence: -0.5 })];
  const { metrics } = saturation(
    events,
    { ...BOUNDS, half_lives: { valence: 6000 } },
    6000,
  );
  // One half-life toward -0.5 from 0 reaches -0.25.
  assert.equal(metrics["affect_valence_final"], -0.25);
  assert.equal(metrics["affect_valence_tonic_time_fraction"], 1);
  assert.equal(metrics["affect_valence_tonic_offset_mean"], -0.5);
  assert.equal(metrics["affect_valence_near_bound_fraction"], 0);
  assert.equal(metrics["affect_tonic_updates"], 1);
  assert.equal(metrics["affect_appraisals"], 0);
});

test("a condition strong enough reaches a bound late, and never settles while it holds", () => {
  const zero = { valence: 0 };
  const events = [
    tonic(0, zero, zero, { valence: -1 }),
    appraisal(1, "harm", { valence: 0 }, { valence: -0.05 }),
  ];
  const { metrics } = saturation(
    events,
    { ...BOUNDS, half_lives: { valence: 6000 } },
    30001,
  );
  // From -0.05 toward -1, |valence| passes 0.9 after 6000 * log2(0.95 / 0.1).
  const reach = 6000 * Math.log2(0.95 / 0.1);
  assert.equal(
    metrics["affect_valence_near_bound_fraction"],
    Number(((30000 - reach) / 30001).toFixed(4)),
  );
  assert.equal(metrics["affect_valence_saturation_episodes"], 1);
  assert.equal(metrics["affect_valence_ticks_to_settle_after_last_push"], -1);
});
