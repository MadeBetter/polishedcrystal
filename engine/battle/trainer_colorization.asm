DEF TRAINER_COLOR_CLASS            EQU 0
DEF TRAINER_COLOR_GFX_BANK         EQU 1
DEF TRAINER_COLOR_TILE_COUNT       EQU 2
DEF TRAINER_COLOR_GFX_POINTER      EQU 3
DEF TRAINER_COLOR_GRID_POINTER     EQU 5
DEF TRAINER_COLOR_BG_MAP_POINTER   EQU 7
DEF TRAINER_COLOR_BG2_POINTER      EQU 9
DEF TRAINER_COLOR_OAM_PALS_POINTER EQU 11
DEF TRAINER_COLOR_DESCRIPTOR_SIZE  EQU 13


GetTrainerColorDescriptor:
; Find the colorization resources for trainer class a.
; Returns carry and hl = descriptor when found; otherwise returns no carry.
	ld c, a
	ld hl, TrainerColorDescriptors
.loop
	ld a, [hl]
	cp -1
	jr z, .not_found
	cp c
	jr z, .found
	ld de, TRAINER_COLOR_DESCRIPTOR_SIZE
	add hl, de
	jr .loop

.found
	scf
	ret

.not_found
	and a
	ret


GetTrainerColorPointer:
; Read a pointer from descriptor hl at offset de.
	add hl, de
	ld a, [hli]
	ld h, [hl]
	ld l, a
	ret


LoadTrainerPalette_White_Col1_Col2_Black_Far:
; a = source bank, hl = palette (2 colors), de = destination in GBC Video WRAM
	ld b, a
	ldh a, [rWBK]
	push af
	ld a, BANK("GBC Video")
	ldh [rWBK], a

if !DEF(MONOCHROME)
	ld a, $ff ; RGB 31,31,31
	ld [de], a
	inc de
	ld [de], a
	inc de
else
	ld a, LOW(PAL_MONOCHROME_WHITE)
	ld [de], a
	inc de
	ld a, HIGH(PAL_MONOCHROME_WHITE)
	ld [de], a
	inc de
endc

	ld a, b
	ld bc, 2 * 2
	call FarCopyBytesToColorWRAM

if !DEF(MONOCHROME)
	xor a ; RGB 00, 00, 00
	ld [de], a
	inc de
	ld [de], a
	inc de
else
	ld a, LOW(PAL_MONOCHROME_BLACK)
	ld [de], a
	inc de
	ld a, HIGH(PAL_MONOCHROME_BLACK)
	ld [de], a
	inc de
endc

	pop af
	ldh [rWBK], a
	ret


SetBattlePal_EnemyBG_Far::
; Default: use enemy Pokemon palette.
	farjp SetBattlePal_Enemy


SetBattlePal2_EnemyBG_Far::
	push de
	ld a, [wOtherTrainerClass]
	call GetTrainerColorDescriptor
	jr nc, .default

	ld de, TRAINER_COLOR_BG2_POINTER
	call GetTrainerColorPointer
	ld a, BANK(TrainerColorDescriptors)
	pop de
	jp LoadTrainerPalette_White_Col1_Col2_Black_Far

.default
	pop de
	farjp SetBattlePal_Status


SetEnemyTrainerOAMPalettes_Far::
	ld a, [wOtherTrainerClass]
	call GetTrainerColorDescriptor
	jr nc, .default

	ld de, TRAINER_COLOR_OAM_PALS_POINTER
	call GetTrainerColorPointer

	ld a, BANK(TrainerColorDescriptors)
	ld de, wOBPals1 palette PAL_BATTLE_OB_ENEMY
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM

	ld a, BANK(TrainerColorDescriptors)
	ld de, wOBPals1 palette 2
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM

	ld a, BANK(TrainerColorDescriptors)
	ld de, wOBPals1 palette 6
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM

	ld a, BANK(TrainerColorDescriptors)
	ld de, wOBPals1 palette 7
	ld bc, 1 palettes
	jp FarCopyBytesToColorWRAM

.default
	; Color 1: use enemy Pokemon palette (slot 0).
	ld de, wOBPals1 palette PAL_BATTLE_OB_ENEMY
	farcall SetBattlePal_Enemy

	; Colors 2-4: use the standard gray palettes.
	ld hl, BattleObjectPals + 4 palettes
	ld a, BANK(BattleObjectPals)
	ld de, wOBPals1 palette 2
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM

	ld hl, BattleObjectPals + 5 palettes
	ld a, BANK(BattleObjectPals)
	ld de, wOBPals1 palette 6
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM

	ld hl, BattleObjectPals + 6 palettes
	ld a, BANK(BattleObjectPals)
	ld de, wOBPals1 palette 7
	ld bc, 1 palettes
	jp FarCopyBytesToColorWRAM


SetTrainerBGPalettes_Far::
; Apply the trainer's 7x7 background palette map during the battle intro.
	ld a, [wBattleMode]
	dec a
	ret z

	ld a, [wOtherTrainerClass]
	call GetTrainerColorDescriptor
	ret nc
	ld de, TRAINER_COLOR_BG_MAP_POINTER
	call GetTrainerColorPointer
	ld d, h
	ld e, l

	; Compute wAttrmap + y * SCREEN_WIDTH + x.
	ld a, [wEnemyTrainerPicCoordY]
	ld b, a
	ld a, [wEnemyTrainerPicCoordX]
	ld c, a
	ld hl, 0
	push de
	ld de, SCREEN_WIDTH
.multiply_y
	ld a, b
	and a
	jr z, .multiply_y_done
	add hl, de
	dec b
	jr .multiply_y

.multiply_y_done
	ld e, c
	ld d, 0
	add hl, de
	ld de, wAttrmap
	add hl, de
	pop de

	ld b, 7
.row_loop
	ld c, 7
.column_loop
	ld a, [de]
	ld [hli], a
	inc de
	dec c
	jr nz, .column_loop

	ld a, SCREEN_WIDTH - 7
	add l
	ld l, a
	adc h
	sub l
	ld h, a
	dec b
	jr nz, .row_loop
	ret


LoadTrainerColorSprites_Far::
; Load the color-layer graphics and create its OAM entries.
	ld a, [wBattleMode]
	dec a
	ret z

	ld a, [wTrainerClass]
	call GetTrainerColorDescriptor
	ret nc
	push hl

	ldh a, [rVBK]
	push af
	xor a
	ldh [rVBK], a

	; Read the graphics bank, tile count, and pointer from the descriptor.
	inc hl
	ld a, [hli]
	ld b, a
	ld a, [hli]
	ld c, a
	ld a, [hli]
	ld h, [hl]
	ld l, a
	ld de, vTiles0 tile $69
	call DecompressRequest2bpp

.wait_decompress
	call DelayFrame
	ldh a, [hRequested2bpp]
	and a
	jr nz, .wait_decompress

	pop af
	ldh [rVBK], a
	pop hl
	; fallthrough

CreateTrainerColorOAMFromDescriptor:
; hl = trainer color descriptor
	ld de, TRAINER_COLOR_GRID_POINTER
	call GetTrainerColorPointer
	ld de, wShadowOAM + TRAINER_COLOR_LAYER_OAM_START * OBJ_SIZE
	ld b, 7
.row_loop
	ld c, 7
.column_loop
	ld a, [hli]
	and a
	jr z, .skip_sprite

	push af ; tile ID
	ld a, [hli]
	push af ; X offset
	ld a, [hli]
	push hl ; grid pointer, now at palette
	ld l, a ; Y offset
	ld a, 7
	sub b
	add a
	add a
	add a
	add 16
	sub l
	ld [de], a
	inc de
	pop hl

	pop af ; X offset
	push hl
	ld l, a
	ld a, 7
	sub c
	add a
	add a
	add a
	add 13 * 8
	add l
	ld [de], a
	inc de
	pop hl

	pop af ; tile ID
	add $69
	ld [de], a
	inc de
	ld a, [hli]
	ld [de], a
	inc de
	jr .next_position

.skip_sprite
	inc hl
	inc hl
	inc hl

.next_position
	dec c
	jr nz, .column_loop
	dec b
	jr nz, .row_loop
	ld a, 7 * 7
	ldh [hBattleTurn], a
	ret


INCLUDE "data/trainers/colorization.asm"
