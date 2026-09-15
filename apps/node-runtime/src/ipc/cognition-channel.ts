import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { EventEmitter } from "node:events";
import {
  COGNITION_MESSAGE_TYPES,
  LineReader,
  ProtocolValidator,
  decodeFrame,
  encodeFrame,
  protocolValidator,
  type CognitionMessage,
  type CognitionMessageType,
  type NodeMessage,
} from "#protocol";

export interface ChannelOptions {
  command: string[];
  cwd: string;
  env?: NodeJS.ProcessEnv;
  startTimeoutMs: number;
  decisionTimeoutMs: number;
  validator?: ProtocolValidator;
  onDiagnostic?: (kind: string, detail: Record<string, unknown>) => void;
}

interface Waiter {
  type: CognitionMessageType;
  resolve: (message: CognitionMessage) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

export class CognitionUnavailableError extends Error {
  readonly reason: string;
  constructor(reason: string, message?: string) {
    super(message ?? reason);
    this.name = "CognitionUnavailableError";
    this.reason = reason;
  }
}

/**
 * Owns the cognition subprocess.
 *
 * Node is the parent: if cognition dies, hangs, or starts emitting nonsense,
 * the runtime notices and keeps control of the body. A malformed frame is
 * logged and dropped, never executed, and it can never desynchronise the
 * stream because framing is newline-delimited with a hard size cap.
 */
export class CognitionChannel extends EventEmitter {
  readonly #options: ChannelOptions;
  readonly #validator: ProtocolValidator;
  readonly #reader = new LineReader();
  readonly #queue: CognitionMessage[] = [];
  readonly #waiters: Waiter[] = [];
  #child: ChildProcessWithoutNullStreams | null = null;
  #dead: CognitionUnavailableError | null = null;
  #stopping = false;
  #stderr = "";

  constructor(options: ChannelOptions) {
    super();
    this.#options = options;
    this.#validator = options.validator ?? protocolValidator();
  }

  get stderr(): string {
    return this.#stderr;
  }

  get alive(): boolean {
    return this.#child !== null && this.#dead === null;
  }

  #diagnostic(kind: string, detail: Record<string, unknown>): void {
    this.#options.onDiagnostic?.(kind, detail);
    this.emit("diagnostic", kind, detail);
  }

  start(): void {
    const [command, ...args] = this.#options.command;
    if (!command)
      throw new CognitionUnavailableError(
        "no_command",
        "No cognition command given",
      );
    const child = spawn(command, args, {
      cwd: this.#options.cwd,
      env: { ...process.env, ...this.#options.env },
      stdio: ["pipe", "pipe", "pipe"],
    });
    this.#child = child as ChildProcessWithoutNullStreams;
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => this.#ingest(chunk));
    child.stderr.on("data", (chunk: string) => {
      this.#stderr = `${this.#stderr}${chunk}`.slice(-16384);
    });
    child.on("error", (error) => this.#fail("spawn_failed", error.message));
    child.on("exit", (code, signal) =>
      this.#fail(
        "cognition_exited",
        `code=${code ?? "null"} signal=${signal ?? "null"}`,
      ),
    );
  }

  #ingest(chunk: string): void {
    const { lines, error } = this.#reader.push(chunk);
    if (error) {
      this.#diagnostic("malformed_frame", { error });
      return;
    }
    for (const line of lines) {
      const frame = decodeFrame(line);
      if (!frame.ok) {
        this.#diagnostic("malformed_frame", {
          error: frame.error,
          preview: line.slice(0, 120),
        });
        continue;
      }
      const result = this.#validator.validate(frame.value);
      if (!result.valid) {
        this.#diagnostic("invalid_message", {
          diagnostics: result.diagnostics,
        });
        continue;
      }
      const message = frame.value as CognitionMessage;
      if (
        !(COGNITION_MESSAGE_TYPES as readonly string[]).includes(message.type)
      ) {
        this.#diagnostic("unexpected_direction", { type: message.type });
        continue;
      }
      this.#deliver(message);
    }
  }

  #deliver(message: CognitionMessage): void {
    const index = this.#waiters.findIndex(
      (waiter) => waiter.type === message.type,
    );
    if (index < 0) {
      this.#queue.push(message);
      if (this.#queue.length > 64) this.#queue.shift();
      return;
    }
    const [waiter] = this.#waiters.splice(index, 1);
    if (!waiter) return;
    clearTimeout(waiter.timer);
    waiter.resolve(message);
  }

  #fail(reason: string, detail: string): void {
    if (this.#dead) return;
    if (this.#stopping) {
      // The runtime asked for this exit. It is not a failure to report.
      this.#dead = new CognitionUnavailableError(
        "stopped",
        "Cognition was stopped by the runtime",
      );
      for (const waiter of this.#waiters.splice(0)) {
        clearTimeout(waiter.timer);
        waiter.reject(this.#dead);
      }
      return;
    }
    this.#dead = new CognitionUnavailableError(reason, `${reason}: ${detail}`);
    for (const waiter of this.#waiters.splice(0)) {
      clearTimeout(waiter.timer);
      waiter.reject(this.#dead);
    }
    this.#diagnostic("cognition_unavailable", { reason, detail });
    this.emit("unavailable", this.#dead);
  }

  send(message: NodeMessage): void {
    if (this.#dead) throw this.#dead;
    const child = this.#child;
    if (!child) throw new CognitionUnavailableError("not_started");
    const validation = this.#validator.validate(message);
    if (!validation.valid)
      throw new Error(
        `Refusing to send an invalid ${message.type}: ${validation.diagnostics.join("; ")}`,
      );
    child.stdin.write(encodeFrame(message));
  }

  /** Waits for the next message of a given type, or fails closed. */
  expect(
    type: CognitionMessageType,
    timeoutMs = this.#options.decisionTimeoutMs,
  ): Promise<CognitionMessage> {
    if (this.#dead) return Promise.reject(this.#dead);
    const queued = this.#queue.findIndex((message) => message.type === type);
    if (queued >= 0) {
      const [message] = this.#queue.splice(queued, 1);
      return Promise.resolve(message as CognitionMessage);
    }
    return new Promise<CognitionMessage>((resolve, reject) => {
      const timer = setTimeout(() => {
        const index = this.#waiters.findIndex(
          (waiter) => waiter.timer === timer,
        );
        if (index >= 0) this.#waiters.splice(index, 1);
        reject(
          new CognitionUnavailableError(
            "decision_timeout",
            `No ${type} within ${timeoutMs}ms`,
          ),
        );
      }, timeoutMs);
      timer.unref?.();
      this.#waiters.push({ type, resolve, reject, timer });
    });
  }

  waitForReady(): Promise<CognitionMessage> {
    return this.expect("CognitionReady", this.#options.startTimeoutMs);
  }

  async stop(): Promise<void> {
    this.#stopping = true;
    const child = this.#child;
    this.#child = null;
    for (const waiter of this.#waiters.splice(0)) clearTimeout(waiter.timer);
    if (!child) return;
    try {
      child.stdin.end();
    } catch {
      // The pipe may already be closed if cognition exited first.
    }
    if (child.exitCode === null && child.signalCode === null) {
      child.kill("SIGTERM");
      await new Promise<void>((resolve) => {
        const timer = setTimeout(() => {
          child.kill("SIGKILL");
          resolve();
        }, 2000);
        timer.unref?.();
        child.once("exit", () => {
          clearTimeout(timer);
          resolve();
        });
      });
    }
  }
}
