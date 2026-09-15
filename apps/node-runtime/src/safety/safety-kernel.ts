import { distance } from "#config";
import type { WorldSnapshot } from "../embodiment/types.ts";
import type { PermissionGate } from "./permissions.ts";

export type EmergencyAction =
  "flee" | "dig_in" | "eat_to_target" | "return_home" | "cancel_skill";

export interface EmergencyAssessment {
  level: "L0" | "L1";
  trigger:
    | "imminent_lethal_damage"
    | "lava_exposure"
    | "suffocation"
    | "hostile_swarm"
    | "immediate_threat"
    | "critical_health"
    | "critical_hunger"
    | "dangerous_path"
    | "protected_area_entry";
  action: EmergencyAction;
  reasonCodes: string[];
}

export type ThreatState = "none" | "nearby" | "immediate";

export interface SafetyThresholds {
  criticalHealth: number;
  lowHealth: number;
  criticalFood: number;
  lowFood: number;
  immediateThreatDistance: number;
  nearbyThreatDistance: number;
  swarmCount: number;
  hazardDistance: number;
  lowAir: number;
  /** Exploration is only permitted above these values. */
  safeEnvelopeHealth: number;
  safeEnvelopeFood: number;
}

export const DEFAULT_THRESHOLDS: SafetyThresholds = Object.freeze({
  criticalHealth: 6,
  lowHealth: 12,
  criticalFood: 6,
  lowFood: 12,
  immediateThreatDistance: 7,
  nearbyThreatDistance: 16,
  swarmCount: 3,
  hazardDistance: 2,
  lowAir: 80,
  safeEnvelopeHealth: 16,
  safeEnvelopeFood: 14,
});

const EDIBLE =
  /(^cooked_|^sweet_berries$|^apple$|^bread$|^carrot$|^baked_potato$)/;

export const edibleCount = (snapshot: WorldSnapshot): number =>
  snapshot.inventory
    .filter((item) => EDIBLE.test(item.name))
    .reduce((total, item) => total + item.count, 0);

/**
 * The safety hierarchy.
 *
 *   L0 hard safety
 *   L1 emergency survival
 *   L2 active survival goal
 *   L3 routine optimisation
 *   L4 exploration
 *
 * L0 and L1 belong to Node alone. Cognition cannot suppress them, cannot see
 * enough to bypass them, and is told after the fact what actually happened.
 */
export class SafetyKernel {
  readonly thresholds: SafetyThresholds;
  readonly #permissions: PermissionGate;

  constructor(
    permissions: PermissionGate,
    thresholds: SafetyThresholds = DEFAULT_THRESHOLDS,
  ) {
    this.#permissions = permissions;
    this.thresholds = thresholds;
  }

  threatState(snapshot: WorldSnapshot): ThreatState {
    const hostiles = snapshot.entities.filter((entity) => entity.hostile);
    if (
      hostiles.some(
        (e) => e.distance <= this.thresholds.immediateThreatDistance,
      )
    )
      return "immediate";
    if (
      hostiles.some((e) => e.distance <= this.thresholds.nearbyThreatDistance)
    )
      return "nearby";
    return "none";
  }

  /** True when the exploration envelope (L4) is open. */
  safeEnvelope(snapshot: WorldSnapshot): boolean {
    return (
      snapshot.alive &&
      snapshot.health >= this.thresholds.safeEnvelopeHealth &&
      snapshot.food >= this.thresholds.safeEnvelopeFood &&
      this.threatState(snapshot) === "none" &&
      this.#hazardDistance(snapshot) > this.thresholds.hazardDistance
    );
  }

  #hazardDistance(snapshot: WorldSnapshot): number {
    let nearest = Number.POSITIVE_INFINITY;
    for (const hazard of snapshot.hazards)
      nearest = Math.min(nearest, distance(snapshot.position, hazard.position));
    return nearest;
  }

  /**
   * Evaluated before every proposal and on every execution checkpoint.
   * Returning an assessment means Node acts now, whatever cognition wanted.
   */
  assess(snapshot: WorldSnapshot): EmergencyAssessment | null {
    if (!snapshot.connected || !snapshot.alive) return null;
    const t = this.thresholds;

    const standingHazard = snapshot.hazards.find(
      (hazard) => distance(snapshot.position, hazard.position) <= 1.5,
    );
    if (
      standingHazard &&
      (standingHazard.kind === "lava" || standingHazard.kind === "fire")
    )
      return {
        level: "L0",
        trigger: "lava_exposure",
        action: "flee",
        reasonCodes: ["standing_in_hazard", `hazard_${standingHazard.kind}`],
      };

    if (snapshot.air <= t.lowAir)
      return {
        level: "L0",
        trigger: "suffocation",
        action: "flee",
        reasonCodes: ["air_below_threshold"],
      };

    if (!this.#permissions.areas.permitted(snapshot.position))
      return {
        level: "L0",
        trigger: "protected_area_entry",
        action: "return_home",
        reasonCodes: ["position_outside_permitted_territory"],
      };

    const hostiles = snapshot.entities.filter((entity) => entity.hostile);
    const immediate = hostiles.filter(
      (e) => e.distance <= t.immediateThreatDistance,
    );
    if (snapshot.health <= t.criticalHealth && immediate.length > 0)
      return {
        level: "L1",
        trigger: "imminent_lethal_damage",
        action: "flee",
        reasonCodes: ["critical_health", "hostile_in_contact_range"],
      };
    if (immediate.length >= t.swarmCount)
      return {
        level: "L1",
        trigger: "hostile_swarm",
        action: "dig_in",
        reasonCodes: [`hostiles_${immediate.length}`],
      };
    if (immediate.length > 0)
      return {
        level: "L1",
        trigger: "immediate_threat",
        action: "flee",
        reasonCodes: [`hostile_${immediate[0]?.name ?? "unknown"}`],
      };

    if (snapshot.food <= t.criticalFood && edibleCount(snapshot) > 0)
      return {
        level: "L1",
        trigger: "critical_hunger",
        action: "eat_to_target",
        reasonCodes: ["food_below_critical", "edible_food_available"],
      };
    if (
      snapshot.health <= t.criticalHealth &&
      edibleCount(snapshot) > 0 &&
      snapshot.food < 18
    )
      return {
        level: "L1",
        trigger: "critical_health",
        action: "eat_to_target",
        reasonCodes: ["health_below_critical", "regeneration_requires_food"],
      };
    return null;
  }
}
