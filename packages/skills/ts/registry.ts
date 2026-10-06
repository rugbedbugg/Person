import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { ValidateFunction } from "ajv";
import { soleEnvironment } from "#protocol";
import type { ParameterSpec, SkillSpec, SkillVocabulary } from "./types.ts";

/** The generic SkillSpec schema. Each environment supplies the specs. */
export const SKILL_SPEC_SCHEMA = fileURLToPath(
  new URL("../schema/skill-spec.schema.json", import.meta.url),
);

/** Files in a skill directory that are not specs. */
const NOT_SPECS = new Set(["facts.json", "vocabulary.json"]);

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

function compileSpecValidator(): ValidateFunction {
  const ajv = new Ajv2020({
    strict: true,
    allErrors: true,
    allowUnionTypes: true,
  });
  const schema: object = JSON.parse(readFileSync(SKILL_SPEC_SCHEMA, "utf8"));
  return ajv.compile(schema);
}

/** What a spec names that its environment's vocabulary does not allow. */
function vocabularyProblems(
  spec: SkillSpec,
  vocabulary: SkillVocabulary,
): string[] {
  const problems: string[] = [];
  if (!vocabulary.categories.includes(spec.category))
    problems.push(`category ${spec.category}`);
  for (const permission of spec.requiredPermissions)
    if (!vocabulary.permissions.includes(permission))
      problems.push(`permission ${permission}`);
  for (const kind of spec.completionEvidence)
    if (!vocabulary.completionEvidence.includes(kind))
      problems.push(`completion evidence ${kind}`);
  const limits = spec.costLimits;
  if (limits.maxTicks > vocabulary.limits.maxTicks)
    problems.push(`maxTicks above ${vocabulary.limits.maxTicks}`);
  if (limits.maxDistance > vocabulary.limits.maxDistance)
    problems.push(`maxDistance above ${vocabulary.limits.maxDistance}`);
  if (limits.minHealth > vocabulary.limits.minHealth)
    problems.push(`minHealth above ${vocabulary.limits.minHealth}`);
  return problems;
}

/**
 * A skill library, loaded from an environment's canonical JSON specs, which
 * the cognition process also reads. Generic: the mechanism is Person's, the
 * specs and their vocabulary are the environment's (ADR 0025). Nothing here
 * executes anything: this is the contract the planner reasons over and the
 * runtime enforces.
 */
export class SkillRegistry {
  readonly specs: ReadonlyMap<string, SkillSpec>;
  readonly facts: FactVocabulary;
  readonly vocabulary: SkillVocabulary;
  readonly revision: string;

  constructor(directory: string = soleEnvironment().skillsDirectory) {
    const validate = compileSpecValidator();
    this.facts = JSON.parse(
      readFileSync(path.join(directory, "facts.json"), "utf8"),
    );
    this.vocabulary = JSON.parse(
      readFileSync(path.join(directory, "vocabulary.json"), "utf8"),
    );
    for (const [name, facts] of Object.entries(this.vocabulary.factClasses))
      for (const fact of facts)
        if (!(fact in this.facts.facts))
          throw new SkillSpecError(
            `vocabulary fact class ${name} names unknown fact ${fact}`,
          );
    const specs = new Map<string, SkillSpec>();
    const digest = createHash("sha256");
    for (const file of readdirSync(directory).sort()) {
      if (!file.endsWith(".json")) continue;
      if (NOT_SPECS.has(file)) continue;
      const raw = readFileSync(path.join(directory, file), "utf8");
      const spec: SkillSpec = JSON.parse(raw);
      if (!validate(spec))
        throw new SkillSpecError(
          `${file} is not a valid SkillSpec: ${(validate.errors ?? [])
            .map((e) => `${e.instancePath} ${e.message}`)
            .join("; ")}`,
        );
      const outside = vocabularyProblems(spec, this.vocabulary);
      if (outside.length)
        throw new SkillSpecError(
          `${file} names what its environment does not allow: ${outside.join(", ")}`,
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
