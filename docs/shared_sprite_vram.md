# Shared overworld sprite graphics

The object engine keeps its 13 active structures and its original split pose
regions, with ten shared graphics allocations (slots 0-9) plus the private player.
NPC structures reference graphics allocations independently of their structure
indexes. Identical resolved graphics share one allocation, even when
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
| Shared slots 7–9 | 1 | `$00–$23` | `$40–$63` |
| Slot 9 with a 15-tile sprite | 1 | `$18–$26` | `$58–$66` |
| Strength/stationary boulders (fixed, on demand) | 1 | `$35–$38` | None |
| Smashable rocks (fixed, on demand) | 1 | `$39–$3c` | None |
| Stationary balls (fixed, on demand) | 1 | `$3d–$3f` | None |

Ordinary allocations retain the 12-tile stride. Pokemon icons copy eight base
tiles and no alternate group. Boulders, smashable rocks, and stationary balls use compact
fixed allocations, described below. Other resources retain the existing paired-copy
behavior; their short standing-sprite assets have not been compacted. The effects area beginning at bank-0 `$60`, the `$6f–$7f`
effects, and map-name/UI graphics at `$e0+` are not available to this allocator.

The final allocation is slot 9. Big Gyarados and Alolan Exeggutor upload
15 base tiles at bank 1 `$8180` and 15 alternate tiles at `$8580`. The sailboat
uses the same slot with 12 tiles per group. Ordinary resources can still use
slot 9 until a special sprite needs it, at which point live ordinary owners
are relocated together into a free earlier allocation.

The existing Alolan Exeggutor asset contains 24 tiles, although its descriptor
requests two groups of 15. This layout change preserves that loader behavior;
six trailing alternate tiles come from decompression scratch beyond the asset.
Tests verify its valid source pixels and exact destination boundaries without
assuming contents for those six tiles. Asset/upload sizing remains separate work.

The following bank-1 ranges remain available outside all shared allocations and
the player-overlay region, even with a 15-tile special sprite present.

| Available tiles | VRAM addresses | Count |
| --- | --- | --- |
| `$27-$34` | `$8270-$834f` | 14 |
| `$67-$73` | `$8670-$873f` | 13 |

Bank-1 tiles `$74-$7f` are a fixed 12-tile player-overlay region. Every
`LoadOverworldGFX` call uploads `gfx/overlays/chris.png` there, after restoring
the bank-0 effects atlas, and restores the caller's original VRAM bank. The
current asset is raw 2bpp data in ROM because its exact 192-byte size is small
and avoids decompression scratch or persistent WRAM.

Chris's normal, running, biking, and surfing sprites use a player-only vertical
step layout. On the mirrored down/up frame, the lower body keeps the standard
horizontal flip while the two head tiles retain their unmirrored positions and
attributes. Other player characters and NPCs using Chris graphics keep the
generic facing layout.

Only the regular `SPRITE_CHRIS` state currently renders the bank-1 overlay;
running, biking, surfing, fishing, other player characters, and NPC Chris
sprites do not. The overlay uses `PAL_OW_CHRIS_OVERLAY` through the dynamic
object-palette loader, independently of the base player's palette. Hardware OBJ
palette slot 0 is permanently assigned to the current player palette, and slot
1 is permanently assigned to `PAL_OW_CHRIS_OVERLAY`; dynamic allocation cannot
replace either slot, although an exact matching palette may safely share one.
The overlay adds three OAM objects to down and side facings and two to up facings. The overlay
records are rendered after the base four objects, giving them foreground OAM
priority. If the complete overlay record does not fit, none of its objects are
written and the four-object base player remains valid.

The static mappings are `$74/$75/$76` over down `$00/$01/$02`, `$77/$78`
over up `$04/$06`, and `$79/$7a/$7b` over side `$08/$09/$0b`. Walking uses
`$74/$75/$7c` over down `$80/$81/$82`, `$77/$7d` over up `$84/$86`, and
`$7e/$7a/$7f` over side `$88/$89/$8a`. Horizontal offsets and X flips reflect
with right-facing frames; for example, `$7f` moves from x+5 over left-facing
`$8a` to x-5 over its mirrored right-facing position.

Two additional transient WRAM0 bytes remember the dynamically selected shared
tree-trunk palette slot and the current total player OAM count.
`HidePlayerSprite` therefore hides all six or seven player objects when an overlay is active, while retaining
the original four-object behavior for every other state. These bytes are outside
saved Game Data.

Ten distinct shared resources can coexist; duplicate objects share them, and
atlas trees, fixed rocks, and fixed balls consume no shared slots. A new incompatible resource
fails allocation when no slot is available, without overwriting live graphics.
The object-structure limit remains 13, including the player. Future maps and
scripts must respect the reduced resource capacity.

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

This uses 55 bytes of transient WRAM0: 40 bytes of resource keys, 10 live-use
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

Ordinary scripted dialogue closes through `CloseDialogueText`, which calls
`RestoreTextSpriteGFX`. It preserves every allocation, graphics key, and object
tile reference. Only the private player's alternate group and live bank-0 shared
alternate groups are restored, once per resource, at their existing addresses.
Bank-1 graphics, bank-0 base poses, atlas objects, fixed rocks/balls, and eight-tile
Pokemon icons are not uploaded. Unused allocation keys are ignored and gaps
are retained. The caller keeps text poses active until restoration completes.

This prevents the woman/bird flash caused by rebuilding allocations on text
close: holding OAM DMA leaves hardware OAM visible, so changing a base tile's
owner while holding DMA can briefly display another sprite. The dialogue path
avoids changing those pixels or references at all. It also avoids the separate
full player reload previously performed after every textbox.

`CloseText` remains the full restore entry point for menu and other legacy
callers. Map transitions, picture-screen cleanup, and variable-sprite changes
retain their existing `RefreshSprites` / `ReloadSpriteIndex` calls. A changed
player graphics resource detected during dialogue restoration also falls back
to `RefreshSprites`. New scripted screens that overwrite base graphics must use
one of these full restore paths; the dialogue path only repairs the font overlap.

Full refreshes detach and rebuild shared allocations, then rebuild shadow OAM.
They can change tile addresses and are not made atomic by the dialogue fix.
The existing special-slot relocation separately publishes new OAM references
before overwriting its old location. `LoadSpriteAsMapObject1` continues to rebind
an active object through the full restore path.

Dialogue restoration reuses the live-allocation scan and the loader's existing
skip-base flag. It adds no RAM and preserves the caller's sprite flags, object
index, registers, and VRAM/WRAM banks. Normal restores scan only the seven bank-0
shared slots after handling the private player.

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

Fruit and picked facings retain their positions and palette rules. Cut-tree
green now goes through the normal identity-based object palette allocator, so
all visible cut trees share one non-glowing `PAL_OW_COPY_BG_GREEN` entry. Cut
and fruit trunks make one normal `PAL_OW_COPY_BG_BROWN` request and store its
selected hardware slot in transient WRAM; every trunk OAM entry reads that same
slot. The slot is not fixed and remains available on maps without either tree
type. Picking removes only the fruit OAM entry;
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

## Four-tile Strength boulders

`SPRITE_BOULDER_ROCK` with `SPRITEMOVEDATA_STRENGTH_BOULDER` uses exactly the
four tiles in `gfx/overworld/strength_boulder.png`. Stationary/fallen boulders
using the same graphics group also select this path. Together, all 41 authored
placements share fixed bank-1 tiles `$35-$38`, consume no shared allocation,
and have no alternate-pose reservation.

The first live boulder uploads 64 bytes and later boulders reuse them. A full
refresh uploads the resource once when needed. The build rejects an asset that
is not exactly four tiles. The Pokécom information sign keeps the original
`boulder_rock.png` sheet, and Ice Path's boulders retain their distinct
`ice_boulder_fossils.png` resource.

## Four-tile smashable rocks

`SPRITE_BOULDER_ROCK` with `SPRITEMOVEDATA_SMASHABLE_ROCK` uses exactly the four
tiles in `gfx/overworld/smashable_rock.png`. Its position, palette, and lower-half
relative priority are unchanged. The Pokécom information sign retains the
original `boulder_rock.png` shared resource.
Mount Moon Square's special N64-sheet rock also retains its separate appearance.

All live ordinary smashable rocks share four fixed tiles in bank 1 `$39-$3c`.
They consume no shared graphics slot and have no alternate-pose reservation.
Only 64 bytes reach VRAM. The first live rock loads the asset; subsequent rocks
reuse it, and a full refresh loads it once when such rocks are present. The build
rejects an asset that is not exactly four tiles.

## Three-tile stationary balls

`SPRITE_BALL_CUT_TREE` with `SPRITEMOVEDATA_STANDING_DOWN` uses exactly the three
tiles in `gfx/overworld/ball.png`. The bottom-left OAM entry uses tile 2, and the
bottom-right entry uses the same tile with horizontal flipping. Positions,
palettes, and the lower-half relative priority are unchanged. Item balls,
key-item balls, TM/HM balls, starter balls, and the existing stationary scripted
ball objects all select this path without changes to map IDs or saved data.

All live stationary balls share three fixed tiles in bank 1 `$3d-$3f`.
They do not consume any of the ten shared allocations and never overlap the
special-sprite ranges. There is no alternate-pose reservation or upload. Only
48 bytes reach VRAM, and the build rejects an asset that is not exactly three tiles.

Uploads remain on demand: the first live ball loads the asset, and further balls
share it. A full refresh reloads it once if balls are present, and does not touch
these tiles when none are present. Live object scans handle sharing and deletion;
detached objects cannot produce false hits during a refresh. No new persistent
RAM or reference count is needed.

Balls never relocate, including when a special sprite appears. Their former
fallback allocation, partial-block ownership, and relocation routines have been
removed. Ordinary resource relocation out of the special slot still publishes
new OAM references before replacing the old graphics.

The old sheet remains available for other uses, including Silver Cave arch-tree
decorations. Tests verify exact fixed uploads, all twelve balls sharing, mirrored
OAM, map creation, on-demand/menu restoration, special coexistence in both spawn
orders, full shared capacity with balls, and stable hardware OAM.

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
all ten distinct allocations, capacity exhaustion, bank-1 alternate offsets,
protected VRAM ranges,
shared-owner deletion, fruit picking, actual font overwrite/restoration, variable
rebinding, Pokemon species/forms, private player state changes, temporary effects,
map-object creation/failure, direct trainer replacement, special relocation,
hardware OAM publication, and conflicting special-resource rejection.

Development also included a normal new-game run through the intro, upstairs and
downstairs home maps, Mom's dialogue, and the outdoor map, with menu open/close.
A symbol comparison against the base build confirmed all 1,079 saved player-data
symbols and the player/Pokemon save boundaries retained their original addresses.
This is targeted regression coverage, not a full playthrough of every event.

The ten-slot revision passes 48 compiled-ROM regression tests and the assembly
optimizer reports no findings. Ownership scratch shrinks from 65 to 55 bytes;
all 1,616 symbols within the saved Game Data range retain their prior addresses.
The map visibility/resource audit estimates at most nine simultaneous shared
resources in the current maps, below the ten-slot limit. This estimate is not
an exhaustive execution of every script or dynamic sprite substitution.

The dialogue revision passes 55 compiled-ROM regression tests. New checks cover
exact alternate-only writes, duplicate resources, stale keys and preserved gaps,
all player gender/state combinations, bank-1 exclusion, player-change fallback,
and the real `OpenText` / `Script_closetext` flow on a synthetic Cherrygrove map
setup. VBlank samples verify visible teacher OAM and unchanged base graphics
through two open/close cycles with out-of-order graphics allocations. Legacy
`CloseText` still exercises full reload. All 23,578 RAM symbols retain their
pre-dialogue addresses, and the assembly optimizer reports no findings.

The compact boulder revisions raise the suite to 68 tests. They check exact
four-tile transfers to bank 1 `$39-$3c`, twelve simultaneous rocks sharing one
upload, OAM tile/palette behavior, the real map-object path, coexistence with
fixed balls and special sprites, and preservation of the other boulder-sheet
uses and Mount Moon Square's N64-sheet rock.
