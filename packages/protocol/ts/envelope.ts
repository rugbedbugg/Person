import { randomUUID } from "node:crypto";
import { PROTOCOL_VERSION, type MessageType } from "./version.ts";
import type { Envelope } from "./types.ts";

export interface SessionIdentity {
  personId: string;
  sessionId: string;
  worldId: string;
}

/**
 * Builds the metadata every message carries. Keeping it in one place means a
 * replayable trace always has the same identifying fields, whichever runtime
 * produced the message.
 */
export function envelope(
  identity: SessionIdentity,
  type: MessageType,
  tick: number,
  now: () => Date = () => new Date(),
): Envelope {
  return {
    protocolVersion: PROTOCOL_VERSION,
    messageId: randomUUID(),
    personId: identity.personId,
    sessionId: identity.sessionId,
    worldId: identity.worldId,
    tick,
    timestamp: now().toISOString(),
    type,
  };
}
