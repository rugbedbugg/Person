import { EmbodimentError } from "#node-runtime";

/**
 * Turns a failed connection into something an operator can act on.
 *
 * The first contact with a real server is the least diagnosable moment in the
 * whole system: no observation has been built, no skill has run, and the only
 * evidence is whatever the network or the server said. Collapsing all of that
 * into "failed to connect" wastes the one signal available.
 */
export interface ConnectionContext {
  host: string;
  port: number;
  version: string;
  username: string;
}

const code = (error: unknown): string =>
  String((error as { code?: unknown })?.code ?? "");

const text = (value: unknown): string =>
  typeof value === "string"
    ? value
    : (((value as { message?: unknown })?.message as string | undefined) ??
      JSON.stringify(value ?? null));

/** Classifies a socket or client error raised before the bot ever spawned. */
export function classifyConnectError(
  error: unknown,
  context: ConnectionContext,
): EmbodimentError {
  const message = text(error);
  const where = `${context.host}:${context.port}`;

  switch (code(error)) {
    case "ECONNREFUSED":
      return new EmbodimentError(
        "connection_refused",
        `Nothing is listening on ${where}`,
        "Open the world to LAN in Minecraft, then pass the port it prints with --port. The port changes every time the world is reopened.",
      );
    case "ENOTFOUND":
    case "EAI_AGAIN":
      return new EmbodimentError(
        "host_unresolved",
        `The host ${context.host} could not be resolved`,
        "Use 127.0.0.1 for a world opened to LAN on this machine.",
      );
    case "EHOSTUNREACH":
    case "ENETUNREACH":
      return new EmbodimentError(
        "host_unreachable",
        `No route to ${where}`,
        "Check that Minecraft is running on this machine and that the port is the one it displayed.",
      );
    case "ETIMEDOUT":
      return new EmbodimentError(
        "connection_timed_out",
        `The connection to ${where} timed out`,
        "The port may belong to a world that has since been closed. Reopen to LAN and use the new port.",
      );
    case "ECONNRESET":
    case "EPIPE":
      return new EmbodimentError(
        "connection_reset",
        `The server at ${where} closed the connection`,
        "This usually means the world was closed, or the server rejected the client before login finished.",
      );
    default:
      break;
  }

  if (
    /unsupported protocol|outdated|protocol version|unsupported version/i.test(
      message,
    )
  )
    return new EmbodimentError(
      "protocol_mismatch",
      `The server did not accept protocol ${context.version}: ${message}`,
      `Person speaks Minecraft Java ${context.version} only. Open a world of that exact version.`,
    );
  if (/deserialization|unknown packet|chunk/i.test(message))
    return new EmbodimentError(
      "protocol_mismatch",
      `The client could not decode what the server sent: ${message}`,
      `This is usually a version mismatch. Person speaks Minecraft Java ${context.version} only.`,
    );
  return new EmbodimentError(
    "connection_error",
    `Connecting to ${where} failed: ${message}`,
    "Check that the world is open to LAN and that the port matches the one Minecraft displayed.",
  );
}

/** Classifies a kick, which arrives as a chat component or a plain string. */
export function classifyKick(
  reason: unknown,
  context: ConnectionContext,
): EmbodimentError {
  const message = text(reason);

  if (/already (logged in|playing)|duplicate|same name/i.test(message))
    return new EmbodimentError(
      "identity_conflict",
      `The server refused a second login for ${context.username}: ${message}`,
      "Another client is already connected with that name. Close the other Person, or give this one a different bot.username.",
    );
  if (/whitelist|not white-?listed|banned|blacklist/i.test(message))
    return new EmbodimentError(
      "login_refused",
      `The server refused ${context.username}: ${message}`,
      "A world opened to LAN accepts local players; a dedicated server may need the bot name allowing.",
    );
  if (/outdated|version|protocol/i.test(message))
    return new EmbodimentError(
      "protocol_mismatch",
      `The server rejected the client version: ${message}`,
      `Person speaks Minecraft Java ${context.version} only.`,
    );
  if (/authentic|premium|online.?mode|mojang|session/i.test(message))
    return new EmbodimentError(
      "authentication_refused",
      `The server requires authentication: ${message}`,
      "Person uses an offline identity. Open a single-player world to LAN rather than joining an online-mode server.",
    );
  return new EmbodimentError(
    "server_kicked",
    `The server disconnected Person: ${message}`,
    "The message above comes from the server; it is the most direct evidence of why.",
  );
}

/** Turns the readiness gaps into a reason that says which half went wrong. */
export function classifyReadiness(
  gaps: string[],
  timeoutMs: number,
): EmbodimentError {
  const chunkGaps = gaps.filter((gap) => gap.startsWith("chunk"));
  if (chunkGaps.length === gaps.length)
    return new EmbodimentError(
      "chunk_data_unavailable",
      `The server sent no block data around Person within ${timeoutMs}ms (${gaps.join(", ")})`,
      "The spawn point may be in an unloaded area, or the server is still generating terrain. Try again, and check world.home is somewhere already explored.",
    );
  return new EmbodimentError(
    "world_not_ready",
    `The world was still incomplete after ${timeoutMs}ms: ${gaps.join(", ")}`,
    "Person spawned but the server had not finished telling it about the world. Try again; if it repeats, the server may be overloaded.",
  );
}
