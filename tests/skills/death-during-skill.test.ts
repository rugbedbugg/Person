/**
 * A skill whose body dies is a death, however the skill itself ended (ADR
 * 0017). Found in the E3 live rehearsal: a flee on a body a skeleton had
 * killed ended as an ordinary failure, so the death went unreported.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { EmbodimentError } from "#node-runtime";
import { harness } from "../support/harness.ts";

test("a move that fails because the body died ends the skill as DEATH, not FAILED", async () => {
  const h = await harness({ home: { x: 6, y: 64, z: 0 } });
  h.world.moveTo = async () => {
    h.world.setVitals({ health: 0 });
    throw new EmbodimentError("no_route", "the pathfinder gave up");
  };
  const result = await h.run("return_home");
  assert.equal(result.status, "DEATH");
});

test("a move that fails on a living body is still an ordinary failure", async () => {
  const h = await harness({ home: { x: 6, y: 64, z: 0 } });
  h.world.moveTo = async () => {
    throw new EmbodimentError("no_route", "the pathfinder gave up");
  };
  const result = await h.run("return_home");
  assert.notEqual(result.status, "DEATH");
});
