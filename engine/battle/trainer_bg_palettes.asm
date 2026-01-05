SetTrainerBGPalettes_Far::
	; Dispatcher function to set trainer-specific BG tile palette assignments
	; Called during battle intro when trainer sprites are on screen
	; Only runs for trainer battles
	ld a, [wBattleMode]
	dec a
	ret z  ; Return if wild battle (wBattleMode=1), continue if trainer (wBattleMode=2)

	ld a, [wOtherTrainerClass]
	cp LYRA1
	jp z, SetLyra1BGPalettes
	; Add more trainers here as needed
	ret

SetLyra1BGPalettes:
	; Set Lyra1 trainer background tile palettes
	; Special tiles: 16,17,18,22,23,25,30,31,32 use palette 06 (PAL_BATTLE_BG_TYPE_CAT)

	; Get sprite coordinates from WRAM and compute address in hl
	ld a, [wEnemyTrainerPicCoordY]
	ld b, a
	ld a, [wEnemyTrainerPicCoordX]
	ld c, a
	; hl = y * SCREEN_WIDTH
	ld hl, 0
	ld de, SCREEN_WIDTH
.MultiplyYLoop:
	ld a, b
	and a
	jr z, .MultiplyYDone
	add hl, de
	dec b
	jr .MultiplyYLoop
.MultiplyYDone:
	; hl = hl + x
	ld e, c
	ld d, 0
	add hl, de
	; hl = hl + wAttrmap
	ld de, wAttrmap
	add hl, de

	; First, set all 7×7 tiles to palette 01
	push hl
	lb bc, 7, 7
	ld a, PAL_BATTLE_BG_ENEMY
	call FillBoxWithByte
	pop hl

	; Now override specific tiles to palette 06
	ld a, PAL_BATTLE_BG_TYPE_CAT

	; Calculate addresses relative to base coordinate in hl
	push hl
	ld de, (2 * SCREEN_WIDTH) + 2
	add hl, de
	ld [hl], a ; Tile 16
	inc hl
	ld [hl], a ; Tile 17
	inc hl
	ld [hl], a ; Tile 18
	pop hl

	push hl
	ld de, (3 * SCREEN_WIDTH) + 1
	add hl, de
	ld [hl], a ; Tile 22
	inc hl
	ld [hl], a ; Tile 23
	inc hl
	inc hl
	ld [hl], a ; Tile 25
	pop hl

	push hl
	ld de, (4 * SCREEN_WIDTH) + 2
	add hl, de
	ld [hl], a ; Tile 30
	inc hl
	ld [hl], a ; Tile 31
	inc hl
	ld [hl], a ; Tile 32
	pop hl

	ret
