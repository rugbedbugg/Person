import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import vec3Package from "vec3";
import { resolveBiome } from "#minecraft-adapter";

/**
 * Biome resolution, checked against Minecraft's own data structures.
 *
 * The first live observation reported `biome: "unknown"` standing in a loaded
 * Overworld chunk, and every test in the suite was green at the time, because
 * the Mineflayer double invented a biome name that `prismarine-block` never
 * produces. These tests use the real registry, the real chunk column and the
 * real block class, so the thing under test is the library that will be
 * running against Minecraft rather than a friendlier imitation of it.
 */
const require = createRequire(import.meta.url);
const { Vec3 } = vec3Package;
const registry = require("prismarine-registry")("1.16.1");
const ChunkColumn = require("prismarine-chunk")(registry);

const column = (biomeId: number): InstanceType<typeof ChunkColumn> => {
  const chunk = new ChunkColumn();
  chunk.setBlockStateId(
    new Vec3(1, 66, 1),
    registry.blocksByName.stone.defaultState,
  );
  chunk.loadBiomes(new Array(1024).fill(biomeId));
  return chunk;
};

test("prismarine-block really does hand back a nameless biome", () => {
  // This is the defect, pinned. prismarine-block builds its Biome class from
  // registry.version (a Version object) instead of the registry, so
  // prismarine-biome finds no biome table and returns its placeholder for
  // every id. If a future upgrade fixes this upstream, this test fails and the
  // workaround below can be reconsidered rather than silently kept forever.
  const block = column(1).getBlock(new Vec3(1, 66, 1));
  assert.equal(block.name, "stone", "the block itself resolves normally");
  assert.equal(block.biome.name, "", "the biome name is empty, not wrong");
  assert.equal(block.biome.id, 1, "the biome id is correct");
});

test("the biome is resolved from the id against the client registry", () => {
  for (const [id, expected] of [
    [1, "plains"],
    [4, "forest"],
    [2, "desert"],
  ] as const) {
    const block = column(id).getBlock(new Vec3(1, 66, 1));
    assert.equal(
      resolveBiome(registry, block),
      expected,
      `biome ${id} must resolve to ${expected}`,
    );
  }
});

test("every biome the 1.16.1 registry knows resolves to a protocol identifier", () => {
  const identifier = /^[a-z][a-z0-9_]{0,63}$/;
  const ids = Object.keys(registry.biomes).map(Number);
  assert.ok(ids.length > 50, "the registry should hold the 1.16 biome table");
  for (const id of ids) {
    const name = resolveBiome(registry, { biome: { id, name: "" } });
    assert.match(
      name,
      identifier,
      `biome ${id} (${registry.biomes[id]?.name}) must be reportable`,
    );
    assert.notEqual(name, "unknown", `biome ${id} must be resolvable`);
  }
});

test("a block whose chunk has not arrived stays explicitly unknown", () => {
  assert.equal(resolveBiome(registry, null), "unknown");
  assert.equal(resolveBiome(registry, undefined), "unknown");
});

test("an id no registry knows stays unknown rather than being guessed", () => {
  assert.equal(
    resolveBiome(registry, { biome: { id: 4242, name: "" } }),
    "unknown",
  );
  assert.equal(
    resolveBiome(registry, { biome: { id: -1, name: "" } }),
    "unknown",
  );
  assert.equal(resolveBiome(registry, { biome: {} }), "unknown");
  assert.equal(
    resolveBiome(undefined, { biome: { id: 1, name: "" } }),
    "unknown",
  );
});

test("a name the library does supply is used and namespace-stripped", () => {
  // Later Minecraft versions send a biome registry in the dimension codec, and
  // a fixed prismarine-block would name the biome itself. Both are accepted.
  assert.equal(
    resolveBiome(registry, { biome: { id: 1, name: "minecraft:snowy_taiga" } }),
    "snowy_taiga",
  );
  assert.equal(
    resolveBiome(registry, { biome: { id: 1, name: "Not An Identifier" } }),
    "plains",
    "a name the protocol cannot carry falls back to the registry lookup",
  );
});
