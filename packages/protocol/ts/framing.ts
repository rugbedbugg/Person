import { ProtocolError } from "./validator.ts";

/** Hard ceiling for a single framed message. Anything larger is rejected unread. */
export const MAX_FRAME_BYTES = 1024 * 1024;

/**
 * Newline-delimited JSON framing.
 *
 * Framing is deliberately dumb: one JSON object per line, no embedded
 * newlines, one hard size cap. A malformed frame must never be able to stall,
 * desynchronise, or crash the runtime that reads it.
 */
export function encodeFrame(message: unknown): string {
  const line = JSON.stringify(message);
  if (line === undefined)
    throw new ProtocolError("Message is not JSON serialisable");
  if (line.includes("\n"))
    throw new ProtocolError("Encoded message contains a newline");
  if (Buffer.byteLength(line, "utf8") > MAX_FRAME_BYTES)
    throw new ProtocolError("Encoded message exceeds the frame size limit");
  return `${line}\n`;
}

export interface FrameResult {
  ok: boolean;
  value?: unknown;
  error?: string;
}

export function decodeFrame(line: string): FrameResult {
  if (Buffer.byteLength(line, "utf8") > MAX_FRAME_BYTES)
    return { ok: false, error: "frame exceeds the size limit" };
  try {
    const value: unknown = JSON.parse(line);
    if (typeof value !== "object" || value === null || Array.isArray(value))
      return { ok: false, error: "frame is not a JSON object" };
    return { ok: true, value };
  } catch (error) {
    return {
      ok: false,
      error: `frame is not valid JSON: ${(error as Error).message}`,
    };
  }
}

/**
 * Incremental line splitter with a bounded buffer.
 *
 * `push` returns complete lines. When the peer sends an unterminated stream
 * larger than the frame limit the reader reports an error and drops the
 * buffer rather than growing without bound.
 */
export class LineReader {
  #buffer = "";
  readonly #limit: number;

  constructor(limit: number = MAX_FRAME_BYTES) {
    this.#limit = limit;
  }

  push(chunk: string): { lines: string[]; error?: string } {
    this.#buffer += chunk;
    const lines: string[] = [];
    let index = this.#buffer.indexOf("\n");
    while (index >= 0) {
      const line = this.#buffer.slice(0, index);
      this.#buffer = this.#buffer.slice(index + 1);
      if (line.trim().length > 0) lines.push(line);
      index = this.#buffer.indexOf("\n");
    }
    if (Buffer.byteLength(this.#buffer, "utf8") > this.#limit) {
      this.#buffer = "";
      return { lines, error: "unterminated frame exceeded the size limit" };
    }
    return { lines };
  }

  get pending(): string {
    return this.#buffer;
  }
}
