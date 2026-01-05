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
	; Enemy trainer sprite is at coordinates (12, 0), 7×7 tiles
	; Default: All tiles use BG palette 01 (PAL_BATTLE_BG_ENEMY)
	; Special tiles: 16,17,18,22,23,25,30,31,32 use palette 06 (PAL_BATTLE_BG_TYPE_CAT)

	; First, set all 7×7 tiles to palette 01
	hlcoord 12, 0, wAttrmap
	lb bc, 7, 7
	ld a, PAL_BATTLE_BG_ENEMY
	call FillBoxWithByte

	; Now override specific tiles to palette 06
	ld a, PAL_BATTLE_BG_TYPE_CAT

	; Row 2: Tiles 16, 17, 18
	ldcoord_a 14, 2, wAttrmap  ; Tile 16
	ldcoord_a 15, 2, wAttrmap  ; Tile 17
	ldcoord_a 16, 2, wAttrmap  ; Tile 18

	; Row 3: Tiles 22, 23, 25
	ldcoord_a 13, 3, wAttrmap  ; Tile 22
	ldcoord_a 14, 3, wAttrmap  ; Tile 23
	ldcoord_a 16, 3, wAttrmap  ; Tile 25

	; Row 4: Tiles 30, 31, 32
	ldcoord_a 14, 4, wAttrmap  ; Tile 30
	ldcoord_a 15, 4, wAttrmap  ; Tile 31
	ldcoord_a 16, 4, wAttrmap  ; Tile 32

	ret
