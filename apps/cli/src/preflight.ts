/**
 * The operator's preflight before a founding or an embodiment (ADR 0018).
 *
 * Read-only and fail-closed: it connects to nothing, writes nothing, takes no
 * lock, and passes only when every condition is demonstrably true. A check
 * that cannot be carried out fails, rather than being skipped.
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { lookup } from "node:dns/promises";
import {
  accessSync,
  constants,
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
  statfsSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { parse as parseToml } from "smol-toml";
import { loadMinecraftConfig, type MinecraftConfig } from "#minecraft";

/** Kept inside the world directory it describes, so one server can hold several. */
export const WORLD_MANIFEST = "person-world-manifest.json";

/** Where the manifest of the world a server is set to load lives. */
export function manifestPath(serverDirectory: string): string {
  const directory = path.resolve(serverDirectory);
  const level = readProperties(path.join(directory, "server.properties")).get(
    "level-name",
  );
  if (!level) throw new Error("server.properties names no world");
  return path.join(directory, level, WORLD_MANIFEST);
}
export const MINIMUM_FREE_BYTES = 1024 ** 3;

const CANONICAL = /^person-(\d{3})$/;
const VALIDATION = /^validation-(\d{3})$/;

export type Operation = "found" | "embody";

export interface Check {
  group:
    "software" | "configuration" | "identity" | "persistence" | "minecraft";
  name: string;
  ok: boolean;
  detail: string;
}

/** What `person-cognition --inspect-root` reports (ADR 0018). */
export interface RootReport {
  state: "absent" | "founded" | "legacy";
  founding: {
    person_id: string;
    name: string;
    designation: string | null;
  } | null;
  persons: string[];
  life: { status: string; deaths: number; respawns: number } | null;
  journal: { events: number; truncated: number; duplicates: number };
  lock: { pid: number | null; live: boolean };
}

/** A world's identity, written once when it is created (ADR 0018). */
export interface WorldManifest {
  manifestVersion: 1;
  levelName: string;
  seed: string;
  jarSha256: string;
  difficulty: string;
  gamemode: string;
  spawnMonsters: boolean;
  createdAt: string;
  purpose: string;
}

export interface PreflightOptions {
  configPath: string;
  operation: Operation;
  serverDirectory: string;
  backupDirectory: string;
  repository: string;
  minimumFreeBytes?: number;
  /** Reads a root without touching it. Default: the configured cognition. */
  inspectRoot?: (evidenceDirectory: string) => RootReport;
  /** Resolves a host to its addresses. Default: the system resolver. */
  resolve?: (host: string) => Promise<string[]>;
  /** Runs git in the repository. Default: the git on PATH. */
  git?: (args: string[]) => string;
}

export interface PreflightResult {
  ok: boolean;
  operation: Operation;
  checks: Check[];
  /** What an authorization names; any change afterwards voids it. */
  pinned: {
    revision: string | null;
    personId: string | null;
    configSha256: string | null;
    worldManifestSha256: string | null;
  };
}

const sha256 = (bytes: Buffer | string): string =>
  createHash("sha256").update(bytes).digest("hex");

/** Minecraft's offline-mode UUID: a name-based UUID v3 of "OfflinePlayer:<name>". */
export function offlineUuid(username: string): string {
  const hash = createHash("md5").update(`OfflinePlayer:${username}`).digest();
  hash[6] = (hash[6]! & 0x0f) | 0x30;
  hash[8] = (hash[8]! & 0x3f) | 0x80;
  const hex = hash.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function readProperties(file: string): Map<string, string> {
  const properties = new Map<string, string>();
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    const at = line.indexOf("=");
    if (at < 0) continue;
    properties.set(line.slice(0, at).trim(), line.slice(at + 1).trim());
  }
  return properties;
}

const loopback = (address: string): boolean =>
  /^127\./.test(address) || address === "::1" || /^::ffff:127\./i.test(address);

function nearestExisting(target: string): string {
  let current = path.resolve(target);
  while (!existsSync(current)) {
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return current;
}

const inside = (child: string, parent: string): boolean => {
  const relative = path.relative(path.resolve(parent), path.resolve(child));
  return (
    relative === "" ||
    (!relative.startsWith("..") && !path.isAbsolute(relative))
  );
};

function hasPath(document: unknown, keys: string[]): boolean {
  let node = document as Record<string, unknown> | undefined;
  for (const key of keys) {
    if (!node || typeof node !== "object" || !(key in node)) return false;
    node = node[key] as Record<string, unknown>;
  }
  return true;
}

function defaultInspect(config: MinecraftConfig, repository: string) {
  return (evidenceDirectory: string): RootReport => {
    const [command, ...rest] = config.cognition.command;
    const output = execFileSync(
      command as string,
      [...rest, "--inspect-root", evidenceDirectory],
      { cwd: repository, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
    );
    return JSON.parse(output) as RootReport;
  };
}

export async function preflight(
  options: PreflightOptions,
): Promise<PreflightResult> {
  const checks: Check[] = [];
  const check = (
    group: Check["group"],
    name: string,
    ok: boolean,
    detail: string,
  ): boolean => {
    checks.push({ group, name, ok, detail });
    return ok;
  };
  const attempt = <T>(
    group: Check["group"],
    name: string,
    work: () => T,
  ): T | null => {
    try {
      return work();
    } catch (error) {
      check(
        group,
        name,
        false,
        `could not be checked: ${(error as Error).message}`,
      );
      return null;
    }
  };
  const pinned: PreflightResult["pinned"] = {
    revision: null,
    personId: null,
    configSha256: null,
    worldManifestSha256: null,
  };
  const git =
    options.git ??
    ((args: string[]) =>
      execFileSync("git", args, {
        cwd: options.repository,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      }));

  // ---------------------------------------------------------------- software
  const revision = attempt("software", "revision", () =>
    git(["rev-parse", "HEAD"]).trim(),
  );
  if (revision) {
    pinned.revision = revision;
    check("software", "revision", true, revision);
  }
  const dirty = attempt("software", "clean working tree", () =>
    git(["status", "--porcelain"]).trim(),
  );
  if (dirty !== null)
    check(
      "software",
      "clean working tree",
      dirty === "",
      dirty === ""
        ? "nothing uncommitted"
        : `uncommitted: ${dirty.split("\n").length} path(s)`,
    );
  for (const [adr, file] of [
    ["0017", "0017-identity-continuity-and-lifetime.md"],
    ["0018", "0018-first-ada-readiness-and-canonical-history.md"],
  ] as const) {
    const text = attempt("software", `ADR ${adr} accepted`, () =>
      readFileSync(
        path.join(options.repository, "docs/decisions", file),
        "utf8",
      ),
    );
    if (text !== null)
      check(
        "software",
        `ADR ${adr} accepted`,
        /^\*\*Status:\*\* Accepted/m.test(text),
        /^\*\*Status:\*\* (.*)$/m.exec(text)?.[1] ?? "no status line",
      );
  }

  // ----------------------------------------------------------- configuration
  const configText = attempt("configuration", "readable", () =>
    readFileSync(path.resolve(options.configPath)),
  );
  if (configText) pinned.configSha256 = sha256(configText);
  const config = attempt("configuration", "schema-valid", () =>
    loadMinecraftConfig(options.configPath),
  );
  if (config) check("configuration", "schema-valid", true, options.configPath);
  const raw = configText
    ? attempt("configuration", "parsed", () =>
        options.configPath.endsWith(".json")
          ? (JSON.parse(configText.toString("utf8")) as unknown)
          : parseToml(configText.toString("utf8")),
      )
    : null;
  if (raw)
    for (const keys of [
      ["affect", "mode"],
      ["learning", "mode"],
      ["lifecycle", "death"],
      ["runtime", "reconnectAttempts"],
      ["runtime", "reconnectIntervalMs"],
    ])
      check(
        "configuration",
        `explicit ${keys.join(".")}`,
        hasPath(raw, keys),
        hasPath(raw, keys)
          ? String(
              keys.reduce<unknown>(
                (node, key) => (node as Record<string, unknown>)[key],
                raw,
              ),
            )
          : "not written in the file; a default is not a decision",
      );
  if (!config) return finish();
  check(
    "configuration",
    "Minecraft embodiment",
    config.runtime.embodiment === "mineflayer",
    config.runtime.embodiment,
  );

  // ---------------------------------------------------------------- identity
  const personId = config.personId;
  pinned.personId = personId;
  const serial = CANONICAL.exec(personId) ?? VALIDATION.exec(personId);
  const expectedDesignation = CANONICAL.test(personId)
    ? `Person-${serial?.[1]}`
    : `Validation-${serial?.[1]}`;
  check(
    "identity",
    "canonical or validation identity",
    serial !== null,
    serial ? personId : `${personId} is neither person-NNN nor validation-NNN`,
  );
  check(
    "identity",
    "name and designation",
    Boolean(config.identity?.name) &&
      config.identity?.designation === expectedDesignation,
    `name ${config.identity?.name ?? "missing"}, designation ${config.identity?.designation ?? "missing"} (expected ${expectedDesignation})`,
  );
  const evidence = config.learning.evidenceDirectory;
  const inspect =
    options.inspectRoot ?? defaultInspect(config, options.repository);
  const root = attempt("identity", "root state", () => inspect(evidence));
  if (root) {
    if (options.operation === "found")
      check(
        "identity",
        "root state",
        root.state === "absent",
        root.state === "absent"
          ? `${evidence} holds no Person yet`
          : `${evidence} is already ${root.state}; founding happens once, into an empty root`,
      );
    else
      check(
        "identity",
        "root state",
        root.state === "founded" && root.founding?.person_id === personId,
        root.state === "founded"
          ? `founded as ${root.founding?.person_id}`
          : `${root.state}; only a founded root is embodied`,
      );
    if (options.operation === "embody")
      check(
        "identity",
        "not terminated",
        root.life?.status !== "terminated",
        `life ${root.life?.status ?? "unknown"}`,
      );
    check(
      "identity",
      "no foreign evidence",
      root.persons.every((person) => person === personId),
      root.persons.length ? root.persons.join(", ") : "none",
    );
    check(
      "identity",
      "no lock held",
      !root.lock.live,
      root.lock.pid === null
        ? "unlocked"
        : `lock by process ${root.lock.pid} (${root.lock.live ? "running" : "stale"})`,
    );
    check(
      "identity",
      "journal intact",
      root.journal.truncated === 0,
      `${root.journal.events} events, ${root.journal.truncated} truncated`,
    );
  }

  // ------------------------------------------------------------- persistence
  const existing = nearestExisting(evidence);
  attempt("persistence", "writable", () => {
    accessSync(existing, constants.W_OK);
    check("persistence", "writable", true, existing);
  });
  attempt("persistence", "free space", () => {
    const stats = statfsSync(existing);
    const free = Number(stats.bavail) * Number(stats.bsize);
    const needed = options.minimumFreeBytes ?? MINIMUM_FREE_BYTES;
    check(
      "persistence",
      "free space",
      free >= needed,
      `${Math.floor(free / 1024 ** 2)} MiB free, ${Math.floor(needed / 1024 ** 2)} MiB needed`,
    );
  });
  if (options.operation === "found")
    check(
      "persistence",
      "empty evidence path",
      !existsSync(evidence) || readdirSync(evidence).length === 0,
      existsSync(evidence)
        ? `${readdirSync(evidence).length} entr(ies) already in ${evidence}`
        : `${evidence} does not exist yet`,
    );
  check(
    "persistence",
    "dedicated evidence path",
    !inside(options.repository, evidence) &&
      !existsSync(path.join(path.dirname(path.resolve(evidence)), "journal")),
    "neither containing the repository nor nested inside another root",
  );
  attempt("persistence", "backup destination", () => {
    const backup = path.resolve(options.backupDirectory);
    const usable = statSync(backup).isDirectory();
    accessSync(backup, constants.W_OK);
    check(
      "persistence",
      "backup destination",
      usable && !inside(backup, evidence) && !inside(evidence, backup),
      `${backup}, outside the evidence root`,
    );
  });

  // --------------------------------------------------------------- minecraft
  const server = config.server;
  const bot = config.bot;
  if (!server || !bot) return finish();
  const addresses = await (
    options.resolve ??
    (async (host: string) =>
      (await lookup(host, { all: true })).map((entry) => entry.address))
  )(server.host).catch((error: Error) => {
    check(
      "minecraft",
      "loopback target",
      false,
      `could not resolve: ${error.message}`,
    );
    return null;
  });
  if (addresses)
    check(
      "minecraft",
      "loopback target",
      addresses.length > 0 && addresses.every(loopback),
      `${server.host} -> ${addresses.join(", ") || "nothing"}`,
    );

  const directory = path.resolve(options.serverDirectory);
  const manifestText = attempt("minecraft", "world manifest", () =>
    readFileSync(manifestPath(directory)),
  );
  if (!manifestText) return finish();
  pinned.worldManifestSha256 = sha256(manifestText);
  const manifest = JSON.parse(manifestText.toString("utf8")) as WorldManifest;
  check(
    "minecraft",
    "world manifest",
    manifest.manifestVersion === 1,
    `${manifest.levelName}, seed ${manifest.seed}, ${manifest.purpose}`,
  );
  attempt("minecraft", "server jar", () => {
    const actual = sha256(readFileSync(path.join(directory, "server.jar")));
    check(
      "minecraft",
      "server jar",
      actual === manifest.jarSha256,
      actual === manifest.jarSha256
        ? actual
        : `${actual}, manifest says ${manifest.jarSha256}`,
    );
  });
  const properties = attempt("minecraft", "server properties", () =>
    readProperties(path.join(directory, "server.properties")),
  );
  if (properties) {
    const expect = (key: string, value: string, name = key): void => {
      const actual = properties.get(key);
      check(
        "minecraft",
        name,
        actual === value,
        `${key}=${actual ?? "unset"} (expected ${value})`,
      );
    };
    expect("level-name", manifest.levelName, "world named by the manifest");
    expect("level-seed", manifest.seed, "seed of the manifest");
    expect("white-list", "true", "whitelist on");
    expect("enforce-whitelist", "true");
    expect("gamemode", "survival");
    expect("force-gamemode", "true");
    expect("difficulty", manifest.difficulty);
    expect("spawn-monsters", String(manifest.spawnMonsters));
    expect("online-mode", "false", "offline accounts");
    expect("server-port", String(server.port), "port of the configuration");
    const peaceful = manifest.difficulty === "peaceful";
    check(
      "minecraft",
      "configured difficulty matches the server",
      config.environment.difficulty === (peaceful ? "peaceful" : "normal"),
      `${config.environment.difficulty ?? "no difficulty"} on ${manifest.difficulty}`,
    );
  }
  const uuid = offlineUuid(bot.username);
  attempt("minecraft", "Person whitelisted", () => {
    const listed = JSON.parse(
      readFileSync(path.join(directory, "whitelist.json"), "utf8"),
    ) as { name?: string; uuid?: string }[];
    check(
      "minecraft",
      "Person whitelisted",
      listed.some(
        (entry) =>
          entry.name?.toLowerCase() === bot.username.toLowerCase() &&
          entry.uuid === uuid,
      ),
      `${bot.username} (${uuid})`,
    );
  });
  attempt("minecraft", "Person not an operator", () => {
    const ops = JSON.parse(
      readFileSync(path.join(directory, "ops.json"), "utf8"),
    ) as { name?: string; uuid?: string }[];
    check(
      "minecraft",
      "Person not an operator",
      !ops.some(
        (entry) =>
          entry.name?.toLowerCase() === bot.username.toLowerCase() ||
          entry.uuid === uuid,
      ),
      `${ops.length} operator(s)`,
    );
  });
  if (options.operation === "found") {
    const playerdata = path.join(directory, manifest.levelName, "playerdata");
    const entered =
      existsSync(playerdata) &&
      readdirSync(playerdata).some((file) => file.startsWith(uuid));
    check(
      "minecraft",
      "Person has never entered this world",
      !entered,
      entered
        ? `${bot.username} already has player data here`
        : "no player data",
    );
  }
  return finish();

  function finish(): PreflightResult {
    return {
      ok: checks.length > 0 && checks.every((c) => c.ok),
      operation: options.operation,
      checks,
      pinned,
    };
  }
}

export function renderPreflight(result: PreflightResult): string {
  const lines = [`person preflight (${result.operation})`];
  let group = "";
  for (const item of result.checks) {
    if (item.group !== group) lines.push(`  ${(group = item.group)}`);
    lines.push(
      `    ${item.ok ? "PASS" : "FAIL"}  ${item.name}: ${item.detail}`,
    );
  }
  lines.push(
    "",
    `  revision ${result.pinned.revision ?? "unknown"}`,
    `  personId ${result.pinned.personId ?? "unknown"}`,
    `  config sha256 ${result.pinned.configSha256 ?? "unknown"}`,
    `  world manifest sha256 ${result.pinned.worldManifestSha256 ?? "unknown"}`,
    "",
    result.ok
      ? "READY: every check passed."
      : `NOT READY: ${result.checks.filter((c) => !c.ok).length} check(s) failed.`,
  );
  return `${lines.join("\n")}\n`;
}

/**
 * Writes a world's manifest, once, from the server as it stands (ADR 0018).
 * It refuses to overwrite: a world's identity is fixed when it is made.
 */
export function writeWorldManifest(
  serverDirectory: string,
  purpose: string,
  now: string = new Date().toISOString(),
): WorldManifest {
  const directory = path.resolve(serverDirectory);
  const target = manifestPath(directory);
  if (!existsSync(path.join(path.dirname(target), "level.dat")))
    throw new Error(
      `${path.dirname(target)} has not been generated; start the server once, then stop it, before writing its manifest`,
    );
  if (existsSync(target))
    throw new Error(
      `${target} already exists; a world's manifest is written once`,
    );
  const properties = readProperties(path.join(directory, "server.properties"));
  const required = (key: string): string => {
    const value = properties.get(key);
    if (value === undefined || value === "")
      throw new Error(
        `server.properties has no ${key}; the world must be pinned`,
      );
    return value;
  };
  const manifest: WorldManifest = {
    manifestVersion: 1,
    levelName: required("level-name"),
    seed: required("level-seed"),
    jarSha256: sha256(readFileSync(path.join(directory, "server.jar"))),
    difficulty: required("difficulty"),
    gamemode: required("gamemode"),
    spawnMonsters: required("spawn-monsters") === "true",
    createdAt: now,
    purpose,
  };
  writeFileSync(target, `${JSON.stringify(manifest, null, 2)}\n`, {
    flag: "wx",
  });
  return manifest;
}
