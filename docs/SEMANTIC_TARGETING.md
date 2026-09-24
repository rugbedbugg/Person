# Semantic targeting: a design note

Status: a direction, not an implementation. Nothing described here is built.

## The problem this anticipates

Cognition cannot name a place. A `SkillInvocation` carries a skill id and
scalar parameters, and that is deliberate: a coordinate field would be raw
movement authority wearing a different hat, and the whole trust boundary rests
on cognition being unable to say "go to x, y, z".

The consequence is that skills choose their own targets. `gather_wood` finds
the nearest permitted tree; `place_owned_chest` finds a site near home. This
works for survival, where one tree is as good as another, and it stops working
as soon as a goal is about a particular thing:

```
mine the iron seam we found yesterday
repair the east wall, not the north one
put this in the food chest, not the tool chest
```

None of those can be expressed today, and none of them should be expressed by
letting Python send coordinates.

## The direction

Targets become identifiers issued by the runtime, not coordinates chosen by
cognition:

```
targetPlaceId    a named location the runtime knows: "home", "mine_north"
targetObjectId   a specific tracked object: an owned chest, a furnace
targetRegionId   a bounded area from configuration or from exploration
```

A skill invocation would carry `targetObjectId: "storage_12_64_8"` where it
today carries nothing, and the runtime would resolve that identifier to a
position it already knows. Cognition can refer to a place; it still cannot
invent one.

The pieces that would carry this already exist in spirit:

- `PlacementLedger` already issues `storageId` values with provenance, and the
  observation already reports them. That is the first real object identifier
  in the system, and it was introduced for ownership rather than targeting.
- `Observation.home.activeHome.homeId` is the first place identifier.
- `world.protectedAreas` and `world.resourceAreas` are region identifiers in
  everything but name.

## The rules it would have to keep

1. **Identifiers are issued by the runtime.** Cognition may only use an
   identifier that appeared in an observation. An unknown identifier is a
   rejected proposal, not a coordinate lookup.
2. **Resolution stays behind the boundary.** The runtime turns an identifier
   into a position; the position never travels the other way in a form
   cognition could compose arithmetic on.
3. **Permission is checked after resolution, every time.** An identifier that
   resolved to a legal place last week resolves again now, and the protected
   area check runs against the resolved position.
4. **Identifiers are stable and provenanced.** The same chest keeps the same id
   across restarts, which is what makes evidence about it accumulate, and the
   record says who created it and when.
5. **The parameter stays a scalar string.** `targetObjectId` is a slug, so the
   existing scalar-only rule on skill parameters is unchanged and no nested
   structure enters the protocol.

## What would have to be built

A place registry in the runtime, persisted alongside the existing storage
provenance; identifier fields in the observation for each referable thing; an
optional `target*` parameter on the skills where it means something; and
resolution plus permission checking in the validator. Roughly the size of the
existing `PlacementLedger`, not a subsystem.

## Why it is not being built now

Survival does not need it. Every skill in the current library can pick its own
target correctly, and the one case where it visibly matters, choosing between
two owned chests, has exactly one chest to choose from. Building a targeting
system before there is a goal that needs one would be designing against an
imagined requirement, and the shape above is cheap to adopt later precisely
because the identifiers it depends on are already being issued.
