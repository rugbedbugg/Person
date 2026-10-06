import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { ErrorObject, ValidateFunction } from "ajv";
import addFormatsModule from "ajv-formats";

// ajv-formats is CommonJS: its module.exports is the plugin function itself,
// which NodeNext hands back as the default import at runtime.
const addFormats = addFormatsModule as unknown as (ajv: Ajv2020) => unknown;
import {
  MESSAGE_TYPES,
  PROTOCOL_VERSION,
  SCHEMA_FILES,
  type MessageType,
} from "./version.ts";
import type { ProtocolMessage } from "./types.ts";
import {
  discoveredEnvironments,
  type EnvironmentManifest,
} from "./environments.ts";

export const SCHEMA_DIRECTORY = fileURLToPath(
  new URL("../schemas/", import.meta.url),
);

export class ProtocolError extends Error {
  readonly diagnostics: string[];
  constructor(message: string, diagnostics: string[] = []) {
    super(
      diagnostics.length ? `${message}: ${diagnostics.join("; ")}` : message,
    );
    this.name = "ProtocolError";
    this.diagnostics = diagnostics;
  }
}

export interface ValidationResult {
  valid: boolean;
  diagnostics: string[];
}

const describe = (errors: ErrorObject[] | null | undefined): string[] =>
  (errors ?? []).map(
    (error) => `${error.instancePath || "/"} ${error.message ?? "is invalid"}`,
  );

/**
 * Validates protocol messages against the canonical JSON Schema files that the
 * Python runtime also loads. Both runtimes therefore enforce one contract
 * rather than two hand-maintained approximations of it.
 */
export class ProtocolValidator {
  readonly #ajv: Ajv2020;
  readonly #byType = new Map<MessageType, ValidateFunction>();
  readonly #payloads = new Map<string, ValidateFunction>();
  readonly #triggers = new Set<string>();
  readonly #actions = new Set<string>();

  /**
   * The core contract, plus the payload and vocabulary of each environment
   * profile (ADR 0025). An Observation's envelope is checked against the core
   * schema and its payload against the schema of the environment its
   * `experience` names; an environment that is not installed cannot be
   * observed in.
   */
  constructor(
    schemaDirectory: string = SCHEMA_DIRECTORY,
    environments: Iterable<EnvironmentManifest> = discoveredEnvironments().values(),
  ) {
    this.#ajv = new Ajv2020({
      strict: true,
      allErrors: true,
      allowUnionTypes: true,
    });
    addFormats(this.#ajv);
    for (const file of readdirSync(schemaDirectory).sort()) {
      if (!file.endsWith(".schema.json")) continue;
      const schema = JSON.parse(
        readFileSync(path.join(schemaDirectory, file), "utf8"),
      ) as object;
      this.#ajv.addSchema(schema, file);
    }
    for (const type of MESSAGE_TYPES) {
      const compiled = this.#ajv.getSchema(SCHEMA_FILES[type]);
      if (!compiled)
        throw new ProtocolError(`Missing schema for message type ${type}`);
      this.#byType.set(type, compiled);
    }
    for (const manifest of environments) {
      this.#payloads.set(
        manifest.kind,
        this.#ajv.compile(manifest.payloadSchema),
      );
      for (const trigger of manifest.emergencyTriggers)
        this.#triggers.add(trigger);
      for (const action of manifest.emergencyActions) this.#actions.add(action);
    }
  }

  #environmentDiagnostics(
    type: string,
    record: Record<string, unknown>,
  ): string[] {
    if (type === "Observation") {
      const experience = record["experience"] as { environmentKind: string };
      const payload = this.#payloads.get(experience.environmentKind);
      if (!payload)
        return [
          `/experience/environmentKind no installed environment ${JSON.stringify(experience.environmentKind)}`,
        ];
      return payload(record["payload"])
        ? []
        : describe(payload.errors).map((line) => `/payload${line}`);
    }
    if (type === "EmergencyEvent") {
      const problems: string[] = [];
      if (!this.#triggers.has(String(record["trigger"])))
        problems.push(
          `/trigger ${JSON.stringify(record["trigger"])} is not an emergency`,
        );
      if (!this.#actions.has(String(record["action"])))
        problems.push(
          `/action ${JSON.stringify(record["action"])} is not an emergency`,
        );
      return problems;
    }
    return [];
  }

  /** Message types this validator knows about, in a stable order. */
  get messageTypes(): readonly MessageType[] {
    return MESSAGE_TYPES;
  }

  validate(message: unknown): ValidationResult {
    if (
      typeof message !== "object" ||
      message === null ||
      Array.isArray(message)
    )
      return { valid: false, diagnostics: ["/ message must be a JSON object"] };
    const record = message as Record<string, unknown>;
    if (record["protocolVersion"] !== PROTOCOL_VERSION)
      return {
        valid: false,
        diagnostics: [
          `/protocolVersion unsupported protocol version ${JSON.stringify(
            record["protocolVersion"],
          )}; this runtime speaks ${PROTOCOL_VERSION}`,
        ],
      };
    const type = record["type"];
    if (typeof type !== "string" || !this.#byType.has(type as MessageType))
      return {
        valid: false,
        diagnostics: [`/type unknown message type ${JSON.stringify(type)}`],
      };
    const check = this.#byType.get(type as MessageType) as ValidateFunction;
    if (!check(message))
      return { valid: false, diagnostics: describe(check.errors) };
    const diagnostics = this.#environmentDiagnostics(type, record);
    return { valid: diagnostics.length === 0, diagnostics };
  }

  assertValid<T extends ProtocolMessage>(message: unknown): T {
    const result = this.validate(message);
    if (!result.valid)
      throw new ProtocolError("Invalid protocol message", result.diagnostics);
    return message as T;
  }
}

let shared: ProtocolValidator | undefined;

/** Process-wide validator. Compiling the schema set once is measurably cheaper. */
export function protocolValidator(): ProtocolValidator {
  shared ??= new ProtocolValidator();
  return shared;
}
