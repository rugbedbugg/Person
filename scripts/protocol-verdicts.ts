/**
 * Prints the Node validator's verdict for every message in the shared protocol
 * corpus. The Python contract test runs this and compares, so a schema change
 * that only one runtime understands fails the build.
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ProtocolValidator } from "#protocol";

const corpus =
  process.argv[2] ??
  fileURLToPath(new URL("../fixtures/protocol-corpus/", import.meta.url));
const validator = new ProtocolValidator();
const verdicts: Record<string, { valid: boolean; diagnostics: string[] }> = {};

for (const group of ["valid", "invalid"]) {
  const directory = path.join(corpus, group);
  for (const file of readdirSync(directory).sort()) {
    if (!file.endsWith(".json")) continue;
    const message: unknown = JSON.parse(
      readFileSync(path.join(directory, file), "utf8"),
    );
    verdicts[`${group}/${file}`] = validator.validate(message);
  }
}

process.stdout.write(`${JSON.stringify(verdicts, null, 2)}\n`);
