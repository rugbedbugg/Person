import type { PersonConfig, Position } from "#config";
import type { Permission } from "#skills";
import type { ContainerView, EntityView } from "../embodiment/types.ts";
import { ProtectedAreas } from "./protected-areas.ts";

export interface PermissionVerdict {
  allowed: boolean;
  reason: string;
}

const allow = (): PermissionVerdict => ({ allowed: true, reason: "permitted" });
const deny = (reason: string): PermissionVerdict => ({
  allowed: false,
  reason,
});

/**
 * Capability gate.
 *
 * Every physical capability is explicit and fails closed. Two rules have no
 * configuration path to "yes" at all, and are checked here as well as in the
 * configuration schema: Person never deposits into a container it did not
 * place, and Person never targets players, villagers, named or tamed animals.
 */
export class PermissionGate {
  readonly areas: ProtectedAreas;
  readonly #config: PersonConfig;

  constructor(
    config: PersonConfig,
    areas: ProtectedAreas = new ProtectedAreas(config),
  ) {
    this.#config = config;
    this.areas = areas;
  }

  get permissions(): PersonConfig["permissions"] {
    return this.#config.permissions;
  }

  mayEnter(position: Position): PermissionVerdict {
    return this.areas.permitted(position) ? allow() : deny("protected_area");
  }

  mayHarvest(position: Position): PermissionVerdict {
    if (!this.areas.permitted(position)) return deny("protected_area");
    if (!this.areas.harvestable(position)) return deny("outside_resource_area");
    return allow();
  }

  mayMine(position: Position): PermissionVerdict {
    return this.mayHarvest(position);
  }

  mayBuild(position: Position): PermissionVerdict {
    if (!this.#config.permissions.building.enabled)
      return deny("building_disabled");
    if (!this.areas.permitted(position)) return deny("protected_area");
    return allow();
  }

  mayEmergencyDig(position: Position): PermissionVerdict {
    if (!this.areas.permitted(position)) return deny("protected_area");
    if (!this.areas.harvestable(position)) return deny("outside_resource_area");
    return allow();
  }

  /**
   * Hunting is restricted to unnamed, untamed passive animals, for food.
   * Players, villagers, named animals and tamed animals are never targets, and
   * combat with players is out of scope entirely.
   */
  mayHunt(entity: EntityView): PermissionVerdict {
    if (entity.player) return deny("player_target_forbidden");
    if (entity.villager) return deny("villager_target_forbidden");
    if (entity.named) return deny("named_animal_forbidden");
    if (entity.tamed) return deny("tamed_animal_forbidden");
    if (!entity.passive) return deny("not_a_passive_animal");
    if (!this.#config.permissions.hunting.passiveUnnamedAnimals)
      return deny("hunting_disabled");
    if (!this.areas.permitted(entity.position)) return deny("protected_area");
    return allow();
  }

  /** Bounded self-defence during an emergency. Never players or villagers. */
  mayDefend(entity: EntityView): PermissionVerdict {
    if (entity.player) return deny("player_target_forbidden");
    if (entity.villager) return deny("villager_target_forbidden");
    if (entity.tamed || entity.named) return deny("owned_entity_forbidden");
    if (!entity.hostile) return deny("not_a_hostile");
    return allow();
  }

  mayDeposit(container: ContainerView): PermissionVerdict {
    if (container.storageId === null)
      return deny("existing_container_deposit_forbidden");
    if (!this.#config.permissions.containers.owned.deposit)
      return deny("owned_deposit_disabled");
    if (!this.areas.permitted(container.position))
      return deny("protected_area");
    return allow();
  }

  mayWithdraw(container: ContainerView): PermissionVerdict {
    const owned = container.storageId !== null;
    const setting = owned
      ? this.#config.permissions.containers.owned.withdraw
      : this.#config.permissions.containers.existing.withdraw;
    if (!setting)
      return deny(
        owned ? "owned_withdraw_disabled" : "existing_withdraw_disabled",
      );
    if (!this.areas.permitted(container.position))
      return deny("protected_area");
    return allow();
  }

  /** Which of a skill's declared permissions are currently unavailable. */
  missingFor(required: readonly Permission[]): Permission[] {
    const config = this.#config.permissions;
    const granted: Record<Permission, boolean> = {
      harvest_resource: true,
      mine_resource: true,
      build: config.building.enabled,
      hunt_passive_animal: config.hunting.passiveUnnamedAnimals,
      place_owned_storage: config.building.enabled,
      deposit_owned_storage: config.containers.owned.deposit,
      withdraw_owned_storage: config.containers.owned.withdraw,
      withdraw_existing_container: config.containers.existing.withdraw,
      emergency_dig: true,
      craft: true,
      consume: true,
    };
    return required.filter((permission) => !granted[permission]);
  }

  /** The summary Node publishes in the Observation. */
  summary(): Record<string, boolean> {
    const config = this.#config.permissions;
    return {
      harvest: true,
      mine: true,
      build: config.building.enabled,
      huntPassive: config.hunting.passiveUnnamedAnimals,
      depositOwned: config.containers.owned.deposit,
      withdrawOwned: config.containers.owned.withdraw,
      withdrawExisting: config.containers.existing.withdraw,
      craft: true,
      consume: true,
    };
  }
}
