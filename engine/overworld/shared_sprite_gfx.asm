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
	; Select graphics by use: atlas trees, compact dynamic objects, or the
	; original sheet for decorations. Pearl rocks also retain their sheet.
	ldh a, [hUsedSpriteIndex]
	cp SPRITE_CAMPFIRE
	jp z, AcquireCampfire
	cp SPRITE_BALL_CUT_TREE
	jr z, .get_movement
	cp SPRITE_BOULDER_ROCK
	jr z, .get_movement
	cp SPRITE_BLANK_FRUIT
	jr z, .get_movement
	cp SPRITE_BOOK_PAPER_POKEDEX
	jr z, .get_movement
	cp SPRITE_ICE_BOULDER_FOSSILS
	jp nz, .resolve
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
	cp SPRITE_ICE_BOULDER_FOSSILS
	jr z, .ice_boulder_fossils
	cp SPRITE_BOOK_PAPER_POKEDEX
	jr z, .book_paper_pokedex
	cp SPRITE_BOULDER_ROCK
	jr z, .rock
	cp SPRITE_BLANK_FRUIT
	ld a, d
	jr z, .fruit
	cp SPRITEMOVEDATA_STANDING_DOWN
	jp z, AcquireStationaryBall
	cp SPRITEMOVEDATA_ARCH_TREE_LEFT
	jp z, AcquireArchTree
	cp SPRITEMOVEDATA_ARCH_TREE_RIGHT
	jp z, AcquireArchTree
	cp SPRITEMOVEDATA_CUTTABLE_TREE
	jr z, .atlas
	; Every supported use of this overloaded sprite ID has its own compact or
	; atlas path. Reject unknown movement types instead of reading past a
	; three-tile descriptor as though it were a 12-tile standing sheet.
	scf
	ret
.atlas
	ld a, $80 ; bank 0, no shared graphics slot; facing uses absolute tiles
	and a
	ret

.fruit
	; Fruit trees and invisible anchors need no allocation; Silver Cave does.
	cp SPRITEMOVEDATA_FRUIT
	jr z, .atlas
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr z, .atlas
	cp SPRITEMOVEDATA_POKECOM_NEWS
	jp z, AcquireSilverCaveArch
	cp SPRITEMOVEDATA_ARCH_TREE_RIGHT
	jp z, AcquireSilverCaveArch
	; Every supported use has an atlas or compact resource.
	scf
	ret
.ice_boulder_fossils
	ld a, d
	cp SPRITEMOVEDATA_STRENGTH_BOULDER
	jp z, AcquireIceBoulder
	cp SPRITEMOVEDATA_STANDING_DOWN
	jp z, AcquireIceBoulder
	cp SPRITEMOVEDATA_STANDING_UP
	jp z, AcquireHelixFossil
	cp SPRITEMOVEDATA_STANDING_LEFT
	jp z, AcquireDomeFossil
	scf
	ret
.book_paper_pokedex
	ld a, d
	cp SPRITEMOVEDATA_STANDING_DOWN
	jp z, AcquireBook
	cp SPRITEMOVEDATA_STANDING_UP
	jp z, AcquirePaper
	cp SPRITEMOVEDATA_STANDING_LEFT
	jp z, AcquirePokedex
	scf
	ret
.rock
	ld a, d
	cp SPRITEMOVEDATA_SMASHABLE_ROCK
	jp z, AcquireSmashableRock
	cp SPRITEMOVEDATA_STRENGTH_BOULDER
	jp z, AcquireStrengthBoulder
	cp SPRITEMOVEDATA_STANDING_DOWN
	jp z, AcquireStrengthBoulder
	cp SPRITEMOVEDATA_STANDING_LEFT
	jp z, AcquirePokecomSign
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
	; Keep special sprites clear of the compact-object allocation pool.
	assert SPECIAL_SPRITE_GFX_TILE + 15 == $27
	assert SPECIAL_SPRITE_GFX_TILE + 15 == OVERWORLD_OBJECT_VRAM1_START
	assert OVERWORLD_OBJECT_VRAM1_START < OVERWORLD_OBJECT_VRAM1_END
	assert SPECIAL_SPRITE_GFX_TILE + $40 + 15 == $67
	assert OVERWORLD_OBJECT_VRAM1_END <= PLAYER_OVERLAY_VRAM1_TILE
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
	cp NUM_SPRITE_GFX_SLOTS ; also excludes atlas and compact dynamic objects
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
; Only live shared allocations can hit; compact objects own no shared slot.
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
	ld a, OVERWORLD_OBJECT_GFX_STATIONARY_BALL
	ld de, StationaryBallSpriteGFX
	lb bc, BANK(StationaryBallSpriteGFX), STATIONARY_BALL_TILES
	jr AcquireOverworldObjectGFX

AcquireArchTree:
	ld a, OVERWORLD_OBJECT_GFX_ARCH_TREE
	ld de, ArchTreeSpriteGFX
	lb bc, BANK(ArchTreeSpriteGFX), ARCH_TREE_TILES
	jr AcquireOverworldObjectGFX

AcquireSilverCaveArch:
	ld a, OVERWORLD_OBJECT_GFX_SILVER_CAVE_ARCH
	ld de, SilverCaveArchSpriteGFX
	lb bc, BANK(SilverCaveArchSpriteGFX), SILVER_CAVE_ARCH_TILES
	jr AcquireOverworldObjectGFX

AcquireBook:
	ld a, OVERWORLD_OBJECT_GFX_BOOK
	ld de, BookSpriteGFX
	lb bc, BANK(BookSpriteGFX), BOOK_TILES
	jr AcquireOverworldObjectGFX

AcquirePaper:
	ld a, OVERWORLD_OBJECT_GFX_PAPER
	ld de, PaperSpriteGFX
	lb bc, BANK(PaperSpriteGFX), PAPER_TILES
	jr AcquireOverworldObjectGFX

AcquirePokedex:
	ld a, OVERWORLD_OBJECT_GFX_POKEDEX
	ld de, PokedexObjectSpriteGFX
	lb bc, BANK(PokedexObjectSpriteGFX), POKEDEX_TILES
	jr AcquireOverworldObjectGFX

AcquirePokecomSign:
	ld a, OVERWORLD_OBJECT_GFX_POKECOM_SIGN
	ld de, PokecomSignSpriteGFX
	lb bc, BANK(PokecomSignSpriteGFX), POKECOM_SIGN_TILES
	jr AcquireOverworldObjectGFX

AcquireIceBoulder:
	ld a, OVERWORLD_OBJECT_GFX_ICE_BOULDER
	ld de, IceBoulderSpriteGFX
	lb bc, BANK(IceBoulderSpriteGFX), ICE_BOULDER_TILES
	jr AcquireOverworldObjectGFX

AcquireHelixFossil:
	ld a, OVERWORLD_OBJECT_GFX_HELIX_FOSSIL
	ld de, HelixFossilSpriteGFX
	lb bc, BANK(HelixFossilSpriteGFX), HELIX_FOSSIL_TILES
	jr AcquireOverworldObjectGFX

AcquireDomeFossil:
	ld a, OVERWORLD_OBJECT_GFX_DOME_FOSSIL
	ld de, DomeFossilSpriteGFX
	lb bc, BANK(DomeFossilSpriteGFX), DOME_FOSSIL_TILES
	jr AcquireOverworldObjectGFX

AcquireCampfire:
	ld a, OVERWORLD_OBJECT_GFX_CAMPFIRE
	ld de, CompactCampfireSpriteGFX
	lb bc, BANK(CompactCampfireSpriteGFX), CAMPFIRE_TILES
	jr AcquireOverworldObjectGFX

AcquireSmashableRock:
	ld a, OVERWORLD_OBJECT_GFX_SMASHABLE_ROCK
	ld de, SmashableRockSpriteGFX
	lb bc, BANK(SmashableRockSpriteGFX), SMASHABLE_ROCK_TILES
	jr AcquireOverworldObjectGFX

AcquireStrengthBoulder:
	ld a, OVERWORLD_OBJECT_GFX_STRENGTH_BOULDER
	ld de, StrengthBoulderSpriteGFX
	lb bc, BANK(StrengthBoulderSpriteGFX), STRENGTH_BOULDER_TILES
	; fallthrough

AcquireOverworldObjectGFX:
; a = resource ID; b:de = graphics; c = exact tile count.
; Allocate downward from $3f and use live objects as the ownership table.
	ld [wSpriteGfxSlot], a
	ld hl, wSpriteGfxRequest
	ld a, b
	ld [hli], a
	ld a, e
	ld [hli], a
	ld a, d
	ld [hli], a
	ld [hl], c
	call FindLiveOverworldObjectGFX
	jr nc, .new
	and a ; sharing hit: no decompression or transfer
	ret
.new
	call FindFreeOverworldObjectGFX
	ret c
	push af
	ld hl, wSpriteGfxRequest
	ld a, [hli]
	ld b, a
	ld a, [hli]
	ld e, a
	ld a, [hli]
	ld d, a
	ld c, [hl]
	pop af
	push af
	ld hl, wSpriteFlags
	set 5, [hl]
	ldh [hUsedSpriteTile], a
	farcall LoadUsedSpriteGFX
	pop af
	and a
	ret

FindLiveOverworldObjectGFX:
; Carry and a = an existing base for the requested resource. Ignore the object
; being rebound and detached objects so a stale tile cannot become a hit.
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
	ld a, [hl]
	cp TEMP_OBJECT
	jr z, .next
	call GetOverworldObjectGFXResource
	jr nc, .next
	ld d, a
	ld a, [wSpriteGfxSlot]
	cp d
	jr nz, .next
	ld hl, OBJECT_SPRITE_TILE
	add hl, bc
	ld a, [hl]
	cp OVERWORLD_OBJECT_VRAM1_START
	jr c, .next
	cp OVERWORLD_OBJECT_VRAM1_END
	jr nc, .next
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

FindFreeOverworldObjectGFX:
; Return the highest exact-size free range in a. The lower bound permanently
; reserves the three tiles that overlap the 15-tile special sprite.
	ld a, [wSpriteGfxRequest + 3]
	cpl
	add OVERWORLD_OBJECT_VRAM1_END + 1
.loop
	ldh [hUsedSpriteTile], a
	call OverworldObjectGFXRangeIsFree
	jr nc, .found
	ldh a, [hUsedSpriteTile]
	dec a
	cp OVERWORLD_OBJECT_VRAM1_START - 1
	jr nz, .loop
	scf
	ret
.found
	ldh a, [hUsedSpriteTile]
	and a
	ret

OverworldObjectGFXRangeIsFree:
; Carry means the requested range overlaps a live compact resource.
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
	ld a, [hl]
	cp TEMP_OBJECT
	jr z, .next
	call GetOverworldObjectGFXResource
	jr nc, .next
	call OverworldObjectGFXTileCount
	ld d, a
	ld hl, OBJECT_SPRITE_TILE
	add hl, bc
	ld a, [hl]
	cp OVERWORLD_OBJECT_VRAM1_START
	jr c, .next
	cp OVERWORLD_OBJECT_VRAM1_END
	jr nc, .next
	ld h, a ; live start
	ldh a, [hUsedSpriteTile]
	ld l, a ; requested start
	ld a, [wSpriteGfxRequest + 3]
	add l ; requested end
	cp h
	jr c, .next
	jr z, .next
	ld a, h
	add d ; live end
	cp l
	jr c, .next
	jr z, .next
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

GetOverworldObjectGFXResource:
; bc = object_struct. Return resource ID in a and carry for compact objects.
	ld a, [bc] ; OBJECT_SPRITE
	cp SPRITE_CAMPFIRE
	jr z, .campfire
	cp SPRITE_BOULDER_ROCK
	jp z, .boulder
	cp SPRITE_BALL_CUT_TREE
	jr z, .ball_cut_tree
	cp SPRITE_BLANK_FRUIT
	jr z, .blank_fruit
	cp SPRITE_BOOK_PAPER_POKEDEX
	jr z, .book_paper_pokedex
	cp SPRITE_ICE_BOULDER_FOSSILS
	jr z, .ice_boulder_fossils
	jp .no
.campfire
	ld a, OVERWORLD_OBJECT_GFX_CAMPFIRE
	scf
	ret
.ball_cut_tree
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr z, .ball
	cp SPRITEMOVEDATA_ARCH_TREE_LEFT
	jr z, .arch_tree
	cp SPRITEMOVEDATA_ARCH_TREE_RIGHT
	jr nz, .no
.arch_tree
	ld a, OVERWORLD_OBJECT_GFX_ARCH_TREE
	scf
	ret
.ball
	ld a, OVERWORLD_OBJECT_GFX_STATIONARY_BALL
	scf
	ret
.blank_fruit
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr z, .no
	cp SPRITEMOVEDATA_POKECOM_NEWS
	jr z, .silver_cave_arch
	cp SPRITEMOVEDATA_ARCH_TREE_RIGHT
	jr nz, .no
.silver_cave_arch
	ld a, OVERWORLD_OBJECT_GFX_SILVER_CAVE_ARCH
	scf
	ret
.book_paper_pokedex
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr z, .book
	cp SPRITEMOVEDATA_STANDING_UP
	jr z, .paper
	cp SPRITEMOVEDATA_STANDING_LEFT
	jr nz, .no
	ld a, OVERWORLD_OBJECT_GFX_POKEDEX
	scf
	ret
.book
	ld a, OVERWORLD_OBJECT_GFX_BOOK
	scf
	ret
.paper
	ld a, OVERWORLD_OBJECT_GFX_PAPER
	scf
	ret
.ice_boulder_fossils
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STRENGTH_BOULDER
	jr z, .ice_boulder
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr z, .ice_boulder
	cp SPRITEMOVEDATA_STANDING_UP
	jr z, .helix_fossil
	cp SPRITEMOVEDATA_STANDING_LEFT
	jr nz, .no
	ld a, OVERWORLD_OBJECT_GFX_DOME_FOSSIL
	scf
	ret
.ice_boulder
	ld a, OVERWORLD_OBJECT_GFX_ICE_BOULDER
	scf
	ret
.helix_fossil
	ld a, OVERWORLD_OBJECT_GFX_HELIX_FOSSIL
	scf
	ret
.boulder
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STANDING_LEFT
	jr z, .pokecom_sign
	cp SPRITEMOVEDATA_SMASHABLE_ROCK
	jr z, .smashable
	cp SPRITEMOVEDATA_STRENGTH_BOULDER
	jr z, .strength
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr nz, .no
.strength
	ld a, OVERWORLD_OBJECT_GFX_STRENGTH_BOULDER
	scf
	ret
.smashable
	ld a, OVERWORLD_OBJECT_GFX_SMASHABLE_ROCK
	scf
	ret
.pokecom_sign
	ld a, OVERWORLD_OBJECT_GFX_POKECOM_SIGN
	scf
	ret
.no
	and a
	ret

OverworldObjectGFXTileCount:
; a = resource ID. Return its exact tile count in a.
	add LOW(.TileCounts)
	ld l, a
	adc HIGH(.TileCounts)
	sub l
	ld h, a
	ld a, [hl]
	ret
.TileCounts
	table_width 1
	db STRENGTH_BOULDER_TILES
	db SMASHABLE_ROCK_TILES
	db STATIONARY_BALL_TILES
	db ARCH_TREE_TILES
	db SILVER_CAVE_ARCH_TILES
	db BOOK_TILES
	db PAPER_TILES
	db POKEDEX_TILES
	db POKECOM_SIGN_TILES
	db ICE_BOULDER_TILES
	db HELIX_FOSSIL_TILES
	db DOME_FOSSIL_TILES
	db CAMPFIRE_TILES
	assert_table_length NUM_OVERWORLD_OBJECT_GFX
