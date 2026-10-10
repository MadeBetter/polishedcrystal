BlindingFlash::
	call FadeOutPalettes
	ld hl, wStatusFlags
	set 2, [hl] ; Flash
	call ReplaceTimeOfDayPals
	call UpdateTimeOfDayPal
	ld a, CGB_MAPPALS
	call GetCGBLayout
	farcall LoadBlindingFlashPalette
	jmp FadeInPalettes_EnableDynNoApply

ShakeHeadbuttTree:
; AutoHeadbuttScript has reanchored the map: wTilemap/wAttrmap are fresh,
; the BG origin is (0,0), and text/map-name popup updates are suspended.
; Only the RedPlusPlus tree artwork is supported. Other trees still run
; the unchanged encounter/item scripts, without a visual animation.
	call FindHeadbuttTree
	ret nc
	ld a, l
	ld [wHeadbuttTilemapPointer], a
	ld a, h
	ld [wHeadbuttTilemapPointer + 1], a
	; b,c are the replacement band's screen y,x (in 8x8 tiles).
	ld l, b
	ld h, 0
rept 5
	add hl, hl
endr
	ld b, 0
	add hl, bc
	ld bc, vBGMap0
	add hl, bc
	ld a, l
	ld [wHeadbuttBGMapPointer], a
	ld a, h
	ld [wHeadbuttBGMapPointer + 1], a

.wait_upload
	ldh a, [hBGMapUpdate]
	and a
	jr z, .ready
	call DelayFrame
	jr .wait_upload
.ready
	ld a, [wWeatherFlags]
	push af
	ld hl, wWeatherFlags
	set OW_WEATHER_LIGHTNING_DISABLED_F, [hl]
	farcall CancelOWFadePalettes
	ldh a, [hBGMapMode]
	push af
	xor a
	assert NO_BG_MAP_TRANSFER == 0
	ldh [hBGMapMode], a
	ldh a, [rVBK]
	push af
	xor a
	ldh [rVBK], a
	ld de, HeadbuttTreeBGGFX
	ld hl, vTiles0 tile HEADBUTT_BG_TILE
	lb bc, BANK(HeadbuttTreeBGGFX), NUM_HEADBUTT_BG_TILES
	call Get2bpp
	call HeadbuttBGMapPointers
	call WaitSFX
	ld de, SFX_SANDSTORM
	call PlaySFX
	ld a, TRUE
	call QueueHeadbuttTree
	ld c, 4
	call HeadbuttDelayFrames
	xor a
	call QueueHeadbuttTree
	ld c, 4
	call HeadbuttDelayFrames
	ld a, TRUE
	call QueueHeadbuttTree
	ld c, 4
	call HeadbuttDelayFrames
	xor a
	call QueueHeadbuttTree
	ld c, 3
	call HeadbuttDelayFrames
	ld a, TRUE
	call QueueHeadbuttTree
	ld c, 3
	call HeadbuttDelayFrames
	xor a
	call QueueHeadbuttTree
	; Keep the original 32-frame pacing, with the tree restored for the rest.
	ld c, 14
	call HeadbuttDelayFrames
	farcall RestoreHeadbuttFontTiles
	pop af
	ldh [rVBK], a
	pop af
	ldh [hBGMapMode], a
	pop af
	and 1 << OW_WEATHER_LIGHTNING_DISABLED_F
	ret nz
	ld hl, wWeatherFlags
	res OW_WEATHER_LIGHTNING_DISABLED_F, [hl]
	ret

FindHeadbuttTree:
; Return carry, hl = original band's tilemap address, b,c = screen y,x.
; Match the graphics family, not map/block IDs (including connection strips).
	ld a, [wTilesetGFX0Bank]
	cp BANK(TilesetNewBarkCherrygroveGFX0)
	jr nz, .not_supported
	ld hl, wTilesetGFX0Address
	ld a, [hli]
	cp LOW(TilesetNewBarkCherrygroveGFX0)
	jr nz, .not_supported
	ld a, [hl]
	cp HIGH(TilesetNewBarkCherrygroveGFX0)
	jr nz, .not_supported
	call GetFacingTileCoord
	cp COLL_HEADBUTT_TREE
	jr nz, .not_supported
	; Facing cells are 16x16; the reanchored player cell starts at (8,8).
	ld a, [wPlayerMapX]
	ld b, a
	ld a, d
	sub b
	add 4
	add a
	ld c, a
	ld a, [wPlayerMapY]
	ld b, a
	ld a, e
	sub b
	add 4
	add a
	ld b, a
	push bc
	ld hl, wTilemap
	ld b, 0
	add hl, bc
	ld bc, SCREEN_WIDTH
	rst AddNTimes
	pop bc
	; The facing cell can be either half of the body, or the cap above it.
	call CheckHeadbuttTree
	ret c
	ld de, -2
	add hl, de
	dec c
	dec c
	call CheckHeadbuttTree
	ret c
	ld de, 2 - 2 * SCREEN_WIDTH
	add hl, de
	inc c
	inc c
	dec b
	dec b
	call CheckHeadbuttTree
	ret c
	ld de, -2
	add hl, de
	dec c
	dec c
	call CheckHeadbuttTree
	ret c
	ld de, 2 + 4 * SCREEN_WIDTH
	add hl, de
	inc c
	inc c
	inc b
	inc b
	inc b
	inc b
	call CheckHeadbuttTree
	ret c
	ld de, -2
	add hl, de
	dec c
	dec c
	jmp CheckHeadbuttTree
.not_supported
	xor a
	ret

CheckHeadbuttTree:
; Preserve hl/bc. All six candidates fit on screen after reanchoring.
	push hl
	push bc
	ld de, 2 * SCREEN_WIDTH + 1
	add hl, de
	ld a, [hl]
	cp $61 ; tree base
	jr z, .variant
	cp $20 ; another tree underneath
	jr nz, .fail
.variant
	ld [wHeadbuttTreeVariant], a
	ld de, -(2 * SCREEN_WIDTH + 1)
	; Reset to the candidate before walking the 4x3 signature.
	add hl, de
	ld de, .Tiles
	ld b, 3
.row
	ld c, 4
.tile
	ld a, [de]
	inc de
	cp $ff
	jr nz, .compare
	ld a, [wHeadbuttTreeVariant]
.compare
	cp [hl]
	jr z, .attributes
	; The shared Violet/Route 36 gate tree has a bank-1 left edge.
	cp $40
	jr nz, .fail
	ld a, c
	cp 4
	jr nz, .fail
	ld a, [hl]
	cp $fb
	jr nz, .fail
.attributes
	push hl
	push bc
	push de
	ld a, c
	cp 3
	ld e, 0
	jr nc, .not_flipped
	ld e, BG_XFLIP
.not_flipped
	ld a, [hl]
	cp $fb
	jr nz, .bank0
	set B_BG_BANK1, e
.bank0
	ld bc, SCREEN_AREA
	add hl, bc
	ld a, [hl]
	and BG_BANK1 | BG_XFLIP | BG_YFLIP
	cp e
	pop de
	pop bc
	pop hl
	jr nz, .fail
	inc hl
	dec c
	jr nz, .tile
	push de
	ld de, SCREEN_WIDTH - 4
	add hl, de
	pop de
	dec b
	jr nz, .row
	scf
	jr .done
.fail
	xor a
.done
	pop bc
	pop hl
	ret

.Tiles:
	db $40, $41, $41, $40
	db $50, $51, $51, $50
	db $60, $ff, $ff, $60

HeadbuttBGMapPointers:
; Six 16x8 pairs, grouped by row; UpdateBGMapBuffer also writes attributes.
	ld a, [wHeadbuttBGMapPointer]
	ld e, a
	ld a, [wHeadbuttBGMapPointer + 1]
	ld d, a
	ld hl, wBGMapBufferPtrs
	ld b, 3
.row
	ld a, e
	ld [hli], a
	ld a, d
	ld [hli], a
	inc de
	inc de
	ld a, e
	ld [hli], a
	ld a, d
	ld [hli], a
	ld a, TILEMAP_WIDTH - 2
	add e
	ld e, a
	adc d
	sub e
	ld d, a
	dec b
	jr nz, .row
	ret

QueueHeadbuttTree:
; a = shake/original. Keep wTilemap/wAttrmap unchanged for exact restoration.
	ld [wHeadbuttShakeState], a
	ld hl, wHeadbuttTilemapPointer
	ld a, [hli]
	ld h, [hl]
	ld l, a
	push hl
	ld de, wBGMapBuffer
	call .CopyRows
	pop hl
	ld bc, SCREEN_AREA
	add hl, bc
	ld de, wBGMapPalBuffer
	call .CopyRows
	ld a, [wHeadbuttShakeState]
	and a
	jr z, .upload
	ld hl, .ShakingTiles
	ld de, wBGMapBuffer
	ld bc, 12
	rst CopyBytes
	ld a, [wHeadbuttTreeVariant]
	cp $20
	ld a, HEADBUTT_BG_TILE + 5
	jr nz, .base
	inc a
.base
	ld [wBGMapBuffer + 9], a
	ld [wBGMapBuffer + 10], a
	ld hl, wBGMapPalBuffer
	ld c, 12
.attributes
	ld a, [hl]
	; Palette/priority and the validated left/right flips are retained.
	and ~(BG_BANK1 | BG_YFLIP)
	ld [hli], a
	dec c
	jr nz, .attributes
.upload
	ld a, 6
	ldh [hBGMapTileCount], a
	ld a, TRUE
	ldh [hBGMapUpdate], a ; publish only after both planes are complete
	ret

.CopyRows:
	ld b, 3
.row
	ld c, 4
.tile
	ld a, [hli]
	ld [de], a
	inc de
	dec c
	jr nz, .tile
	push de
	ld de, SCREEN_WIDTH - 4
	add hl, de
	pop de
	dec b
	jr nz, .row
	ret

.ShakingTiles:
	db HEADBUTT_BG_TILE + 0, HEADBUTT_BG_TILE + 1, HEADBUTT_BG_TILE + 1, HEADBUTT_BG_TILE + 0
	db HEADBUTT_BG_TILE + 2, HEADBUTT_BG_TILE + 3, HEADBUTT_BG_TILE + 3, HEADBUTT_BG_TILE + 2
	db HEADBUTT_BG_TILE + 4, HEADBUTT_BG_TILE + 5, HEADBUTT_BG_TILE + 5, HEADBUTT_BG_TILE + 4

HeadbuttDelayFrames:
; The queued state commits at the first VBlank; the next state is not
; published until c VBlanks have elapsed, giving exactly c display frames.
	farcall DoOverworldWeather
	call DelayFrame
	dec c
	jr nz, HeadbuttDelayFrames
	ret

OWCutAnimation:
	; Animation index in a
	; 0: Split tree in half
	; 1: Mow the lawn
	ld [wJumptableIndex], a
	call ClearSpriteAnims
	call WaitSFX
	ld de, SFX_PLACE_PUZZLE_PIECE_DOWN
	call PlaySFX
	; shift all sprites left in OAM by 4 slots
	; hl = source, de = destination, bc = length
	ldh a, [hUsedOAMIndex]
	; a = OAM_SIZE - a
	cpl
	add OAM_SIZE + 1
	ld h, HIGH(wShadowOAM)
	ld l, a
	sub (4 * OBJ_SIZE)
	ld e, a
	ld d, h
	ld b, 0
	ldh a, [hUsedOAMIndex]
	ld c, a
.copy_loop
	ld a, [hli]
	ld [de], a
	inc de
	dec c
	jr nz, .copy_loop
.loop
	ld a, [wJumptableIndex]
	bit 7, a
	jr nz, .finish

	ld a, LOW(wShadowOAMSprite36)
	ld [wCurSpriteOAMAddr], a
	call DoNextFrameForAllSprites
	farcall DoOverworldWeather
	call OWCutJumptable
	call DelayFrame
	jr .loop

.finish
	; hide tree/leaf sprites

	; shift all sprites right in OAM by 4 slots
	; hl = source, de = destination, bc = length
	ldh a, [hUsedOAMIndex]
	; a = OAM_SIZE - a - 1
	cpl
	add OAM_SIZE
	ld l, a
	ld h, HIGH(wShadowOAM)
	ld de, wShadowOAMSprite39 + 3
	ld c, OBJ_SIZE * 4
.copy_done_loop
	ld a, [hld]
	ld [de], a
	dec de
	dec c
	jr nz, .copy_done_loop

	ld h, HIGH(wShadowOAM)
	ldh a, [hUsedOAMIndex]
	; a = (OAM_COUNT - 4) * OBJ_SIZE - a
	cpl
	add (OAM_COUNT - 4) * OBJ_SIZE + 1
	ld l, a
	ld c, 4
	ld de, OBJ_SIZE
	ld a, OAM_YCOORD_HIDDEN
.hide_loop
	ld [hl], a
	add hl, de
	dec c
	jr nz, .hide_loop
	ret

OWCutJumptable:
	call StandardStackJumpTable

.Jumptable:
	dw Cut_SpawnAnimateTree
	dw Cut_SpawnAnimateLeaves
	dw Cut_StartWaiting
	dw Cut_WaitAnimSFX

Cut_SpawnAnimateTree:
	call Cut_Headbutt_GetPixelFacing
	ld a, SPRITE_ANIM_INDEX_CUT_TREE
	call InitSpriteAnimStruct
	ld hl, SPRITEANIMSTRUCT_TILE_ID
	add hl, bc
	ld [hl], $74
	ld a, 32
	ld [wFrameCounter], a
; Cut_StartWaiting
	ld hl, wJumptableIndex
	inc [hl]
	inc [hl]
	ret

Cut_SpawnAnimateLeaves:
	call Cut_GetLeafSpawnCoords
	xor a
	call Cut_SpawnLeaf
	ld a, $10
	call Cut_SpawnLeaf
	ld a, $20
	call Cut_SpawnLeaf
	ld a, $30
	call Cut_SpawnLeaf
	ld a, 32 ; frames
	ld [wFrameCounter], a
; Cut_StartWaiting
	ld hl, wJumptableIndex
	inc [hl]
	ret

Cut_StartWaiting:
	ld a, TRANSFER_TILEMAP
	ldh [hBGMapMode], a
; Cut_WaitAnimSFX
	ld hl, wJumptableIndex
	inc [hl]

Cut_WaitAnimSFX:
	ld hl, wFrameCounter
	ld a, [hl]
	and a
	jr z, .finished
	dec [hl]
	ret

.finished
	ld hl, wJumptableIndex
	set 7, [hl]
	ret

Cut_SpawnLeaf:
	push de
	push af
	ld a, SPRITE_ANIM_INDEX_LEAF ; leaf
	call InitSpriteAnimStruct
	ld hl, SPRITEANIMSTRUCT_TILE_ID
	add hl, bc
	ld [hl], $70
	ld hl, SPRITEANIMSTRUCT_VAR3
	add hl, bc
	ld [hl], $4
	pop af
	ld hl, SPRITEANIMSTRUCT_VAR1
	add hl, bc
	ld [hl], a
	pop de
	ret

Cut_GetLeafSpawnCoords:
	ld de, 0
	ldh a, [hMetatileStandingX]
	bit 0, a
	jr z, .left_side
	set 0, e
.left_side
	ldh a, [hMetatileStandingY]
	bit 0, a
	jr z, .top_side
	set 1, e
.top_side
	ld a, [wPlayerDirection]
	and %00001100
	add e
	ld e, a
	ld hl, .Coords
	add hl, de
	add hl, de
	ld a, [hli]
	ld d, [hl]
	ld e, a
	ret

.Coords:
	dbpixel 11, 12 ; facing down,  top left
	dbpixel  9, 12 ; facing down,  top right
	dbpixel 11, 14 ; facing down,  bottom left
	dbpixel  9, 14 ; facing down,  bottom right

	dbpixel 11,  8 ; facing up,    top left
	dbpixel  9,  8 ; facing up,    top right
	dbpixel 11, 10 ; facing up,    bottom left
	dbpixel  9, 10 ; facing up,    bottom right

	dbpixel  7, 12 ; facing left,  top left
	dbpixel  9, 12 ; facing left,  top right
	dbpixel  7, 10 ; facing left,  bottom left
	dbpixel  9, 10 ; facing left,  bottom right

	dbpixel 11, 12 ; facing right, top left
	dbpixel 13, 12 ; facing right, top right
	dbpixel 11, 10 ; facing right, bottom left
	dbpixel 13, 10 ; facing right, bottom right

Cut_Headbutt_GetPixelFacing:
	ld a, [wPlayerDirection]
	and %00001100
	srl a
	ld e, a
	ld d, 0
	ld hl, .Coords
	add hl, de
	ld a, [hli]
	ld d, [hl]
	ld e, a
	ret

.Coords:
	dbpixel 10, 13
	dbpixel 10,  9
	dbpixel  8, 11
	dbpixel 12, 11

FlyFromAnim:
	farcall CheckForUsedObjPals
	ldh a, [hUsedOAMIndex]
	cp (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS - 1) * OBJ_SIZE
	call nc, ClearNormalSprites ; not enough OAM slots, clear all sprites.
	ld a, [wUsedObjectPals]
	set 7, a ; slot 7 already reserved for leaves.
	ld [wUsedObjectPals], a
	inc a
	call z, ClearSprites ; no more object palettes available, clear all sprites.
	call HidePlayerSprite
	call DelayFrame
	ld a, [wStateFlags]
	push af
	xor a
	ld [wStateFlags], a
	call FlyFunction_InitGFX
	depixel 10, 10, 4, 0
	ld a, SPRITE_ANIM_INDEX_FLY_MON
	call InitSpriteAnimStruct
	ld hl, SPRITEANIMSTRUCT_TILE_ID
	add hl, bc
	ld [hl], $64
	ld hl, SPRITEANIMSTRUCT_ANIM_SEQ_ID
	add hl, bc
	ld [hl], SPRITE_ANIM_SEQ_FLY_FROM
	ld a, 128
	ld [wFrameCounter], a
.loop
	ld a, [wJumptableIndex]
	bit 7, a
	jr nz, .exit

	ldh a, [hUsedOAMIndex]
	cp (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS - 1) * OBJ_SIZE
	ld a, (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS) * OBJ_SIZE
	jr nc, .got_oam_addr
	ldh a, [hUsedOAMIndex]
	; a = (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS) * OBJ_SIZE - a
	cpl
	add (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS) * OBJ_SIZE + 1
.got_oam_addr
	ld [wCurSpriteOAMAddr], a
	call DoNextFrameForAllSprites_OW
	farcall DoOverworldWeather
	call FlyFunction_FrameTimer
	call DelayFrame
	jr .loop

.exit
	pop af
	ld [wStateFlags], a
	ret

FlyToAnim:
	call HideSprites
	farcall LoadWeatherGraphics
	farcall LoadWeatherPal
	farcall SpawnRandomWeatherFullScreen
	call DelayFrame
	ld a, [wStateFlags]
	push af
	xor a
	ld [wStateFlags], a
	call FlyFunction_InitGFX
	depixel 31, 10, 4, 0
	ld a, SPRITE_ANIM_INDEX_FLY_MON
	call InitSpriteAnimStruct
	ld hl, SPRITEANIMSTRUCT_TILE_ID
	add hl, bc
	ld [hl], $64
	ld hl, SPRITEANIMSTRUCT_ANIM_SEQ_ID
	add hl, bc
	ld [hl], SPRITE_ANIM_SEQ_FLY_TO
	ld hl, SPRITEANIMSTRUCT_VAR4
	add hl, bc
	ld [hl], 11 * 8
	ld a, 64
	ld [wFrameCounter], a
.loop
	ld a, [wJumptableIndex]
	bit 7, a
	jr nz, .exit

	ldh a, [hUsedOAMIndex]
	cp (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS - 1) * OBJ_SIZE
	ld a, (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS) * OBJ_SIZE
	jr nc, .got_oam_addr
	ldh a, [hUsedOAMIndex]
	; a = (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS) * OBJ_SIZE - a
	cpl
	add (OAM_COUNT - NUM_FLYFROM_ANIM_OAMS) * OBJ_SIZE + 1
.got_oam_addr

	ld [wCurSpriteOAMAddr], a
	call DoNextFrameForAllSprites_OW
	farcall DoOverworldWeather
	call FlyFunction_FrameTimer
	call DelayFrame
	jr .loop

.exit
	pop af
	ld [wStateFlags], a

	ld h, HIGH(wShadowOAM)
	ld a, [wCurSpriteOAMAddr]
	sub NUM_FLYTO_ANIM_OAMS * OBJ_SIZE
	ld l, a
	ld b, NUM_FLYTO_ANIM_OAMS
	call HideSpritesInRange

	ld hl, wShadowOAMSprite36TileID
	xor a
	ld c, $4
.loop2
	ld [hli], a
	inc hl
	inc hl
	inc hl
	inc a
	dec c
	jr nz, .loop2
	ret

FlyFunction_InitGFX:
	call ClearSpriteAnims
	call SetOWFlyMonColor
	ld e, $64
	call FlyFunction_GetMonIcon
	xor a
	ld [wJumptableIndex], a
	ret

FlyFunction_FrameTimer:
	call .SpawnLeaf
	ld hl, wFrameCounter
	ld a, [hl]
	and a
	jr z, .exit
	dec [hl]
	cp $40
	ret c
	and $7
	ret nz
	ld de, SFX_FLY
	jmp PlaySFX

.exit
	ld hl, wJumptableIndex
	set 7, [hl]
	ret

.SpawnLeaf:
	ld hl, wFrameCounter2
	ld a, [hl]
	inc [hl]
	and $7
	ret nz
	ld a, [hl]
	and (6 * 8) >> 1
	add a
	add 8 * 8 ; gives a number in [$40, $50, $60, $70]
	ld d, a
	ld e, 0
	ld a, SPRITE_ANIM_INDEX_FLY_LEAF ; fly land
	call InitSpriteAnimStruct
	ld hl, SPRITEANIMSTRUCT_TILE_ID
	add hl, bc
	ld [hl], $70
	ret
