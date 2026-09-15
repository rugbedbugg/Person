import { ConfigError } from "./load.ts";
import type { PersonConfig } from "./types.ts";

/**
 * Connection details supplied on the command line.
 *
 * Minecraft assigns a new port every time a world is opened to LAN, so the
 * port is runtime information, not configuration. These overrides apply to one
 * invocation and are never written back to the file they override.
 */
export interface ConnectionOverride {
  host?: string;
  port?: number;
}

/** Hosts a world opened to LAN on this machine can be reached on. */
export const LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "::1"] as const;

export function parsePort(value: string): number {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535)
    throw new ConfigError(
      `--port must be the number Minecraft printed when you opened the world to LAN, not ${JSON.stringify(value)}`,
    );
  return port;
}

export function parseHost(value: string): string {
  if (!(LOOPBACK_HOSTS as readonly string[]).includes(value))
    throw new ConfigError(
      `--host must be one of ${LOOPBACK_HOSTS.join(", ")} for a world opened to LAN on this machine, not ${JSON.stringify(value)}`,
    );
  return value === "localhost" ? "127.0.0.1" : value;
}

/**
 * Returns a copy of the configuration with the connection overridden.
 *
 * The original object is left alone and nothing is persisted: a changed LAN
 * port must never require editing a configuration file, and must never leave a
 * stale one behind either.
 */
export function withConnectionOverride(
  config: PersonConfig,
  override: ConnectionOverride,
): PersonConfig {
  if (override.host === undefined && override.port === undefined) return config;
  if (config.runtime.embodiment !== "minecraft")
    throw new ConfigError(
      `--host and --port only mean something when runtime.embodiment is "minecraft"; this configuration uses "${config.runtime.embodiment}"`,
    );
  if (!config.server)
    throw new ConfigError(
      "--host and --port override the [server] section, which this configuration does not have",
    );
  return {
    ...config,
    server: {
      ...config.server,
      ...(override.host === undefined ? {} : { host: override.host }),
      ...(override.port === undefined ? {} : { port: override.port }),
    },
  };
}

/** How the connection was arrived at, for reporting before Person joins. */
export function describeConnection(
  config: PersonConfig,
  override: ConnectionOverride,
): string {
  if (config.runtime.embodiment !== "minecraft")
    return `the ${config.runtime.embodiment} world (no server is contacted)`;
  if (!config.server) return "no server configured";
  const source =
    override.port === undefined
      ? "from configuration"
      : "from --port, overriding configuration";
  return `${config.server.host}:${config.server.port} (${source}), Minecraft ${config.server.version}, as ${config.bot?.username ?? "unknown"}`;
}
