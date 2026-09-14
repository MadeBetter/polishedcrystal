LoadFishingGFX:
	ldh a, [rVBK]
	push af
	xor a
	ldh [rVBK], a

	ld a, [wPlayerState]
	cp PLAYER_SURF
	ld hl, FishingGFXTable
	jr nz, .got_table
	ld hl, SurfFishingGFXTable
.got_table
	; de = [hl + [wPlayerGender] * 2]
	ld a, [wPlayerGender]
	add a
	add l
	ld l, a
	adc h
	sub l
	ld h, a
	ld a, [hli]
	ld d, [hl]
	ld e, a

	ld hl, vTiles0 tile $02
	call .LoadGFX
	ld hl, vTiles0 tile $06
	call .LoadGFX
	ld hl, vTiles0 tile $0a
	call .LoadGFX

	; Every cast (including retries) restores rods after refreshmap. Fly and
	; Headbutt are separate scripts and reload their own overlapping graphics.
	ld hl, vTiles0 tile FISHING_ROD_TILE
	ld de, FishingRodGFX
	lb bc, BANK(FishingRodGFX), 2
	call Get2bpp

	pop af
	ldh [rVBK], a
	ret

.LoadGFX:
	lb bc, BANK("Fishing Graphics"), 2
	push de
	call Get2bpp
	pop de
	ld hl, 2 tiles
	add hl, de
	ld d, h
	ld e, l
	ret

INCLUDE "data/player/fishing_gfx.asm"
