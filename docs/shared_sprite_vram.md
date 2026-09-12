# Shared overworld sprite graphics

The object engine keeps its 13 active structures and its original split pose
regions. NPC structures now reference graphics allocations independently of their
structure indexes. Identical resolved graphics share one allocation, even when
objects have different palettes, directions, movement phases, or scripts.

## Building and testing

This feature is on `codex/shared-overworld-sprite-vram`, based on commit
`f58d41643` of `md/port-redplusplus-johto-maps`. Its development worktree is
`/private/tmp/polished-crystal-shared-vram`; the original checkout is unchanged.

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
tiles and no alternate group. Other resources retain the existing paired-copy
behavior; this change does not compact short standing-sprite assets or alter
their facing tables. The effects area beginning at bank-0 `$60`, the `$6f–$7f`
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

Fruit/apricorn objects share the `SPRITE_BLANK_FRUIT` resource. Each object's
fruit flag still selects its own fruit/picked facing. Picking one tree does not
modify the shared pixels or the other trees' state.

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
