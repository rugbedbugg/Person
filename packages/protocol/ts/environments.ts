import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Environment profiles, discovered as data (ADR 0025).
 *
 * Person's core names no environment. Each environment ships
 * `environments/<kind>/environment.json`, naming the files that carry what it
 * owns: its observation payload schema, its configuration schema, its skill
 * library and vocabulary, and its emergency vocabulary. The core reads those
 * manifests and nothing else. The Python side reads the same files
 * (`person_protocol.environments`).
 */
export const ENVIRONMENTS_DIRECTORY = fileURLToPath(
  new URL("../../../environments/", import.meta.url),
);

export interface EnvironmentManifestDocument {
  kind: string;
  title: string;
  description: string;
  embodiments: Record<string, { description: string; implementation: string }>;
  observationPayload: { schema: string };
  config: { schema: string };
  skills: { directory: string };
  emergency: { triggers: string[]; actions: string[] };
  cognition?: { python?: string };
}

export class EnvironmentNotFound extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvironmentNotFound";
  }
}

export class EnvironmentManifest {
  readonly kind: string;
  readonly directory: string;
  readonly document: EnvironmentManifestDocument;

  constructor(directory: string, document: EnvironmentManifestDocument) {
    this.kind = document.kind;
    this.directory = directory;
    this.document = document;
  }

  get embodiments(): string[] {
    return Object.keys(this.document.embodiments).sort();
  }

  #json(relative: string): object {
    return JSON.parse(
      readFileSync(path.join(this.directory, relative), "utf8"),
    ) as object;
  }

  get payloadSchema(): object {
    return this.#json(this.document.observationPayload.schema);
  }

  get configSchema(): object {
    return this.#json(this.document.config.schema);
  }

  get skillsDirectory(): string {
    return path.join(this.directory, this.document.skills.directory);
  }

  get emergencyTriggers(): ReadonlySet<string> {
    return new Set(this.document.emergency.triggers);
  }

  get emergencyActions(): ReadonlySet<string> {
    return new Set(this.document.emergency.actions);
  }
}

let found: ReadonlyMap<string, EnvironmentManifest> | undefined;

/** Every installed environment profile, keyed by kind. */
export function discoveredEnvironments(
  root: string = process.env["PERSON_ENVIRONMENTS"] ?? ENVIRONMENTS_DIRECTORY,
): ReadonlyMap<string, EnvironmentManifest> {
  if (found && root === ENVIRONMENTS_DIRECTORY) return found;
  const manifests = new Map<string, EnvironmentManifest>();
  if (existsSync(root))
    for (const entry of readdirSync(root).sort()) {
      const file = path.join(root, entry, "environment.json");
      if (!existsSync(file)) continue;
      const document = JSON.parse(
        readFileSync(file, "utf8"),
      ) as EnvironmentManifestDocument;
      if (document.kind !== entry)
        throw new Error(
          `${file} declares kind ${document.kind} in directory ${entry}`,
        );
      manifests.set(
        document.kind,
        new EnvironmentManifest(path.dirname(file), document),
      );
    }
  if (root === ENVIRONMENTS_DIRECTORY) found = manifests;
  return manifests;
}

export function environmentManifest(kind: string): EnvironmentManifest {
  const manifest = discoveredEnvironments().get(kind);
  if (!manifest)
    throw new EnvironmentNotFound(
      `no environment profile ${JSON.stringify(kind)} is installed`,
    );
  return manifest;
}

/** The one installed environment, for defaults that need one. Refuses ambiguity. */
export function soleEnvironment(): EnvironmentManifest {
  const all = [...discoveredEnvironments().values()];
  if (all.length !== 1)
    throw new EnvironmentNotFound(
      `expected exactly one installed environment, found ${all.map((m) => m.kind).join(", ") || "none"}`,
    );
  return all[0] as EnvironmentManifest;
}
