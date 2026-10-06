import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

/**
 * What the learner knows, measured from outside it.
 *
 * A validation run is not an experience, so nothing it does may change what
 * Person has learned. Asserting that in a comment is worth nothing; this
 * fingerprints the evidence store before and after instead, so the report can
 * be checked rather than believed.
 *
 * It reads bytes, not meaning. The evidence format belongs to the cognition
 * process, and an integrity check that understood the format would start
 * disagreeing with it the moment the format moved.
 */
export interface LearningFingerprint {
  directory: string;
  exists: boolean;
  /** Every evidence file, with its size and content hash. */
  files: { path: string; bytes: number; sha256: string }[];
  /** The highest policy revision any stored snapshot claims. */
  policyRevision: number;
  digest: string;
}

const HASHED_DIRECTORIES = ["journal", "snapshots"] as const;

function walk(root: string, base: string, into: string[]): void {
  if (!existsSync(root)) return;
  for (const entry of readdirSync(root).sort()) {
    const full = path.join(root, entry);
    if (statSync(full).isDirectory()) walk(full, base, into);
    else into.push(full);
  }
}

/** The highest policy revision recorded in any snapshot, or zero. */
function snapshotPolicyRevision(directory: string): number {
  const snapshots = path.join(directory, "snapshots");
  if (!existsSync(snapshots)) return 0;
  let highest = 0;
  for (const entry of readdirSync(snapshots).sort()) {
    if (!entry.endsWith(".json")) continue;
    try {
      const document: unknown = JSON.parse(
        readFileSync(path.join(snapshots, entry), "utf8"),
      );
      const revision = (document as { policy_revision?: unknown })
        .policy_revision;
      if (typeof revision === "number" && Number.isFinite(revision))
        highest = Math.max(highest, revision);
    } catch {
      // An unreadable snapshot is the learner's problem, not this check's. It
      // still counts as part of the fingerprint through its bytes.
    }
  }
  return highest;
}

export function learningFingerprint(directory: string): LearningFingerprint {
  const files: { path: string; bytes: number; sha256: string }[] = [];
  const found: string[] = [];
  for (const sub of HASHED_DIRECTORIES)
    walk(path.join(directory, sub), directory, found);

  for (const file of found.sort()) {
    const body = readFileSync(file);
    files.push({
      path: path.relative(directory, file),
      bytes: body.byteLength,
      sha256: createHash("sha256").update(body).digest("hex"),
    });
  }
  const digest = createHash("sha256");
  for (const file of files) digest.update(`${file.path}:${file.sha256}\n`);
  return {
    directory,
    exists: existsSync(directory),
    files,
    policyRevision: snapshotPolicyRevision(directory),
    digest: digest.digest("hex").slice(0, 32),
  };
}

export function learningChanged(
  before: LearningFingerprint,
  after: LearningFingerprint,
): boolean {
  return (
    before.digest !== after.digest ||
    before.policyRevision !== after.policyRevision ||
    before.files.length !== after.files.length
  );
}
