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

Last Updated: 2025-11-12
