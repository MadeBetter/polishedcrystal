SetTrainerBGPalettes_Far::
	; Sets trainer-specific BG tile palette assignments using lookup tables
	; Called during battle intro when trainer sprites are on screen
	; Only runs for trainer battles
	ld a, [wBattleMode]
	dec a
	ret z  ; Return if wild battle (wBattleMode=1), continue if trainer (wBattleMode=2)

	; Select palette data table based on trainer class
	ld a, [wOtherTrainerClass]
	cp LYRA1
	jr z, .use_lyra1
	cp RIVAL1
	jr z, .use_rival1
	cp RIVAL0
	jr z, .use_rival1
	cp YOUNGSTER
	jr z, .use_youngster
	; Add more trainers here: cp TRAINER_X; jr z, .use_trainer_x
	ret  ; No custom palettes for this trainer

.use_lyra1:
	ld de, .Lyra1PaletteData
	jr .apply_palettes

.use_rival1:
	ld de, .Rival1PaletteData
	jr .apply_palettes

.use_youngster:
	ld de, .YounsterPaletteData
	jr .apply_palettes

.apply_palettes:
	; Save palette data pointer before coordinate calculations clobber DE
	push de

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

	; Restore palette data pointer
	pop de

	; Apply palette data from lookup table
	; hl = destination in wAttrmap
	; de = source palette data (already loaded by dispatcher)
	ld b, 7  ; 7 rows
.row_loop:
	ld c, 7  ; 7 columns
.col_loop:
	ld a, [de]  ; Get palette number from table
	ld [hli], a  ; Write to wAttrmap and increment
	inc de
	dec c
	jr nz, .col_loop

	; Move hl to start of next row in wAttrmap
	; (skip remaining columns: SCREEN_WIDTH - 7)
	ld a, l
	add SCREEN_WIDTH - 7
	ld l, a
	ld a, h
	adc 0
	ld h, a

	dec b
	jr nz, .row_loop
	ret

.Lyra1PaletteData:
	; 7x7 palette lookup table for Lyra1 trainer sprite
	; Each byte represents the palette number for that tile position
	; Palette 1 = Enemy BG, Palette 6 = Skin (Type/Cat), Palette 5 = Clothing (Status)
	db 1, 1, 1, 1, 1, 1, 1  ; Row 0
	db 1, 1, 6, 6, 1, 1, 1  ; Row 1
	db 1, 1, 6, 6, 6, 1, 1  ; Row 2
	db 1, 6, 6, 1, 5, 5, 1  ; Row 3
	db 1, 1, 6, 6, 6, 5, 1  ; Row 4
	db 1, 1, 1, 1, 1, 1, 1  ; Row 5
	db 1, 1, 1, 1, 1, 1, 1  ; Row 6

.Rival1PaletteData:
	db 1, 1, 1, 1, 1, 1, 1  ; Row 0
	db 1, 1, 1, 6, 6, 1, 1  ; Row 1
	db 1, 6, 1, 6, 6, 1, 1  ; Row 2
	db 1, 1, 1, 1, 1, 1, 1  ; Row 3
	db 1, 1, 1, 5, 5, 1, 1  ; Row 4
	db 1, 1, 1, 5, 5, 1, 1  ; Row 5
	db 1, 1, 1, 5, 5, 1, 1  ; Row 6

.YounsterPaletteData:
	db 1, 1, 1, 1, 1, 1, 1  ; Row 0
	db 1, 1, 1, 6, 6, 1, 1  ; Row 1
	db 1, 6, 6, 6, 6, 6, 1  ; Row 2
	db 1, 6, 6, 5, 5, 6, 6  ; Row 3
	db 1, 1, 1, 5, 5, 6, 6  ; Row 4
	db 1, 1, 1, 6, 6, 1, 1  ; Row 5
	db 1, 1, 1, 1, 1, 1, 1  ; Row 6
