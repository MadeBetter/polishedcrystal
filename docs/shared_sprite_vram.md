# Shared overworld sprite graphics

The object engine keeps its 13 active structures and its original split pose
regions. NPC structures now reference graphics allocations independently of their
structure indexes. Identical resolved graphics share one allocation, even when
objects have different palettes, directions, movement phases, or scripts.

## Building and testing

This feature is on `codex/shared-overworld-sprite-vram`, based on commit
`f58d41643` of `md/port-redplusplus-johto-maps`. Its development worktree is
`/Users/Amaury/projects/polished-crystal-vram-opt`; the original checkout is unchanged.

From the feature worktree:

```sh
make -j4
```

Open `polishedcrystal-3.2.3.gbc` in a Game Boy Color emulator. The corresponding
`.sym` file exposes the allocation table and each object's sprite tile for a
VRAM/debugger inspection. Use a copy of a normal battery save to compare builds;
save states contain the old executable's RAM and are not portable between ROMs.
The feature does not change the saved object/player/Pokemon data layouts.

The compiled-ROM regression suite requires Python and PyBoy:

```sh
python -m venv /tmp/shared-vram-tests
/tmp/shared-vram-tests/bin/pip install pyboy
/tmp/shared-vram-tests/bin/python utils/test_shared_sprite_gfx.py
```

The tests run the actual SM83 routines, decompression, VRAM transfers, and OAM
renderer. They patch a CALL/return trap only in the emulator's in-memory ROM;
they do not modify the built ROM or read/write a user's save. Both immediate
LCD-off transfers and LCD-on transfers through the game's VBlank handler are
covered. PyBoy 2.7.0 was used during development.

## Allocation layout

`OBJECT_SPRITE_TILE` retains its existing encoding: bit 7 set means bank 0;
clear means bank 1. `$ff` means no allocation and is not rendered.

| Graphics allocation | Bank | Base | Alternate |
| --- | --- | --- | --- |
| Player (private) | 0 | `$00–$0b` | `$80–$8b` |
| Shared slots 0–6 | 0 | `$0c–$5f` | `$8c–$df` |
| Shared slots 7–11 | 1 | `$00–$3b` | `$40–$7b` |
| Final slot with a 15-tile sprite | 1 | `$30–$3e` | `$70–$7e` |

Ordinary allocations retain the 12-tile stride. Pokemon icons copy eight base
tiles and no alternate group. Stationary balls use a separate three-tile shared
allocation, described below. Other resources retain the existing paired-copy
behavior; their short standing-sprite assets have not been compacted. The effects area beginning at bank-0 `$60`, the `$6f–$7f`
effects, and map-name/UI graphics at `$e0+` are not available to this allocator.

## Ownership and loading

`AcquireSharedSprite` resolves the sprite to a key of four bytes:

1. Compressed graphics ROM bank.
2. Graphics pointer, low byte.
3. Graphics pointer, high byte.
4. Per-group tile count, with bit 7 indicating the special final-slot constraint.

Resolving first lets ordinary IDs, variable aliases, and matching Pokemon
species/forms share the same graphics. Palette is not part of the key. Pokemon
icon geometry is resolved independently of shiny palette selection.

Before acquiring graphics, the allocator scans the other live NPC structures
and marks their graphics slots in use. The object being rebound and temporary
effects are excluded. A matching live key is reused without decompression or a
VRAM transfer. Otherwise, an unused compatible slot is loaded and assigned.

This uses 65 bytes of transient WRAM0: 48 bytes of resource keys, 12 live-use
bytes, four request bytes, and one selected-slot byte. Nothing is inserted into
the saved Game Data or object structures. There are no persistent reference
counts, so deletion, direct structure clearing, and map-connection reassociation
cannot leak allocations. Unreferenced keys do not produce cache hits; graphics
are loaded again if all their users disappear and a new user later appears.
Stale tile bytes can remain physically visible in a VRAM viewer until reused;
they are not owned or referenced by active objects.

The player remains private because player state changes and fishing overwrite
its graphics. Temporary effects keep their existing absolute tile references.

## Restore and replacement paths

`RefreshSprites` / `ReloadSpriteIndex` detach ordinary NPC graphics before
rebuilding. Each distinct resource is restored once, including after a font,
menu, or battle has overwritten VRAM. OAM DMA is held during the rebuild, and
OAM references are regenerated without advancing object movement before the
previous DMA setting is restored.

Variable changes therefore cannot overwrite graphics still needed by an
unrelated object. `LoadSpriteAsMapObject1` also rebinds the active object through
the normal restore path; an inactive object loads its new graphics when spawned.

Berry/apricorn trees use the effects atlas without owning a shared NPC allocation.
Each object's fruit flag still selects its own fruit/picked facing. Picking one
tree does not modify the shared pixels or the other trees' state.

Big Gyarados, Alolan Exeggutor, and the sailboat retain the final bank-1 graphics
allocation. The constraint applies to the resolved resource, including aliases.
An ordinary resource may use that slot until a special resource needs it; then
its graphics and all object references are relocated together. The renderer
updates OAM, and active OAM DMA publishes the new references before the old
allocation is overwritten.

The existing physical layout still accommodates only **one distinct special
resource** at a time. Multiple objects using the same special resource share it
(the sailboat halves and window objects are examples). If a different special
resource is already live, acquisition returns carry instead of corrupting it.
A failed spawn remains unassociated and leaves its object structure free; a
failed full-refresh allocation stays hidden. Increasing simultaneous distinct
large-sprite capacity requires a separate layout change.

## Contextual effects atlas and cuttable trees

The bank-0 effects atlas contains 17 tiles at `$6f-$7f`. On every refresh,
`LoadOverworldGFX` decompresses the atlas into the existing scratch buffer and
selects tiles `$78-$79`, then uploads the entire atlas in one transfer.
The former rod slots `$7a-$7b` now contain the berry and apricorn pair:

- Maps in `data/maps/healing_machine_maps.asm` keep the healing-machine pair.
  The list covers the Pokemon Centers, Goldenrod PokeCom Center, Elm's and Ivy's
  labs, Hall of Fame, and the Battle Tower and Battle Factory nurse locations.
- All other maps replace those two scratch tiles with `gfx/overworld/trunks.png`.
  Non-healing rooms such as the upstairs Pokemon Center and Oak's lab also use
  trunks. No additional persistent RAM or VRAM is reserved.

New maps that invoke `HealMachineAnim` or `pokecenternurse` must be added to that
list. The compiled-ROM tests compare the selection against every map and discover
healing callers independently from map scripts, so missing entries fail testing.

A `SPRITE_BALL_CUT_TREE` object with `SPRITEMOVEDATA_CUTTABLE_TREE` now uses the
atlas directly: `$74-$77` for the tree and `$78` for its trunk overlay. Its five
OAM positions, relative priority, and palette selection are unchanged. It receives
encoded tile `$80` solely to select bank 0; its facing uses absolute tile IDs, so
it does not reference player graphics or own a shared allocation. Both map-object
creation and live-object refresh take this allocation-free path.

Stationary ball objects using the same sprite ID now acquire and share
`ball.png`, as described below. Decorations using other movement types retain
`ball_cut_tree.png`. Pearl rocks on Faraway Island keep their original relative
facing and allocation. Cut's animation still uses atlas `$74-$77`.

Refresh holds OAM DMA through both sprite rebinding and atlas restoration, then
restores the caller's prior setting. The atlas loader also preserves the incoming
VRAM and WRAM banks. Regression checks cover LCD-on map transitions, exact OAM
coordinates/palettes/priority, tree/ball coexistence, rock rendering in bank 1,
font/menu restoration, and delayed publication of rebuilt OAM.

## Atlas-backed berry and apricorn trees

`SPRITE_BLANK_FRUIT` with `SPRITEMOVEDATA_FRUIT` bypasses shared NPC allocation
on both spawn and refresh. Its encoded tile `$80` selects bank 0, with absolute
facing tile IDs: berry `$7a`, apricorn `$7b`, and trunk `$79`. The fruit pair
comes from the two tiles in `gfx/overworld/fruit.png`; the build checks that it
is exactly 32 bytes. The trunk is the second tile in `gfx/overworld/trunks.png`.

Fruit and picked facings retain their positions and palette rules, including
the fixed brown trunk palette. Picking removes only the fruit OAM entry;
daily regrowth restores it without changing the shared pixels. Any number of
active fruit-tree objects needs no NPC graphics block or sprite-sheet upload.
The atlas uses two more tiles than the rod-only change, returning to a single
17-tile upload. No persistent RAM is added and no per-frame lookup is needed.

Other uses of `SPRITE_BLANK_FRUIT`, including standing decorations and Silver
Cave arch-tree objects, still share and upload the original sheet. It remains
in ROM for those uses. Fruit trees must be placed on maps using the trunk pair,
not the healing-machine pair; regression checks reject fruit-tree maps that
also select healing graphics.

Tests cover twelve active fruit trees without allocations, both fruit types,
independent picking/regrowth, exact OAM coordinates and palettes, map-object
creation, menu/atlas restoration in both picked states, bank-1 decorations,
and fishing coexistence. The existing LCD-on atlas and OAM publication checks
also cover the complete atlas, including the fruit pair.

## Shared fishing-rod scratch tiles

Fishing rods use bank-0 `$65-$66` (vertical and horizontal respectively).
`LoadFishingGFX` uploads the two raw tiles on every cast, including retries,
after the script's `refreshmap`. All four fishing facings retain their existing
coordinates, palette, and flips. The atlas contains fruit in the former rod
slots; a separate 32-byte rod upload occurs when fishing starts.

These tiles overlap Fly's `$64-$6b` icon and Headbutt's `$61-$6c` graphics.
The field scripts run separately, and each reloads its graphics before use;
Fly reloads for both departure and arrival. Fishing puts the rod away before
ending its script or entering battle, so no scratch restoration is needed on
cleanup. The shock emote at `$60-$63` and weather at `$6d-$6e` do not overlap.

Regression checks cover exact uploads for all player fishing graphics,
rod OAM in all four directions, shock-emote coexistence, alternating fishing
with the Fly and both Headbutt graphics loaders, and LCD-on refresh/cast/put-away
sequences. They also verify that fishing preserves the fruit at `$7a-$7b`.
These are routine and graphics tests, rather than a complete playthrough of
the field scripts.

## Three-tile stationary balls

`SPRITE_BALL_CUT_TREE` with `SPRITEMOVEDATA_STANDING_DOWN` uses exactly the three
tiles in `gfx/sprites/ball.png`. The bottom-left OAM entry uses tile 2, and the
bottom-right entry uses the same tile with horizontal flipping. Positions,
palettes, and the lower-half relative priority are unchanged. Item balls,
key-item balls, TM/HM balls, starter balls, and the existing stationary scripted
ball objects all select this path without changes to map IDs or saved data.

All live stationary balls share a single three-tile allocation. Normally it is
bank 1 `$3c-$3e`, immediately after the ordinary twelve-tile blocks; none of those
blocks is consumed. There is no alternate-pose reservation or upload. Only 48
bytes reach VRAM, and the build rejects an asset that is not exactly three tiles.

The final large-sprite allocation overlaps that tail. When it is in use, balls
instead occupy the last three tiles of a free ordinary block. Only those three
tiles are copied; the other nine tiles and the alternate region are untouched.
This partial occupancy prevents an overlapping twelve-tile allocation and cannot
match an obsolete ordinary resource key. The current allocator does not yet pack
additional small resources into the remaining nine tiles.

If a large sprite appears after balls, their three tiles are copied to the safe
location and all ball references are repointed. Active OAM DMA publishes the new
references before the large sprite overwrites the old tail. Existing ordinary
resource relocation still works when both moves are necessary. Live object scans
handle sharing and deletion without additional persistent RAM or reference counts;
detached objects cannot produce false hits during a refresh.

The old sheet remains available for other uses, including Silver Cave arch-tree
decorations. This is a targeted three-tile resource allocation, not a general
variable-size rewrite of all NPC graphics. Tests verify exact VRAM writes in both
banks, all twelve balls sharing, mirrored OAM, map creation, menu restoration,
stale-key rejection, full-population relocation, and hardware OAM publication.

## Optimization review

The implementation follows the
[pret assembly optimization guide](https://github.com/pret/pokecrystal/wiki/Optimizing-assembly-code):

- Ownership/key lookup happens on acquisition and refresh, not in the per-frame
  rendering loop. A sharing hit performs no decompression or transfer.
- Four-byte key indexing uses two `add a` instructions; constant pointer addition
  uses the carry-aware `add LOW` / `adc HIGH` pattern without a temporary pair.
- Live tile bases are converted back to slots with a bounded subtraction loop
  instead of repeatedly calling a lookup routine for each possible slot.
- HRAM accesses use `ldh`. Short jumps and tail jumps are used where appropriate.
- Flag preservation is explicit where a returned carry reports failure or a
  conditional return must retain a preceding zero test.
- ROM/WRAM/VRAM bank switching remains within the engine's existing wrappers.

The repository's `utils/optimize.py` reports zero findings in the new allocator
and the touched loading/creation paths. Allocation bounds are asserted at build
time. This does not increase the active-object or hardware OAM limits.

## Verification scope

The regression suite covers duplicate NPCs with independent OAM frames/palettes,
all twelve distinct allocations, bank-1 alternate offsets, protected VRAM ranges,
shared-owner deletion, fruit picking, actual font overwrite/restoration, variable
rebinding, Pokemon species/forms, private player state changes, temporary effects,
map-object creation/failure, direct trainer replacement, special relocation,
hardware OAM publication, and conflicting special-resource rejection.

Development also included a normal new-game run through the intro, upstairs and
downstairs home maps, Mom's dialogue, and the outdoor map, with menu open/close.
A symbol comparison against the base build confirmed all 1,079 saved player-data
symbols and the player/Pokemon save boundaries retained their original addresses.
This is targeted regression coverage, not a full playthrough of every event.
