; Shared NPC graphics retain the original paired VRAM regions. The player and
; temporary effects are private allocations; ordinary object indexes do not
; determine VRAM ownership. All work here happens on spawn/reload, not per frame.

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
	; Select graphics by use: atlas trees, three-tile stationary balls, or
	; the original sheet for decorations. Pearl rocks also retain their sheet.
	ldh a, [hUsedSpriteIndex]
	cp SPRITE_BALL_CUT_TREE
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
	; The three-tile tail overlaps a 15-tile resource's base pose.
	call RelocateStationaryBallForSpecial
	ret c
	call MarkUsedSpriteGfx
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
	ld d, $30 ; old encoded tile: final bank-1 slot
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
	assert SPECIAL_SPRITE_GFX_SLOT == 11
	assert (FIRST_VRAM1_SPRITE_GFX_SLOT + 1) * 12 == $60
	assert (SPECIAL_SPRITE_GFX_SLOT - FIRST_VRAM1_SPRITE_GFX_SLOT) * 12 + 15 < $40

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
	ld d, 1
	cp -12
	jr z, .claim
	; A relocated ball occupies the last three tiles of an ordinary block.
	; Its other nine tiles and its alternate region are never uploaded.
	cp -STATIONARY_BALL_TILES
	jr nz, .restore
	ld d, SPRITE_GFX_PARTIAL
.claim
	ld a, c
	cp NUM_SPRITE_GFX_SLOTS
	jr nc, .restore
	call SpriteGfxUsed
	ld [hl], d
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
; Only complete, live slots can hit. A ball's partial occupancy blocks a
; 12-tile allocation but must never match that block's obsolete resource key.
	ld c, 0
.loop
	ld a, c
	call SpriteGfxUsed
	dec a
	jr nz, .next
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
	call MarkUsedSpriteGfx
	ld a, [wSpriteGfxUsed + SPECIAL_SPRITE_GFX_SLOT]
	dec a
	jr nz, .tail
	ld a, SPECIAL_SPRITE_GFX_SLOT
	call SpriteGfxKey
	inc hl
	inc hl
	inc hl
	bit SPRITE_GFX_SPECIAL_F, [hl]
	jr z, .tail
	; A large sprite occupies $30-$3e. Use three tiles at the end of a
	; free ordinary block instead; no full-block or alternate copy is made.
	ld b, SPECIAL_SPRITE_GFX_SLOT
	call FindFreeSpriteGfx
	ret c
	call SpriteGfxTile
	add 12 - STATIONARY_BALL_TILES
	jr LoadStationaryBallGFX
.tail
	ld a, STATIONARY_BALL_VRAM1_TILE
	assert STATIONARY_BALL_VRAM1_TILE + STATIONARY_BALL_TILES == $3f
	; fallthrough

LoadStationaryBallGFX:
; a = encoded three-tile base; return it with carry clear.
	push af
	ld hl, wSpriteFlags
	res 5, [hl]
	bit 7, a
	jr nz, .bank_set
	set 5, [hl]
.bank_set
	and $7f
	ldh [hUsedSpriteTile], a
	ld de, StationaryBallSpriteGFX
	lb bc, BANK(StationaryBallSpriteGFX), STATIONARY_BALL_TILES
	farcall LoadUsedSpriteGFX
	pop af
	and a
	ret

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
	cp UNALLOCATED_SPRITE_TILE
	jr z, .next
	ld d, a
	ld a, [hl] ; OBJECT_MOVEMENT_TYPE
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr nz, .next
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

RelocateStationaryBallForSpecial:
	call FindLiveStationaryBall
	jr nc, .done
	cp STATIONARY_BALL_VRAM1_TILE
	jr nz, .done
	push af ; old encoded base
	ld b, SPECIAL_SPRITE_GFX_SLOT
	call FindFreeSpriteGfx
	jr c, .full
	call SpriteGfxTile
	add 12 - STATIONARY_BALL_TILES
	call LoadStationaryBallGFX
	pop de ; d = old encoded base
	ld e, a
	call RepointSharedSprites
	; Publish every new ball reference before the special overwrites $3c-$3e.
	farcall _UpdateSprites
	ldh a, [rLCDC]
	bit B_LCDC_ENABLE, a
	jr z, .done
	ldh a, [hOAMUpdate]
	and a
	call z, DelayFrame
.done
	and a
	ret
.full
	pop de
	ret ; preserve allocation failure carry
