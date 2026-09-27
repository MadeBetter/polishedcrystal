; Shared NPC graphics retain the original paired VRAM regions. The player and
; temporary effects are private allocations; ordinary object indexes do not
; determine VRAM ownership. All work here happens on spawn/reload, not per frame.

RestoreTextSpriteGFX::
; Ordinary dialogue overwrites only bank-0 alternate poses. Keep live bases,
; keys and object references intact; the caller keeps sprites in text poses.
	push hl
	push de
	push bc
	farcall GetPlayerSpriteInA
	ld hl, wPlayerSprite
	cp [hl]
	jr z, .restore
	; A scripted player-state change needs the existing full restore path.
	farcall RefreshSprites
	jmp PopBCDEHL
.restore
	ld a, [wSpriteFlags]
	push af
	ld a, 1 << 7 ; skip base copy, allow alternate copy, VRAM bank 0
	ld [wSpriteFlags], a
	ldh a, [hObjectStructIndexBuffer]
	push af
	xor a
	ldh [hObjectStructIndexBuffer], a ; include every live NPC in the scan
	ldh [hUsedSpriteTile], a ; private player base
	ld a, [wPlayerSprite]
	ldh [hUsedSpriteIndex], a
	farcall GetUsedSprite

	call MarkUsedSpriteGfx
	ld c, 0
.loop
	ld a, c
	call SpriteGfxUsed
	jr z, .next
	ld a, c
	call SpriteGfxKey
	inc hl
	inc hl
	inc hl
	ld a, [hl]
	cp 12 ; bank-0 Pokemon icons have no alternate group
	jr nz, .next
	ld a, c
	push bc
	call LoadSharedSpriteGfx
	pop bc
.next
	inc c
	ld a, c
	cp FIRST_VRAM1_SPRITE_GFX_SLOT ; bank 1 was not overwritten by text
	jr nz, .loop
	pop af
	ldh [hObjectStructIndexBuffer], a
	pop af
	ld [wSpriteFlags], a
	jmp PopBCDEHL

AcquireSharedSprite:
; hUsedSpriteIndex = sprite; bc = map/object context; hIsMapObject selects it.
; Return encoded OBJECT_SPRITE_TILE in a, or carry if no compatible slot exists.
	ldh a, [hObjectStructIndexBuffer]
	and a
	jr nz, .npc
	ld hl, wSpriteFlags
	res 5, [hl]
	ldh [hUsedSpriteTile], a
	farcall GetUsedSprite
	ld a, $80
	and a
	ret

.npc
	; Select graphics by use: atlas trees, compact fixed objects, or the
	; original sheet for decorations. Pearl rocks also retain their sheet.
	ldh a, [hUsedSpriteIndex]
	cp SPRITE_BALL_CUT_TREE
	jr z, .get_movement
	cp SPRITE_BOULDER_ROCK
	jr z, .get_movement
	cp SPRITE_BLANK_FRUIT
	jr nz, .resolve
.get_movement
	ldh a, [hIsMapObject]
	and a
	ld hl, MAPOBJECT_MOVEMENT
	jr nz, .movement
	ld hl, OBJECT_MOVEMENT_TYPE
.movement
	add hl, bc
	ld d, [hl]
	ldh a, [hUsedSpriteIndex]
	cp SPRITE_BOULDER_ROCK
	jr z, .rock
	cp SPRITE_BLANK_FRUIT
	ld a, d
	jr z, .fruit
	cp SPRITEMOVEDATA_STANDING_DOWN
	jp z, AcquireStationaryBall
	cp SPRITEMOVEDATA_CUTTABLE_TREE
	jr nz, .resolve
.atlas
	ld a, $80 ; bank 0, no shared graphics slot; facing uses absolute tiles
	and a
	ret

.fruit
	; BlankFruit also supplies decorations; only actual fruit trees use atlas.
	cp SPRITEMOVEDATA_FRUIT
	jr z, .atlas
	jr .resolve
.rock
	ld a, d
	cp SPRITEMOVEDATA_SMASHABLE_ROCK
	jp z, AcquireSmashableRock
	cp SPRITEMOVEDATA_STRENGTH_BOULDER
	jp z, AcquireStrengthBoulder
	cp SPRITEMOVEDATA_STANDING_DOWN
	jp z, AcquireStrengthBoulder
.resolve
	ldh a, [hUsedSpriteIndex]
	farcall GetSprite
	; Resolve aliases and Pokemon forms before comparing the actual ROM data.
	; c=8 is an icon; c=15 needs the extra room in the last bank-1 slot.
	ld a, c
	cp 15
	jr z, .special
	ld a, b
	cp BANK(SailboatSpriteGFX)
	jr nz, .key
	ld a, d
	cp HIGH(SailboatSpriteGFX)
	jr nz, .key
	ld a, e
	cp LOW(SailboatSpriteGFX)
	jr nz, .key
.special
	set SPRITE_GFX_SPECIAL_F, c
.key
	ld hl, wSpriteGfxRequest
	ld a, b
	ld [hli], a
	ld a, e
	ld [hli], a
	ld a, d
	ld [hli], a
	ld [hl], c

	call MarkUsedSpriteGfx
	call FindSharedSpriteGfx
	jr nc, SpriteGfxTile ; hit: no decompression or VRAM transfer

	ld a, [wSpriteGfxRequest + 3]
	bit SPRITE_GFX_SPECIAL_F, a
	jr nz, .special_slot
	ld b, NUM_SPRITE_GFX_SLOTS
	call FindFreeSpriteGfx
	ret c
	jr .allocate

.special_slot
	ld a, [wSpriteGfxUsed + SPECIAL_SPRITE_GFX_SLOT]
	and a
	ld a, SPECIAL_SPRITE_GFX_SLOT
	jr z, .allocate

	; The last slot can hold an ordinary resource until a special needs it.
	; Move that resource and every user together, never overwrite live graphics.
	call SpriteGfxKey
	inc hl
	inc hl
	inc hl
	bit SPRITE_GFX_SPECIAL_F, [hl]
	jr nz, .full ; different special resources cannot share the same fixed slot
	ld b, SPECIAL_SPRITE_GFX_SLOT
	call FindFreeSpriteGfx
	ret c
	push af
	call SpriteGfxKey
	push hl
	ld a, SPECIAL_SPRITE_GFX_SLOT
	call SpriteGfxKey
	pop de
	ld bc, SPRITE_GFX_KEY_LENGTH
	rst CopyBytes
	pop af
	call LoadSharedSpriteGfx
	ld e, a ; new encoded tile
	ld d, SPECIAL_SPRITE_GFX_TILE ; old encoded tile: final bank-1 slot
	call RepointSharedSprites
	; Rebuild OAM without advancing movement. If DMA is active, let it publish
	; the relocated references before replacing the old graphics.
	farcall _UpdateSprites
	ldh a, [rLCDC]
	bit B_LCDC_ENABLE, a
	jr z, .relocated
	ldh a, [hOAMUpdate]
	and a
	call z, DelayFrame
.relocated
	ld a, SPECIAL_SPRITE_GFX_SLOT
.allocate
	ld [wSpriteGfxSlot], a
	call SpriteGfxKey
	ld d, h
	ld e, l
	ld hl, wSpriteGfxRequest
	ld bc, SPRITE_GFX_KEY_LENGTH
	rst CopyBytes
	ld a, [wSpriteGfxSlot]
	jmp LoadSharedSpriteGfx

.full
	scf
	ret

SpriteGfxTile:
; a = graphics slot; return encoded tile base. Preserves bc/de, clears carry.
	add LOW(.Tiles)
	ld l, a
	adc HIGH(.Tiles)
	sub l
	ld h, a
	ld a, [hl]
	and a
	ret
.Tiles
	table_width 1
for i, 1, FIRST_VRAM1_SPRITE_GFX_SLOT + 1
	db $80 | (i * 12)
endr
for i, NUM_SPRITE_GFX_SLOTS - FIRST_VRAM1_SPRITE_GFX_SLOT
	db i * 12
endr
	assert_table_length NUM_SPRITE_GFX_SLOTS
	assert SPECIAL_SPRITE_GFX_SLOT == 9
	assert SPECIAL_SPRITE_GFX_TILE == $18
	assert (FIRST_VRAM1_SPRITE_GFX_SLOT + 1) * 12 == $60
	; Keep special sprites clear of the fixed compact-object atlas.
	assert SPECIAL_SPRITE_GFX_TILE + 15 == $27
	assert SPECIAL_SPRITE_GFX_TILE + 15 <= STRENGTH_BOULDER_VRAM1_TILE
	assert STRENGTH_BOULDER_VRAM1_TILE + STRENGTH_BOULDER_TILES == SMASHABLE_ROCK_VRAM1_TILE
	assert SPECIAL_SPRITE_GFX_TILE + 15 <= SMASHABLE_ROCK_VRAM1_TILE
	assert SMASHABLE_ROCK_VRAM1_TILE + SMASHABLE_ROCK_TILES == STATIONARY_BALL_VRAM1_TILE
	assert SPECIAL_SPRITE_GFX_TILE + 15 <= STATIONARY_BALL_VRAM1_TILE
	assert SPECIAL_SPRITE_GFX_TILE + $40 + 15 == $67
	assert STATIONARY_BALL_VRAM1_TILE + STATIONARY_BALL_TILES == $40
	assert SPECIAL_SPRITE_GFX_TILE + $40 + 15 <= PLAYER_OVERLAY_VRAM1_TILE
	assert PLAYER_OVERLAY_VRAM1_TILE + PLAYER_OVERLAY_TILES == $80

SpriteGfxKey:
; a = graphics slot; return its four-byte key in hl. Preserves bc/de.
	assert SPRITE_GFX_KEY_LENGTH == 4
	add a
	add a
	add LOW(wSpriteGfxKeys)
	ld l, a
	adc HIGH(wSpriteGfxKeys)
	sub l
	ld h, a
	ret

SpriteGfxUsed:
; a = graphics slot; return its live-use flag in a. Preserves bc/de.
	add LOW(wSpriteGfxUsed)
	ld l, a
	adc HIGH(wSpriteGfxUsed)
	sub l
	ld h, a
	ld a, [hl]
	and a
	ret

MarkUsedSpriteGfx:
; Recompute ownership from live objects. This also handles bulk object clears,
; connection reassociation, and multiple users without persistent refcounts.
; Exclude the object being rebound: its old slot is reusable if nobody else
; owns it. Temporary effects use absolute graphics and never own these slots.
	ld hl, wSpriteGfxUsed
	ld bc, NUM_SPRITE_GFX_SLOTS
	xor a
	rst ByteFill
	ld bc, wObject1Struct
	ld e, 1
.loop
	ldh a, [hObjectStructIndexBuffer]
	cp e
	jr z, .next
	ld a, [bc]
	and a
	jr z, .next
	ld hl, OBJECT_MAP_OBJECT_INDEX
	add hl, bc
	ld a, [hli]
	cp TEMP_OBJECT
	jr z, .next
	ld a, [hl] ; OBJECT_SPRITE_TILE
	cp UNALLOCATED_SPRITE_TILE
	jr z, .next
	push bc
	push de
	; Invert the 12-tile stride with at most eight small subtractions, rather
	; than searching the address table once for every live object.
	ld c, -1 ; bank 0 starts at tile 12 (tile 0 belongs to the player)
	bit 7, a
	jr nz, .bank_set
	ld c, FIRST_VRAM1_SPRITE_GFX_SLOT
.bank_set
	and $7f
.divide
	sub 12
	jr c, .slot
	inc c
	jr .divide
.slot
	cp -12 ; only exact twelve-tile bases can own a shared slot
	jr nz, .restore
	ld a, c
	cp NUM_SPRITE_GFX_SLOTS ; also excludes atlas objects and fixed balls
	jr nc, .restore
	call SpriteGfxUsed
	ld [hl], 1
.restore
	pop de
	pop bc
.next
	ld hl, OBJECT_LENGTH
	add hl, bc
	ld b, h
	ld c, l
	inc e
	ld a, e
	cp NUM_OBJECT_STRUCTS
	jr nz, .loop
	ret

FindSharedSpriteGfx:
; Only live shared allocations can hit; fixed balls own no shared slot.
	ld c, 0
.loop
	ld a, c
	call SpriteGfxUsed
	jr z, .next
	ld a, c
	call SpriteGfxKey
	ld de, wSpriteGfxRequest
	ld b, SPRITE_GFX_KEY_LENGTH
.compare
	ld a, [de]
	inc de
	cp [hl]
	jr nz, .next
	inc hl
	dec b
	jr nz, .compare
	ld a, c
	and a
	ret
.next
	inc c
	ld a, c
	cp NUM_SPRITE_GFX_SLOTS
	jr nz, .loop
	scf
	ret

FindFreeSpriteGfx:
; b = exclusive slot limit. Carry means every compatible slot is in use.
	ld c, 0
.loop
	ld a, c
	call SpriteGfxUsed
	ld a, c ; preserve Z from the live-use flag
	ret z ; SpriteGfxUsed cleared carry
	inc c
	ld a, c
	cp b
	jr nz, .loop
	scf
	ret

LoadSharedSpriteGfx:
; Load one resolved key into its paired regions, returning the encoded tile.
	push af
	call SpriteGfxKey
	ld a, [hli]
	ld b, a
	ld a, [hli]
	ld e, a
	ld a, [hli]
	ld d, a
	ld a, [hl]
	and ~(1 << SPRITE_GFX_SPECIAL_F)
	ld c, a
	pop af
	call SpriteGfxTile
	push af
	ld hl, wSpriteFlags
	res 5, [hl]
	bit 7, a
	jr nz, .bank_set
	set 5, [hl]
.bank_set
	and $7f
	ldh [hUsedSpriteTile], a
	farcall LoadUsedSpriteGFX
	pop af ; SpriteGfxTile cleared carry
	ret

RepointSharedSprites:
; d = old encoded tile, e = new encoded tile; preserve temporary effects.
	ld bc, wObject1Struct
.loop
	ld a, [bc]
	and a
	jr z, .next
	ld hl, OBJECT_MAP_OBJECT_INDEX
	add hl, bc
	ld a, [hli]
	cp TEMP_OBJECT
	jr z, .next
	ld a, [hl]
	cp d
	jr nz, .next
	ld [hl], e
.next
	ld hl, OBJECT_LENGTH
	add hl, bc
	ld b, h
	ld c, l
	ld a, c
	cp LOW(wObjectStructsEnd)
	jr nz, .loop
	ld a, b
	cp HIGH(wObjectStructsEnd)
	jr nz, .loop
	ret

DetachSharedSprites:
; Called before a full restore. Do not change object or save-data layouts.
	ld bc, wObject1Struct
	ld d, NUM_OBJECT_STRUCTS - 1
.loop
	ld hl, OBJECT_MAP_OBJECT_INDEX
	add hl, bc
	ld a, [hli]
	cp TEMP_OBJECT
	jr z, .next
	ld [hl], UNALLOCATED_SPRITE_TILE
.next
	ld hl, OBJECT_LENGTH
	add hl, bc
	ld b, h
	ld c, l
	dec d
	jr nz, .loop
	ret

AcquireStationaryBall:
	call FindLiveStationaryBall
	jr nc, .new
	and a ; sharing hit: no decompression or transfer
	ret
.new
	ld a, STATIONARY_BALL_VRAM1_TILE
	ld de, StationaryBallSpriteGFX
	lb bc, BANK(StationaryBallSpriteGFX), STATIONARY_BALL_TILES
	jr LoadFixedSpriteGFX

FindLiveStationaryBall:
; Carry and a = existing encoded base. Ignore the object being rebound and
; detached objects so menu restoration never mistakes stale VRAM for a hit.
	ld bc, wObject1Struct
	ld e, 1
.loop
	ldh a, [hObjectStructIndexBuffer]
	cp e
	jr z, .next
	ld a, [bc]
	cp SPRITE_BALL_CUT_TREE
	jr nz, .next
	ld hl, OBJECT_MAP_OBJECT_INDEX
	add hl, bc
	ld a, [hli]
	cp TEMP_OBJECT
	jr z, .next
	ld a, [hli] ; OBJECT_SPRITE_TILE
	cp STATIONARY_BALL_VRAM1_TILE
	jr nz, .next
	ld a, [hl] ; OBJECT_MOVEMENT_TYPE
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr nz, .next
	ld a, STATIONARY_BALL_VRAM1_TILE
	scf
	ret
.next
	ld hl, OBJECT_LENGTH
	add hl, bc
	ld b, h
	ld c, l
	inc e
	ld a, e
	cp NUM_OBJECT_STRUCTS
	jr nz, .loop
	and a
	ret

AcquireSmashableRock:
	ld d, SMASHABLE_ROCK_VRAM1_TILE
	call FindLiveFixedBoulder
	jr nc, .new
	and a ; sharing hit: no decompression or transfer
	ret
.new
	ld a, SMASHABLE_ROCK_VRAM1_TILE
	ld de, SmashableRockSpriteGFX
	lb bc, BANK(SmashableRockSpriteGFX), SMASHABLE_ROCK_TILES
	; fallthrough

LoadFixedSpriteGFX:
; a = fixed bank-1 tile; b:de = graphics; c = exact tile count.
; These tiles never overlap a shared allocation or special sprite.
	push af
	ld hl, wSpriteFlags
	set 5, [hl]
	ldh [hUsedSpriteTile], a
	farcall LoadUsedSpriteGFX
	pop af
	and a
	ret

AcquireStrengthBoulder:
	ld d, STRENGTH_BOULDER_VRAM1_TILE
	call FindLiveFixedBoulder
	jr nc, .new
	and a ; sharing hit: no decompression or transfer
	ret
.new
	ld a, STRENGTH_BOULDER_VRAM1_TILE
	ld de, StrengthBoulderSpriteGFX
	lb bc, BANK(StrengthBoulderSpriteGFX), STRENGTH_BOULDER_TILES
	jr LoadFixedSpriteGFX

FindLiveFixedBoulder:
; d = fixed tile base. Carry and a = an existing matching base. Only the
; ordinary boulder sheet uses these atlases; special sheets stay separate.
	ld bc, wObject1Struct
	ld e, 1
.loop
	ldh a, [hObjectStructIndexBuffer]
	cp e
	jr z, .next
	ld a, [bc]
	cp SPRITE_BOULDER_ROCK
	jr nz, .next
	ld hl, OBJECT_MAP_OBJECT_INDEX
	add hl, bc
	ld a, [hli]
	cp TEMP_OBJECT
	jr z, .next
	ld a, [hli] ; OBJECT_SPRITE_TILE
	cp d
	jr nz, .next
	ld a, [hl] ; OBJECT_MOVEMENT_TYPE
	cp SPRITEMOVEDATA_SMASHABLE_ROCK
	jr z, .smashable
	cp SPRITEMOVEDATA_STRENGTH_BOULDER
	jr z, .strength
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr nz, .next
.strength
	ld a, d
	cp STRENGTH_BOULDER_VRAM1_TILE
	jr nz, .next
	jr .found
.smashable
	ld a, d
	cp SMASHABLE_ROCK_VRAM1_TILE
	jr nz, .next
.found
	ld a, d
	scf
	ret
.next
	ld hl, OBJECT_LENGTH
	add hl, bc
	ld b, h
	ld c, l
	inc e
	ld a, e
	cp NUM_OBJECT_STRUCTS
	jr nz, .loop
	and a
	ret
