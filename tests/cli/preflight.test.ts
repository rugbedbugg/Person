/**
 * The operator's preflight (ADR 0018): read-only, and failing closed on
 * every condition a founding or embodiment depends on. Validation identities
 * only; nothing here founds anything.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  copyFileSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import {
  WORLD_MANIFEST,
  manifestPath,
  offlineUuid,
  preflight,
  writeWorldManifest,
  type PreflightOptions,
  type RootReport,
} from "../../apps/cli/src/preflight.ts";
import { REPOSITORY, temporaryDirectory } from "../support/harness.ts";

const USERNAME = "PersonRehearsal";

const PROPERTIES = {
  "level-name": "rehearsal-world",
  "level-seed": "8841920315",
  "white-list": "true",
  "enforce-whitelist": "true",
  gamemode: "survival",
  "force-gamemode": "true",
  difficulty: "easy",
  "spawn-monsters": "true",
  "online-mode": "false",
  "server-port": "25565",
  "server-ip": "",
};

const ABSENT: RootReport = {
  state: "absent",
  founding: null,
  persons: [],
  life: null,
  journal: { events: 0, truncated: 0, duplicates: 0 },
  lock: { pid: null, live: false },
};

const FOUNDED: RootReport = {
  state: "founded",
  founding: {
    person_id: "validation-000",
    name: "Rehearsal",
    designation: "Validation-000",
  },
  persons: ["validation-000"],
  life: { status: "alive", deaths: 0, respawns: 0 },
  journal: { events: 2, truncated: 0, duplicates: 0 },
  lock: { pid: null, live: false },
};

function writeProperties(file: string, values: Record<string, string>): void {
  writeFileSync(
    file,
    `#Minecraft server properties\n${Object.entries(values)
      .map(([key, value]) => `${key}=${value}`)
      .join("\n")}\n`,
  );
}

function configDocument(evidence: string, output: string) {
  return {
    configVersion: 3,
    personId: "validation-000",
    worldId: "rehearsal-world",
    identity: { name: "Rehearsal", designation: "Validation-000" },
    environment: { kind: "minecraft", difficulty: "normal" },
    runtime: {
      embodiment: "mineflayer",
      outputDirectory: output,
      reconnectAttempts: 3,
      reconnectIntervalMs: 5000,
    },
    learning: { mode: "off", evidenceDirectory: evidence },
    affect: { mode: "active" },
    lifecycle: { death: "respawn" },
    cognition: { command: ["uv", "run", "person-cognition"] },
    server: { host: "127.0.0.1", port: 25565, version: "1.16.1" },
    bot: { username: USERNAME, auth: "offline" },
    authorization: {
      worldOwnerApproved: true,
      dedicatedIdentity: true,
      resourceAreasAreUnowned: true,
      naturalDaylightCycle: true,
      normalDifficulty: true,
    },
    world: {
      home: { x: 0, y: 64, z: 0 },
      exploration: {
        min: { x: -64, y: 0, z: -64 },
        max: { x: 64, y: 255, z: 64 },
      },
      resourceAreas: [
        { min: { x: -64, y: 0, z: -64 }, max: { x: 64, y: 255, z: 64 } },
      ],
      protectedAreas: [],
    },
    permissions: {
      containers: {
        existing: { withdraw: false, deposit: false },
        owned: { withdraw: true, deposit: true },
      },
      hunting: {
        passiveUnnamedAnimals: true,
        namedAnimals: false,
        tamedAnimals: false,
      },
      players: { combat: false },
      villagers: { harm: false },
      building: { enabled: true },
      protectedAreas: { enforcement: "strict" },
    },
  };
}

interface Setup {
  options: PreflightOptions;
  base: string;
  server: string;
  evidence: string;
  configFile: string;
  document: ReturnType<typeof configDocument>;
  writeConfig: (document: unknown) => void;
}

/** A complete, correct setup for founding validation-000. */
function setup(): Setup {
  const base = temporaryDirectory("person-preflight-");
  const server = path.join(base, "server");
  const evidence = path.join(base, "roots", "validation-000");
  const backup = path.join(base, "backup");
  mkdirSync(server, { recursive: true });
  mkdirSync(backup);
  writeFileSync(path.join(server, "server.jar"), "a pinned server jar");
  writeProperties(path.join(server, "server.properties"), PROPERTIES);
  writeFileSync(
    path.join(server, "whitelist.json"),
    JSON.stringify([{ uuid: offlineUuid(USERNAME), name: USERNAME }]),
  );
  writeFileSync(path.join(server, "ops.json"), "[]");
  mkdirSync(path.join(server, "rehearsal-world"));
  writeFileSync(path.join(server, "rehearsal-world", "level.dat"), "nbt");
  writeWorldManifest(server, "validation rehearsal", "2026-09-30T12:00:00Z");
  const configFile = path.join(base, "validation-000.json");
  const document = configDocument(evidence, path.join(base, "runs"));
  const writeConfig = (value: unknown) =>
    writeFileSync(configFile, JSON.stringify(value));
  writeConfig(document);
  return {
    base,
    server,
    evidence,
    configFile,
    document,
    writeConfig,
    options: {
      configPath: configFile,
      operation: "found",
      serverDirectory: server,
      backupDirectory: backup,
      repository: REPOSITORY,
      minimumFreeBytes: 1,
      inspectRoot: () => ABSENT,
      resolve: async () => ["127.0.0.1"],
      git: (args) => (args[0] === "rev-parse" ? "abc123\n" : ""),
    },
  };
}

const failed = (result: Awaited<ReturnType<typeof preflight>>): string[] =>
  result.checks.filter((c) => !c.ok).map((c) => c.name);

function tree(directory: string): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (at: string): void => {
    for (const name of readdirSync(at)) {
      const full = path.join(at, name);
      const stat = statSync(full);
      if (stat.isDirectory()) walk(full);
      else out[path.relative(directory, full)] = `${stat.size}:${stat.mtimeMs}`;
    }
  };
  walk(directory);
  return out;
}

test("a complete, correct setup for a founding passes and pins what it checked", async () => {
  const { options } = setup();
  const result = await preflight(options);
  assert.deepEqual(failed(result), []);
  assert.equal(result.ok, true);
  assert.equal(result.pinned.revision, "abc123");
  assert.equal(result.pinned.personId, "validation-000");
  assert.match(result.pinned.configSha256 ?? "", /^[0-9a-f]{64}$/);
  assert.match(result.pinned.worldManifestSha256 ?? "", /^[0-9a-f]{64}$/);
});

test("the preflight changes nothing it looks at", async () => {
  const { options, base } = setup();
  const before = tree(base);
  await preflight(options);
  assert.deepEqual(tree(base), before);
});

/** Each defect, and the check that must refuse it. */
const DEFECTS: [
  string,
  string,
  (s: Setup) => Partial<PreflightOptions> | void,
][] = [
  [
    "an uncommitted change",
    "clean working tree",
    () => ({ git: (a) => (a[0] === "rev-parse" ? "abc\n" : " M x.ts\n") }),
  ],
  [
    "a death mode left to its default",
    "explicit lifecycle.death",
    (s) => {
      const { lifecycle: _gone, ...rest } = s.document;
      s.writeConfig(rest);
    },
  ],
  [
    "a reconnection budget left to its default",
    "explicit runtime.reconnectAttempts",
    (s) => {
      const { reconnectAttempts: _gone, ...runtime } = s.document.runtime;
      s.writeConfig({ ...s.document, runtime });
    },
  ],
  [
    "an affect mode left to its default",
    "explicit affect.mode",
    (s) => {
      const { affect: _gone, ...rest } = s.document;
      s.writeConfig(rest);
    },
  ],
  [
    "an ordinary identity",
    "canonical or validation identity",
    (s) =>
      s.writeConfig({
        ...s.document,
        personId: "test-person-000",
        identity: { name: "Rehearsal" },
      }),
  ],
  [
    "a designation that does not match the identity",
    "name and designation",
    (s) =>
      s.writeConfig({
        ...s.document,
        identity: { name: "Rehearsal", designation: "Person-000" },
      }),
  ],
  [
    "a root that is already founded",
    "root state",
    () => ({ inspectRoot: () => FOUNDED }),
  ],
  [
    "a root held by a running process",
    "no lock held",
    () => ({
      inspectRoot: () => ({ ...ABSENT, lock: { pid: 4242, live: true } }),
    }),
  ],
  [
    "evidence of another Person in the root",
    "no foreign evidence",
    () => ({ inspectRoot: () => ({ ...ABSENT, persons: ["ada"] }) }),
  ],
  [
    "an evidence path that already holds files",
    "empty evidence path",
    (s) => {
      mkdirSync(s.evidence, { recursive: true });
      writeFileSync(path.join(s.evidence, "notes.txt"), "x");
    },
  ],
  [
    "too little free space",
    "free space",
    () => ({ minimumFreeBytes: Number.MAX_SAFE_INTEGER }),
  ],
  [
    "a backup destination inside the root",
    "backup destination",
    (s) => {
      const inner = path.join(s.evidence, "backup");
      mkdirSync(inner, { recursive: true });
      return { backupDirectory: inner };
    },
  ],
  [
    "a missing backup destination",
    "backup destination",
    (s) => ({ backupDirectory: path.join(s.base, "nowhere") }),
  ],
  [
    "a host that resolves beyond loopback",
    "loopback target",
    () => ({ resolve: async () => ["127.0.0.1", "192.168.1.20"] }),
  ],
  [
    "a replaced server jar",
    "server jar",
    (s) => writeFileSync(path.join(s.server, "server.jar"), "another jar"),
  ],
  [
    "a different world, with no manifest",
    "world manifest",
    (s) =>
      writeProperties(path.join(s.server, "server.properties"), {
        ...PROPERTIES,
        "level-name": "someone-elses-world",
      }),
  ],
  [
    "a manifest copied into another world",
    "world named by the manifest",
    (s) => {
      const other = path.join(s.server, "someone-elses-world");
      mkdirSync(other);
      copyFileSync(manifestPath(s.server), path.join(other, WORLD_MANIFEST));
      writeProperties(path.join(s.server, "server.properties"), {
        ...PROPERTIES,
        "level-name": "someone-elses-world",
      });
    },
  ],
  [
    "a different seed",
    "seed of the manifest",
    (s) =>
      writeProperties(path.join(s.server, "server.properties"), {
        ...PROPERTIES,
        "level-seed": "1",
      }),
  ],
  [
    "the whitelist off",
    "whitelist on",
    (s) =>
      writeProperties(path.join(s.server, "server.properties"), {
        ...PROPERTIES,
        "white-list": "false",
      }),
  ],
  [
    "creative mode",
    "gamemode",
    (s) =>
      writeProperties(path.join(s.server, "server.properties"), {
        ...PROPERTIES,
        gamemode: "creative",
      }),
  ],
  [
    "Person not on the whitelist",
    "Person whitelisted",
    (s) => writeFileSync(path.join(s.server, "whitelist.json"), "[]"),
  ],
  [
    "Person an operator",
    "Person not an operator",
    (s) =>
      writeFileSync(
        path.join(s.server, "ops.json"),
        JSON.stringify([{ uuid: offlineUuid(USERNAME), name: USERNAME }]),
      ),
  ],
  [
    "Person's account already in the world",
    "Person has never entered this world",
    (s) => {
      const playerdata = path.join(s.server, "rehearsal-world", "playerdata");
      mkdirSync(playerdata, { recursive: true });
      writeFileSync(
        path.join(playerdata, `${offlineUuid(USERNAME)}.dat`),
        "nbt",
      );
    },
  ],
  [
    "a peaceful difficulty configured for an easy world",
    "configured difficulty matches the server",
    (s) =>
      s.writeConfig({
        ...s.document,
        environment: { kind: "minecraft", difficulty: "peaceful" },
        authorization: { ...s.document.authorization, normalDifficulty: false },
      }),
  ],
  [
    "an inspection that cannot run",
    "root state",
    () => ({
      inspectRoot: () => {
        throw new Error("cognition unavailable");
      },
    }),
  ],
];

for (const [defect, name, arrange] of DEFECTS)
  test(`the preflight refuses ${defect}`, async () => {
    const s = setup();
    const extra = arrange(s) ?? {};
    const result = await preflight({ ...s.options, ...extra });
    assert.equal(result.ok, false);
    assert.ok(
      failed(result).includes(name),
      `expected "${name}" to fail, failed: ${failed(result).join(", ")}`,
    );
  });

test("embodying needs a founded root of this Person, never a terminated one", async () => {
  const s = setup();
  const embody = { ...s.options, operation: "embody" as const };
  assert.deepEqual(
    failed(await preflight({ ...embody, inspectRoot: () => FOUNDED })),
    [],
  );
  assert.ok(
    failed(await preflight({ ...embody, inspectRoot: () => ABSENT })).includes(
      "root state",
    ),
  );
  assert.ok(
    failed(
      await preflight({
        ...embody,
        inspectRoot: () => ({
          ...FOUNDED,
          life: { status: "terminated", deaths: 1, respawns: 0 },
        }),
      }),
    ).includes("not terminated"),
  );
  assert.ok(
    failed(
      await preflight({
        ...embody,
        inspectRoot: () => ({
          ...FOUNDED,
          founding: { ...FOUNDED.founding!, person_id: "validation-001" },
        }),
      }),
    ).includes("root state"),
  );
});

test("the preflight reads a real root through cognition, without touching it", async () => {
  const s = setup();
  const { inspectRoot: _injected, ...options } = s.options;
  const result = await preflight(options);
  assert.deepEqual(failed(result), []);
  assert.throws(() => statSync(s.evidence), "the root was not created");
});

test("a world's manifest is written once, into a generated and pinned world", () => {
  const s = setup();
  assert.equal(
    manifestPath(s.server),
    path.join(s.server, "rehearsal-world", WORLD_MANIFEST),
  );
  const manifest = JSON.parse(readFileSync(manifestPath(s.server), "utf8"));
  assert.equal(manifest.levelName, "rehearsal-world");
  assert.equal(manifest.seed, "8841920315");
  assert.equal(manifest.spawnMonsters, true);
  assert.throws(() => writeWorldManifest(s.server, "again"), /written once/);

  const unpinned = temporaryDirectory("person-preflight-");
  writeFileSync(path.join(unpinned, "server.jar"), "jar");
  writeProperties(path.join(unpinned, "server.properties"), {
    ...PROPERTIES,
    "level-seed": "",
  });
  assert.throws(() => writeWorldManifest(unpinned, "x"), /not been generated/);
  mkdirSync(path.join(unpinned, "rehearsal-world"));
  writeFileSync(path.join(unpinned, "rehearsal-world", "level.dat"), "nbt");
  assert.throws(() => writeWorldManifest(unpinned, "x"), /level-seed/);
});
