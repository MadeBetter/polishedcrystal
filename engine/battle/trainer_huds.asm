BattleStart_TrainerHuds:
	ld a, $e4
	ldh [rOBP0], a
	call LoadBallIconGFX
	call LoadBallIconPalettes
	call ShowPlayerMonsRemaining
	ld a, [wBattleMode]
	dec a
	ret z
	jr ShowOTTrainerMonsRemaining

ShowPlayerMonsRemaining:
	call DrawPlayerPartyIconHUDBorder
	ld hl, wPartyCount
	call StageBallTilesData
	; Player balls at tilemap (11, 10)
	hlcoord 11, 10
	ld a, 1
	ld [wPlaceBallsDirection], a
	jmp LoadTrainerHudOAM

EnemySwitch_TrainerHud:
	ld a, $e4
	ldh [rOBP0], a
	call LoadBallIconGFX
	call LoadEnemyBallIconPalette
	; fallthrough

ShowOTTrainerMonsRemaining:
	call DrawEnemyPartyIconHUDBorder
	ld hl, wOTPartyCount
	call StageBallTilesData
	; Enemy balls at tilemap (8, 2)
	hlcoord 8, 2
	ld a, -1
	ld [wPlaceBallsDirection], a
	jmp LoadTrainerHudOAM

StageBallTilesData:
	ld a, PARTY_LENGTH
	ld c, a
	sub [hl]
	ld b, a
	assert wPartyMon1Status - wPartyCount == wOTPartyMon1Status - wOTPartyCount
	ld de, wPartyMon1Status - wPartyCount
	add hl, de
	ld de, wBuffer1
.loop
	push bc
	ld a, b
	cp c
	ld b, $5e ; <BALL_EMPTY>, empty slot
	jr nc, .load

	assert MON_HP == MON_STATUS + 2
	inc hl
	inc hl ; points to w(OT)PartyMon1HP
	dec b ; $5d, <BALL_FAINT>, fainted
	ld a, [hli]
	and a
	jr nz, .got_hp
	ld a, [hl]
	and a
.got_hp
	dec hl ; dec rr doesn't affect flags
	dec hl
	dec hl
	jr z, .load

	dec b ; $5c, <BALL_STATUS>, statused
	ld a, [hl]
	and a
	jr nz, .load
	dec b ; $5b, <BALL_NORMAL>, normal

.load
	ld a, b
	ld [de], a
	inc de
	ld bc, PARTYMON_STRUCT_LENGTH
	add hl, bc
	pop bc
	dec c
	jr nz, .loop
	ret

DrawPlayerPartyIconHUDBorder:
	ld hl, .tiles
	ld de, wTrainerHUDTiles
	ld bc, 4
	rst CopyBytes
	hlcoord 19, 11
	ld de, -1 ; start on right
	jr PlaceHUDBorderTiles

.tiles
	db "—" ; past right
	db "—" ; right end
	db "—" ; bar
	db "◢" ; left end

DrawEnemyPartyIconHUDBorder:
	ld hl, .tiles
	ld de, wTrainerHUDTiles
	ld bc, 4
	rst CopyBytes
	hlcoord 0, 3
	ld de, 1 ; start on left
	call PlaceHUDBorderTiles
	jr DrawEnemyHUDBorder

.tiles
	db "—" ; past left
	db "—" ; left end
	db "—" ; bar
	db "◣" ; right end

DrawEnemyHUDBorder:
	ld a, [wBattleMode]
	dec a
	ret nz
	ld a, [wOTPartyMon1Species]
	ld c, a
	ld a, [wOTPartyMon1Form]
	ld b, a
	call CheckCosmeticCaughtMon
	ret z
	ld a, [wBattleType]
	cp BATTLETYPE_GHOST
	ret z
	hlcoord 1, 1
	ld [hl], '<BALL>'
	ret

PlaceHUDBorderTiles:
	ld a, [wTrainerHUDTiles]
	ld [hl], a
	ld b, $8
.loop
	add hl, de
	ld a, [wTrainerHUDTiles + 1]
	ld [hl], a
	dec b
	jr nz, .loop
	add hl, de
	ld a, [wTrainerHUDTiles + 2]
	ld [hl], a
	add hl, de
	ld a, [wTrainerHUDTiles + 3]
	ld [hl], a
	ret

LinkBattle_TrainerHuds:
	call LoadBallIconGFX
	ld hl, wPartyCount
	call StageBallTilesData
	; Player balls at tilemap (9, 6)
	hlcoord 9, 6
	ld a, 1
	ld [wPlaceBallsDirection], a
	call LoadTrainerHudOAM

	ld hl, wOTPartyCount
	call StageBallTilesData
	; Enemy balls at tilemap (9, 11)
	hlcoord 9, 11
	ld a, 1
	ld [wPlaceBallsDirection], a
	; fallthrough

LoadTrainerHudOAM:
; Write party ball icons as BG tiles to tilemap
; hl = tilemap position
; wPlaceBallsDirection = 1 (right) or -1 (left)
; wBuffer1 = 6 ball tile IDs from StageBallTilesData
	push bc
	push de
	ld de, wBuffer1
	ld a, [wPlaceBallsDirection]
	ld c, a
	ld b, PARTY_LENGTH
.loop
	; Write ball tile
	ld a, [de]
	ld [hl], a
	inc de

	; Check if this is the last ball
	dec b
	jr z, .done

	; Move to next tilemap position
	ld a, c
	cp 1
	jr z, .move_right

	; Move left (direction = -1)
	dec hl
	jr .loop

.move_right
	inc hl
	jr .loop

.done
	pop de
	pop bc
	ret

LoadBallIconGFX:
	ld de, .gfx
	ld hl, vTiles2 tile $5b
	lb bc, BANK(LoadBallIconGFX), 4
	jmp Get2bpp

.gfx
INCBIN "gfx/battle/balls.2bpp"

LoadBallIconPalettes:
; Load yellow ball palette into BG palette slots 2 and 3
; Uses the yellow palette from battle_anims.pal
	ldh a, [rSVBK]
	push af
	ld a, BANK(wBGPals2)
	ldh [rSVBK], a

	; Load into slot 2 (enemy HP bar slot)
	ld hl, BallIconPalette
	ld de, wBGPals2 palette PAL_BATTLE_BG_ENEMY_HP
	ld bc, 1 palettes
	call CopyBytes

	; Load into slot 3 (player HP bar slot)
	ld hl, BallIconPalette
	ld de, wBGPals2 palette PAL_BATTLE_BG_PLAYER_HP
	ld bc, 1 palettes
	call CopyBytes

	pop af
	ldh [rSVBK], a
	ld a, TRUE
	ldh [hCGBPalUpdate], a
	ret

LoadEnemyBallIconPalette:
; Load yellow ball palette into BG palette slot 2 only (enemy HP bar slot)
; Called once after enemy Pokemon faints to restore ball icon colors
	ldh a, [rSVBK]
	push af
	ld a, BANK(wBGPals2)
	ldh [rSVBK], a

	; Load into slot 2 (enemy HP bar slot)
	ld hl, BallIconPalette
	ld de, wBGPals2 palette PAL_BATTLE_BG_ENEMY_HP
	ld bc, 1 palettes
	call CopyBytes

	pop af
	ldh [rSVBK], a
	ld a, TRUE
	ldh [hCGBPalUpdate], a
	ret

BallIconPalette:
; Yellow palette from battle_anims.pal (OBJ palette 3)
if !DEF(MONOCHROME)
	RGB 31, 31, 31  ; white
	RGB 31, 31, 07  ; bright yellow
	RGB 31, 16, 01  ; orange
	RGB 00, 00, 00  ; black
else
	MONOCHROME_RGB_FOUR
endc

_ShowLinkBattleParticipants:
	call ClearBGPalettes
	call LoadFrame
	hlcoord 2, 3
	lb bc, 9, 14
	call Textbox
	hlcoord 4, 5
	ld de, wPlayerName
	rst PlaceString
	hlcoord 4, 10
	ld de, wOTPlayerName
	rst PlaceString
	hlcoord 9, 8
	ld a, 'V'
	ld [hli], a
	ld [hl], 'S'
	call LinkBattle_TrainerHuds
	ld a, CGB_PLAIN
	call GetCGBLayout
	call SetDefaultBGPAndOBP
	ld a, $e4
	ldh [rOBP0], a
	ret
