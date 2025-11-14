BattleStart_TrainerHuds:
	ld a, $e4
	ldh [rOBP0], a
	call LoadBallIconGFX
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
	ld b, $82 ; <BALL_EMPTY>, empty slot
	jr nc, .load

	assert MON_HP == MON_STATUS + 2
	inc hl
	inc hl ; points to w(OT)PartyMon1HP
	dec b ; $81, <BALL_FAINT>, fainted
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

	dec b ; $80, <BALL_STATUS>, statused
	ld a, [hl]
	and a
	jr nz, .load
	dec b ; $7f, <BALL_NORMAL>, normal

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
	ld de, wBuffer1
	ld a, [wPlaceBallsDirection]
	ld c, a
	ld b, PARTY_LENGTH
.loop
	ld a, [de]
	ld [hl], a
	inc de

	; Move to next tilemap position
	ld a, c
	add l
	ld l, a
	adc h
	sub l
	ld h, a

	dec b
	jr nz, .loop
	pop bc
	ret

LoadBallIconGFX:
	ld de, .gfx
	ld hl, vTiles2 tile $7f
	lb bc, BANK(LoadBallIconGFX), 4
	jmp Get2bpp

.gfx
INCBIN "gfx/battle/balls.2bpp"

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
