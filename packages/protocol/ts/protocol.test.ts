import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  LineReader,
  MESSAGE_TYPES,
  MAX_FRAME_BYTES,
  PROTOCOL_VERSION,
  ProtocolError,
  ProtocolValidator,
  SCHEMA_DIRECTORY,
  decodeFrame,
  encodeFrame,
  envelope,
} from "./index.ts";

const CORPUS = fileURLToPath(
  new URL("../../../fixtures/protocol-corpus/", import.meta.url),
);
const load = (file: string): unknown => JSON.parse(readFileSync(file, "utf8"));
const validator = new ProtocolValidator();

test("every message type has a compiled schema", () => {
  assert.equal(validator.messageTypes.length, MESSAGE_TYPES.length);
  const files = readdirSync(SCHEMA_DIRECTORY).filter((f) =>
    f.endsWith(".schema.json"),
  );
  assert.equal(
    files.length,
    MESSAGE_TYPES.length + 1,
    "one schema per type plus common",
  );
});

test("valid corpus messages are accepted", () => {
  const directory = path.join(CORPUS, "valid");
  const files = readdirSync(directory).filter((f) => f.endsWith(".json"));
  assert.ok(files.length >= MESSAGE_TYPES.length);
  for (const file of files) {
    const result = validator.validate(load(path.join(directory, file)));
    assert.equal(
      result.valid,
      true,
      `${file}: ${result.diagnostics.join("; ")}`,
    );
  }
});

test("invalid corpus messages are rejected with diagnostics", () => {
  const directory = path.join(CORPUS, "invalid");
  const files = readdirSync(directory).filter((f) => f.endsWith(".json"));
  assert.ok(files.length >= 15);
  for (const file of files) {
    const result = validator.validate(load(path.join(directory, file)));
    assert.equal(result.valid, false, `${file} should have been rejected`);
    assert.ok(result.diagnostics.length > 0, `${file} produced no diagnostic`);
  }
});

test("unknown schema versions are rejected by name", () => {
  const message = load(
    path.join(CORPUS, "invalid", "unknown-protocol-version.json"),
  );
  const result = validator.validate(message);
  assert.equal(result.valid, false);
  assert.match(result.diagnostics.join(" "), /unsupported protocol version/);
});

test("SkillInvocation cannot carry a free-form command payload", () => {
  const base = load(
    path.join(CORPUS, "valid", "skill-invocation.json"),
  ) as Record<string, unknown>;
  for (const field of ["command", "chat", "script", "code", "mineflayer"]) {
    assert.equal(
      validator.validate({ ...base, [field]: "anything" }).valid,
      false,
      field,
    );
  }
  const nested = structuredClone(base) as {
    parameters: Record<string, unknown>;
  };
  nested.parameters["payload"] = { run: "rm -rf" };
  assert.equal(validator.validate(nested).valid, false);
});

test("assertValid throws a ProtocolError carrying diagnostics", () => {
  assert.throws(
    () => validator.assertValid({ protocolVersion: PROTOCOL_VERSION }),
    ProtocolError,
  );
});

test("framing round-trips and rejects malformed frames", () => {
  const message = load(path.join(CORPUS, "valid", "observation.json"));
  const line = encodeFrame(message);
  assert.ok(line.endsWith("\n"));
  const decoded = decodeFrame(line.slice(0, -1));
  assert.equal(decoded.ok, true);
  assert.deepEqual(decoded.value, message);
  assert.equal(decodeFrame("{not json").ok, false);
  assert.equal(decodeFrame("[1,2,3]").ok, false);
  assert.equal(decodeFrame("null").ok, false);
});

test("line reader splits frames and bounds its buffer", () => {
  const reader = new LineReader(64);
  assert.deepEqual(reader.push('{"a":1}\n{"b":2}\n').lines, [
    '{"a":1}',
    '{"b":2}',
  ]);
  assert.deepEqual(reader.push('{"c":').lines, []);
  assert.deepEqual(reader.push("3}\n").lines, ['{"c":3}']);
  const overflow = reader.push("x".repeat(128));
  assert.match(overflow.error ?? "", /size limit/);
  assert.equal(reader.pending, "");
});

test("oversized frames are refused at encode time", () => {
  assert.throws(
    () => encodeFrame({ blob: "x".repeat(MAX_FRAME_BYTES + 16) }),
    /frame size limit/,
  );
});

test("envelopes carry the full replay metadata set", () => {
  const meta = envelope(
    {
      personId: "ada",
      sessionId: "8f6c1c0e-3d0a-4a1e-9f3a-2b6f1d9c4e11",
      worldId: "w",
    },
    "Observation",
    17,
  );
  assert.equal(meta.protocolVersion, PROTOCOL_VERSION);
  for (const key of [
    "messageId",
    "personId",
    "sessionId",
    "worldId",
    "tick",
    "timestamp",
    "type",
  ])
    assert.ok(key in meta, key);
});
