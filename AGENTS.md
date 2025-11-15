# Agent Development Log - Chris Back Sprite Color Layer

This document tracks modifications to the Pokémon Polished Crystal ROM hack, specifically the Chris (male player) back sprite color layer system.

## Project Overview

Pokémon Polished Crystal uses a dual-layer sprite system for the player's back sprite in battle:
- **Base layer**: Background tiles (7x7 tiles) showing the main sprite
- **Color layer**: OAM sprites (6x6 tiles) overlaying the base to add color details

This project involved adjusting individual tile positions in the color layer and fixing graphics loading issues.

## File Structure

### Key Files Modified

```
engine/battle/core.asm          - Battle system and sprite loading code
gfx/player/chris_back_color.png - Color layer graphics (48x48px, 8-bit grayscale)
gfx/player/chris_back_color.2bpp - Compiled 2bpp graphics
gfx/player/chris_back_color.2bpp.lz - Compressed graphics
```

### Graphics Pipeline

```
PNG (48x48) → 2bpp (576 bytes) → LZ compressed → VRAM bank 0 → OAM sprites
```

## Technical Details

### Tile Numbering System

The color layer consists of 36 tiles (6 rows × 6 columns), numbered 0-35:

```
Row/Col  1   2   3   4   5   6
   1     0   1   2   3   4   5
   2     6   7   8   9  10  11
   3    12  13  14  15  16  17
   4    18  19  20  21  22  23
   5    24  25  26  27  28  29
   6    30  31  32  33  34  35
```

### VRAM Layout

- Color layer loads to: **vTiles0 tile $55** (decimal 85)
- Tile 0 → VRAM $55
- Tile 15 → VRAM $64
- Tile 35 → VRAM $78

### OAM Sprite Configuration

- **OAM slots**: 12-47 (36 sprites max, but some skipped)
- **Palette**: OBP1
- **Starting position**: X=24px (3 tiles), Y=64px (8 tiles)
- **Each tile**: 8×8 pixels

## Modifications Made

### 1. Tile Position Adjustments

Individual tiles adjusted for better alignment:

| Tile | Adjustment | Code Location |
|------|-----------|---------------|
| 4    | +1px right | Line 8743 |
| 10   | +5px right | Line 8749 |
| 15   | +1px down | Line 8736 |
| 22   | +2px right | Line 8756 |
| 31-34 | -1px left | Line 8762 |

### 2. Expanded Skip List

White/transparent tiles now skipped to reduce OAM sprite count:

**Previous**: 0, 1, 6, 7, 12, 18, 19, 24, 30
**Current**: 0, 1, 5, 6, 7, 11, 12, 18, 19, 21, 23, 24, 30

This reduces sprite count from 27 to 23, helping avoid the 10-sprite-per-scanline hardware limit.

### 3. Fixed Graphics Loading

**Problem**: Tiles $64 and $65 appeared white in VRAM
**Root Cause**: Asynchronous graphics loading wasn't completing before battle started
**Solution**: Added wait loop to ensure graphics load completes

```asm
call DecompressRequest2bpp
.wait_decompress
    call DelayFrame
    ldh a, [hRequested2bpp]
    and a
    jr nz, .wait_decompress
```

### 4. VRAM Bank Selection

Explicitly set VRAM bank 0 for OAM sprite tiles:

```asm
xor a
ldh [rVBK], a  ; Select VRAM bank 0
```

## Code Implementation

### LoadChrisColorLayerSprites (engine/battle/core.asm:8907-8927)

```asm
; Load chris_back_color.png to tiles $55+ in vTiles0
ldh a, [rVBK]
push af
xor a
ldh [rVBK], a  ; Ensure VRAM bank 0

ld hl, ChrisBackpicColor
ld de, vTiles0 tile $55
lb bc, BANK("Trainer Backpics"), 6 * 6
call DecompressRequest2bpp

; Wait for decompression to complete
.wait_decompress
    call DelayFrame
    ldh a, [hRequested2bpp]
    and a
    jr nz, .wait_decompress

pop af
ldh [rVBK], a
ret
```

### Sprite Creation Loop (engine/battle/core.asm:8697-8813)

```asm
ld b, $6   ; 6 rows
ld d, 8 * 8   ; Starting Y position
.color_outer
    ld c, $6   ; 6 columns
    ld e, 3 * 8  ; Starting X position
    .color_inner
        ; Skip white tiles
        ldh a, [hMapObjectIndexBuffer]
        sub $55
        cp 0
        jp z, .skip_sprite
        ; [Additional skip checks...]

        ; Apply position adjustments
        ; [Tile-specific X/Y adjustments...]

        ; Create OAM sprite
        ld [hli], a  ; Y position
        ; [X position, tile number, attributes...]

    .skip_sprite
        ; [Loop continuation...]
```

## Hardware Constraints

### Game Boy Color Limitations

1. **10 sprites per scanline**: Maximum 10 OAM sprites can display on a single horizontal line
2. **40 total OAM sprites**: System limit (we use slots 12-47 for color layer)
3. **VRAM timing**: Graphics must load during VBlank or with LCD off
4. **2 VRAM banks**: OAM sprites must use bank 0

## Common Issues and Solutions

### Issue: Tiles appear white in VRAM viewer

**Causes**:
- Asynchronous loading not completing
- Wrong VRAM bank selected
- Graphics pipeline out of sync

**Solutions**:
- Add wait loop for `hRequested2bpp`
- Explicitly set `rVBK` to 0
- Run `make clean` to rebuild graphics

### Issue: Tiles appear scrambled

**Cause**: Incorrect WRAM bank handling during decompression

**Solution**: Use proper bank-aware functions (`Request2bppInWRA6`)

### Issue: Checksum mismatch error (007)

**Cause**: Save file from different ROM version

**Solution**: Delete `.sav` files and save states, start fresh game

### Issue: JR target out of range errors

**Cause**: Jump distance exceeds ±127 bytes

**Solution**: Replace `jr` with `jp` for longer jumps

## Build Instructions

```bash
# Clean build (regenerates all graphics)
make clean && make

# Regular build
make

# Output: polishedcrystal-3.2.1.gbc (2MB)
```

## Testing Checklist

- [ ] All 23 color layer sprites visible in battle
- [ ] No sprite flickering or disappearing
- [ ] Tiles $64 and $65 have correct data in VRAM viewer
- [ ] No crashes when battle starts
- [ ] Proper tile alignment (verify adjusted tiles)
- [ ] Compatible with existing save files (or note breaking change)

## Future Considerations

### Potential Improvements

1. **Dynamic skip detection**: Auto-detect blank tiles instead of hardcoding list
2. **Per-Pokémon adjustments**: Different tile positions for different opponent sizes
3. **Animation support**: Frame-by-frame color layer changes
4. **Palette optimization**: Use multiple OBP palettes for more colors

### Known Limitations

- Color layer limited to 36 tiles (6×6 grid)
- Cannot exceed 10 sprites on any horizontal scanline
- Adjustments must be done in 1-pixel increments
- No rotation or scaling support

## Commit History

### Latest Commit

```
Adjust Chris back sprite color layer tile positions

- Move tile 4: +1px right
- Move tile 10: +5px right
- Move tile 15: +1px down
- Move tile 22: +2px right
- Move tiles 31-34: -1px left
- Expand skipped white tiles list
- Add proper register preservation (push/pop BC, DE)
- Convert JR to JP instructions where needed
- Fix graphics loading with wait loop
- Add explicit VRAM bank 0 selection
```

## Resources

- **RGBDS Documentation**: https://rgbds.gbdev.io/
- **Game Boy Dev**: https://gbdev.io/
- **Polished Crystal Repo**: https://github.com/Rangi42/polishedcrystal
- **Pan Docs**: https://gbdev.io/pandocs/

## Authors

- AI Agent: Claude (Anthropic)
- Project Lead: MadeBetter
- Original ROM Hack: Rangi42

---

# Ball Icon Display System - Background Tile Conversion Attempt

## Objective

Attempted to convert the ball icon UI (balls.png) from OAM sprites to background tiles to free up OAM slots and allow the Chris color layer to remain visible longer during battle transitions.

## Background

The original implementation uses OAM sprites for displaying party status balls:
- **Location**: `engine/battle/trainer_huds.asm`
- **Graphics**: `gfx/battle/balls.2bpp` (4 tiles: normal, status, faint, empty)
- **OAM slots**: 6 sprites per party (player uses slots 0-23, enemy uses slots 24-47)
- **Palette**: OBJ palette 3 (yellow/orange)

## Technical Challenges Encountered

### 1. VRAM Tileset Addressing Modes

**Discovery**: The game uses $8800 tileset mode (signed addressing), not $8000 mode (unsigned).

- In $8000 mode: tile $31 → VRAM address $8310
- In $8800 mode: tile $31 → VRAM address $9310 (vTiles2 tile $31)

**Initial problem**: Loaded graphics to `vTiles0 tile $31` but game expected `vTiles2 tile $31`

**Solution attempted**: Changed load location from `vTiles0 tile $31` to `vTiles2 tile $7B`

### 2. Tile Number Conflicts

**Problem**: Player backpic uses tiles starting at $31, conflicting with ball graphics at tiles $31-$34.

**Manifestation**: Mystery vertical ball icons appeared at column 2, rows 6-9 using tiles $31-$34 from the backpic data.

**Solution attempted**: Moved ball tiles to $7B-$7E range to avoid conflict.

### 3. Palette System Complexity

**Challenge**: Multiple palette buffer systems:
- `wBGPals1`: Staging buffer for palette data
- `wBGPals2`: Display buffer (Bank 5 WRAM)
- Both buffers needed for proper display

**Initial problem**: Ball palette loaded to palette 3 got overwritten by `_CGB_BattleColors` function.

**Solution attempted**: Load ball palette into both BG palettes 2 and 3 in wBGPals2 display buffer.

### 4. Coordinate Conversion Issues

**Challenge**: Converting from OAM sprite coordinates to tilemap coordinates:

```
OAM coordinates:
- Hardware offsets: Y-16, X-8
- Pixel-based positioning

Tilemap coordinates:
- No hardware offsets
- Tile-based addressing (divide by 8)
- wTilemap buffer: 20×18 tiles
- VRAM tilemap: 32×32 tiles
```

**Initial problem**: First implementation caused text box scrambling with "random scrambled tiles that keep moving around."

**Solution attempted**: Rewrote coordinate calculation with proper offset removal and register preservation.

### 5. Memory Corruption via wBuffer1

**Critical Issue**: Used `wBuffer1` to stage ball tile data.

**Problem**: wBuffer1 is shared scratch memory used by multiple game systems:
- Text rendering
- Menu systems
- Battle animations
- Item selection

**Manifestation**:
- Blank battle menu area
- Garbage text ("eaeao...")
- Screen scrolling by itself
- Move-learning screen appearing incorrectly
- Corruption persisted even after completely disabling ball code with `ret`

**Root cause**: Even disabled code changed function addresses in the compiled ROM, affecting jump tables and relative addressing throughout the battle system.

### 6. ApplyTilemapInVBlank Timing

**Problem**: Calling `ApplyTilemapInVBlank` during ball display interfered with other screen content.

**Effect**: Battle interface elements would disappear or become scrambled.

## Implementation Attempted (REVERTED)

### Modified Files

```
engine/battle/trainer_huds.asm  - Ball display and palette loading
engine/battle/core.asm          - Removed ClearSprites calls
home/clear_sprites.asm          - (read for reference only)
```

### Code Changes Made

**1. LoadBallPaletteIntoBGPal3 (REVERTED)**

```asm
LoadBallPaletteIntoBGPal3:
; Load yellow ball palette into BG palettes 2 and 3
    ldh a, [rSVBK]
    push af
    ld a, $5 ; Bank 5 for wBGPals2
    ldh [rSVBK], a

    ; Load into palette 3 (player HP bar slot)
    ld hl, .BallPalette
    ld de, wBGPals2 palette PAL_BATTLE_BG_PLAYER_HP
    ld bc, 1 palettes
    call CopyBytes

    ; Load into palette 2 (enemy HP bar slot)
    ld hl, .BallPalette
    ld de, wBGPals2 palette PAL_BATTLE_BG_ENEMY_HP
    ld bc, 1 palettes
    call CopyBytes

    pop af
    ldh [rSVBK], a
    ld a, TRUE
    ldh [hCGBPalUpdate], a
    ret

.BallPalette:
    RGB 31, 31, 31 ; white
    RGB 31, 31, 07 ; yellow
    RGB 31, 16, 01 ; orange
    RGB 00, 00, 00 ; black
```

**2. LoadTrainerHudOAM Rewrite (REVERTED)**

Original function created OAM sprites. Attempted replacement wrote background tiles to wTilemap and wAttrmap, then called `ApplyTilemapInVBlank`.

**3. Tile Number Changes (REVERTED)**

- Changed `StageBallTilesData` to use $7B-$7E instead of $31-$34
- Changed `LoadBallIconGFX` to load to `vTiles2 tile $7B`

**4. ClearSprites Removal (REVERTED)**

Removed ClearSprites calls from `engine/battle/core.asm` to preserve color layer longer.

## Debugging Process

### Tools Used

1. **SameBoy Emulator**
   - Memory examination (`examine $address`)
   - Breakpoint and watchpoint support
   - Symbol map integration
   - VRAM tilemap/tileset viewer

2. **Debugging Commands**

```
examine $994b           ; Check tilemap tile ID
examine $D94b          ; Check attrmap palette
examine $dd18          ; Check wBGPals2 palette data
examine $86f0          ; Check VRAM tile graphics
```

3. **VRAM Viewer**

Critical for discovering $8800 vs $8000 tileset mode issue. Could toggle between modes to see where graphics actually loaded.

### Lessons Learned

1. **Always check tileset addressing mode** - Game Boy supports two modes, check which one the game uses
2. **Shared memory is dangerous** - Never use wBuffer1/scratch memory for persistent data
3. **Function address stability matters** - Even disabled code can break a ROM if it shifts function locations
4. **VRAM timing is critical** - `ApplyTilemapInVBlank` can interfere with concurrent screen updates
5. **Multiple palette buffers exist** - Check both staging and display buffers
6. **Tile number conflicts are subtle** - Graphics may load correctly but display wrong tiles

## Why We Reverted

1. **Memory corruption persisted** even with all ball code disabled via `ret`
2. **Function address changes** broke other battle system components
3. **Shared wBuffer1 memory** caused unpredictable corruption across multiple game systems
4. **Complex timing issues** with VRAM transfers difficult to debug
5. **ApplyTilemapInVBlank conflicts** with battle interface rendering

## Current Status

**All changes reverted** to original working code via:

```bash
git checkout HEAD -- engine/battle/trainer_huds.asm engine/battle/core.asm home/clear_sprites.asm
```

ROM builds successfully and runs without corruption.

## Alternative Approaches (Not Implemented)

### Option 1: Keep Original OAM Sprite Approach

**Pros**:
- Already works reliably
- No memory conflicts
- Simpler timing

**Cons**:
- Uses 12 OAM slots (6 per party)
- Conflicts with Chris color layer display

### Option 2: Dedicated Memory Allocation

**Idea**: Allocate dedicated WRAM space instead of using wBuffer1

**Challenges**:
- Requires finding or creating free WRAM space
- May still have timing issues with ApplyTilemapInVBlank
- Doesn't solve function address stability problem

### Option 3: Direct VRAM Write Without Buffering

**Idea**: Write tiles directly to VRAM during VBlank without using wTilemap buffer

**Challenges**:
- More complex VBlank handling
- Must carefully manage VRAM access timing
- Risk of LCD artifacts if timing incorrect

## Key Technical Insights

### VRAM Addressing Modes

```
$8000 mode (LCDC bit 4 = 1):
  Unsigned: tiles $00-$FF
  Tile $00 → $8000
  Tile $31 → $8310
  Tile $FF → $8FF0

$8800 mode (LCDC bit 4 = 0):
  Signed: tiles $80-$FF, then $00-$7F
  Tile $00 → $9000
  Tile $31 → $9310 (vTiles2 tile $31)
  Tile $7B → $97B0 (vTiles2 tile $7B)
```

### Palette Buffer System

```
wBGPals1 (Staging):
  - Where game code typically writes
  - 8 palettes × 4 colors × 2 bytes = 64 bytes

wBGPals2 (Display - Bank 5):
  - Copied to hardware during VBlank
  - Must match wBGPals1 for colors to appear
  - Requires WRAM bank switching (rSVBK = 5)
```

### OAM Sprite Structure

```
Each sprite: 4 bytes
  Byte 0: Y position (+ 16 offset)
  Byte 1: X position (+ 8 offset)
  Byte 2: Tile number
  Byte 3: Attributes (palette, flip, priority)
```

## Pending Tasks

1. **Fix color layer cleared during opponent slide-out** - ClearSprites still called too early
2. **Investigate alternative ball display method** - If OAM slot conflict remains an issue

## References

### VRAM Documentation
- Pan Docs: VRAM Tile Data (https://gbdev.io/pandocs/Tile_Data.html)
- Pan Docs: VRAM Tile Maps (https://gbdev.io/pandocs/Tile_Maps.html)

### Palette System
- Pan Docs: Palettes (https://gbdev.io/pandocs/Palettes.html)
- RGBDS: RGB color macro (https://rgbds.gbdev.io/docs/v0.8.0/rgbasm.5#RGB_and_RGB8)

### Assembly Programming
- RGBDS: Instruction set (https://rgbds.gbdev.io/docs/gbz80.7)
- Game Boy CPU Manual: http://marc.rawer.de/Gameboy/Docs/GBCPUman.pdf

---

Last Updated: 2025-11-14
