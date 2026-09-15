import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { ValidateFunction } from "ajv";
import type { ParameterSpec, SkillSpec } from "./types.ts";

export const SPEC_DIRECTORY = fileURLToPath(
  new URL("../specs/", import.meta.url),
);

export class SkillSpecError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SkillSpecError";
  }
}

export interface FactVocabulary {
  description: string;
  facts: Record<string, string>;
}

function compileSpecValidator(directory: string): ValidateFunction {
  const ajv = new Ajv2020({
    strict: true,
    allErrors: true,
    allowUnionTypes: true,
  });
  const schema: object = JSON.parse(
    readFileSync(path.join(directory, "skill-spec.schema.json"), "utf8"),
  );
  return ajv.compile(schema);
}

/**
 * The skill library, loaded from the canonical JSON specs that the cognition
 * process also reads. Nothing here executes anything: this is the contract the
 * planner reasons over and the runtime enforces.
 */
export class SkillRegistry {
  readonly specs: ReadonlyMap<string, SkillSpec>;
  readonly facts: FactVocabulary;
  readonly revision: string;

  constructor(directory: string = SPEC_DIRECTORY) {
    const validate = compileSpecValidator(directory);
    this.facts = JSON.parse(
      readFileSync(path.join(directory, "facts.json"), "utf8"),
    );
    const specs = new Map<string, SkillSpec>();
    const digest = createHash("sha256");
    for (const file of readdirSync(directory).sort()) {
      if (!file.endsWith(".json")) continue;
      if (file === "facts.json" || file === "skill-spec.schema.json") continue;
      const raw = readFileSync(path.join(directory, file), "utf8");
      const spec: SkillSpec = JSON.parse(raw);
      if (!validate(spec))
        throw new SkillSpecError(
          `${file} is not a valid SkillSpec: ${(validate.errors ?? [])
            .map((e) => `${e.instancePath} ${e.message}`)
            .join("; ")}`,
        );
      if (spec.id !== path.basename(file, ".json"))
        throw new SkillSpecError(
          `${file} declares mismatched skill id ${spec.id}`,
        );
      for (const condition of spec.preconditions)
        if (!(condition.fact in this.facts.facts))
          throw new SkillSpecError(
            `${spec.id} precondition uses unknown fact ${condition.fact}`,
          );
      for (const effect of spec.expectedEffects) {
        if (!(effect.fact in this.facts.facts))
          throw new SkillSpecError(
            `${spec.id} effect uses unknown fact ${effect.fact}`,
          );
        if (effect.scalesWith && !(effect.scalesWith in spec.parameters))
          throw new SkillSpecError(
            `${spec.id} effect scales with unknown parameter ${effect.scalesWith}`,
          );
      }
      specs.set(spec.id, Object.freeze(spec));
      digest.update(`${file}:${raw}`);
    }
    if (specs.size === 0)
      throw new SkillSpecError(`No skill specs found in ${directory}`);
    this.specs = specs;
    this.revision = digest.digest("hex").slice(0, 16);
  }

  get ids(): string[] {
    return [...this.specs.keys()].sort();
  }

  get(id: string): SkillSpec {
    const spec = this.specs.get(id);
    if (!spec) throw new SkillSpecError(`Unknown skill ${id}`);
    return spec;
  }

  has(id: string): boolean {
    return this.specs.has(id);
  }

  /**
   * Applies defaults and rejects anything the spec does not describe. The Node
   * runtime runs this on every proposal, so a malformed or out-of-range
   * parameter can never reach an executor.
   */
  resolveParameters(
    id: string,
    supplied: Readonly<Record<string, number | string | boolean>>,
  ): Record<string, number | string | boolean> {
    const spec = this.get(id);
    const resolved: Record<string, number | string | boolean> = {};
    for (const key of Object.keys(supplied))
      if (!(key in spec.parameters))
        throw new SkillSpecError(`${id} does not accept the parameter ${key}`);
    for (const [key, parameter] of Object.entries(spec.parameters)) {
      const value =
        key in supplied
          ? (supplied[key] as number | string | boolean)
          : parameter.default;
      resolved[key] = checkParameter(id, key, parameter, value);
    }
    return resolved;
  }
}

function checkParameter(
  id: string,
  key: string,
  parameter: ParameterSpec,
  value: number | string | boolean,
): number | string | boolean {
  const fail = (reason: string): never => {
    throw new SkillSpecError(`${id}.${key} ${reason}`);
  };
  if (parameter.type === "boolean") {
    if (typeof value !== "boolean") return fail("must be a boolean");
    return value;
  }
  if (parameter.type === "string") {
    if (typeof value !== "string") return fail("must be a string");
    if (parameter.enum && !parameter.enum.includes(value))
      return fail(`must be one of ${parameter.enum.join(", ")}`);
    return value;
  }
  if (typeof value !== "number" || !Number.isFinite(value))
    return fail("must be a number");
  if (parameter.type === "integer" && !Number.isInteger(value))
    return fail("must be an integer");
  if (parameter.minimum !== undefined && value < parameter.minimum)
    return fail(`must be at least ${parameter.minimum}`);
  if (parameter.maximum !== undefined && value > parameter.maximum)
    return fail(`must be at most ${parameter.maximum}`);
  return value;
}

let shared: SkillRegistry | undefined;

export function skillRegistry(): SkillRegistry {
  shared ??= new SkillRegistry();
  return shared;
}
