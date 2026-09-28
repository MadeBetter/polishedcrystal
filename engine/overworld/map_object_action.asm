ObjectActionPairPointers:
; entries correspond to OBJECT_ACTION_* constants (see constants/map_object_constants.asm)
	table_width 2 + 2
	;  normal action,                  frozen action
	dw SetFacingStanding,              SetFacingStanding          ; OBJECT_ACTION_00
	dw SetFacingStandAction,           SetFacingCurrent           ; OBJECT_ACTION_STAND
	dw SetFacingStepAction,            SetFacingCurrent           ; OBJECT_ACTION_STEP
	dw SetFacingBumpAction,            SetFacingCurrent           ; OBJECT_ACTION_BUMP
	dw SetFacingCounterclockwiseSpin,  SetFacingCurrent           ; OBJECT_ACTION_SPIN
	dw SetFacingCounterclockwiseSpin2, SetFacingStanding          ; OBJECT_ACTION_SPIN_FLICKER
	dw SetFacingFish,                  SetFacingFish              ; OBJECT_ACTION_FISHING
	dw SetFacingShadow,                SetFacingStanding          ; OBJECT_ACTION_SHADOW
	dw SetFacingEmote,                 SetFacingEmote             ; OBJECT_ACTION_EMOTE
	dw SetFacingBigDollSym,            SetFacingBigDollSym        ; OBJECT_ACTION_BIG_SNORLAX
	dw SetFacingBounce,                SetFacingFreezeBounce      ; OBJECT_ACTION_BOUNCE
	dw SetFacingWeirdTree,             SetFacingCurrent           ; OBJECT_ACTION_WEIRD_TREE
	dw SetFacingBigDoll,               SetFacingBigDoll           ; OBJECT_ACTION_BIG_DOLL
	dw SetFacingBoulderDust,           SetFacingStanding          ; OBJECT_ACTION_BOULDER_DUST
	dw SetFacingGrassShake,            SetFacingStanding          ; OBJECT_ACTION_GRASS_SHAKE
	dw SetFacingPuddleSplash,          SetFacingStanding          ; OBJECT_ACTION_PUDDLE_SPLASH
	dw SetFacingSkyfall,               SetFacingCurrent           ; OBJECT_ACTION_SKYFALL
	dw SetFacingFruit,                 SetFacingFruit             ; OBJECT_ACTION_FRUIT
	dw SetFacingBigGyarados,           SetFacingFreezeBigGyarados ; OBJECT_ACTION_BIG_GYARADOS
	dw SetFacingStandFlip,             SetFacingStandFlip         ; OBJECT_ACTION_STAND_FLIP
	dw SetFacingMuseumDrill,           SetFacingMuseumDrill       ; OBJECT_ACTION_MUSEUM_DRILL
	dw SetFacingRun,                   SetFacingCurrent           ; OBJECT_ACTION_RUN
	dw SetFacingSailboatTop,           SetFacingSailboatTop       ; OBJECT_ACTION_SAILBOAT_TOP
	dw SetFacingSailboatBottom,        SetFacingSailboatBottom    ; OBJECT_ACTION_SAILBOAT_BOTTOM
	dw SetFacingAlolanExeggutor,       SetFacingAlolanExeggutor   ; OBJECT_ACTION_ALOLAN_EXEGGUTOR
	dw SetFacingShakeExeggutor,        SetFacingAlolanExeggutor   ; OBJECT_ACTION_SHAKE_EXEGGUTOR
	dw SetFacingTinyWindows,           SetFacingTinyWindows       ; OBJECT_ACTION_TINY_WINDOWS
	dw SetFacingBigHoOh,               SetFacingFreezeBigHoOh     ; OBJECT_ACTION_BIG_HO_OH
	dw SetFacingBigLugia,              SetFacingFreezeBigLugia    ; OBJECT_ACTION_BIG_LUGIA
	dw SetFacingCutTree,               SetFacingCutTree           ; OBJECT_ACTION_CUT_TREE
	dw SetFacingUnownEye,              SetFacingFreezeUnownEye    ; OBJECT_ACTION_UNOWN_EYE
	assert_table_length NUM_OBJECT_ACTIONS

SetFacingStanding:
	ld a, STANDING
	jp SetFixedFacing

SetFacingShadow:
	ld a, [wOptions3]
	bit NO_SHADOW_BLENDING, a
	jr nz, .solid
	ldh a, [hVBlankCounter]
	and 1
	ld a, STANDING
	jp nz, SetFixedFacing
	.solid
	ld a, FACING_SHADOW
	jp SetFixedFacing

SetFacingCutTree:
	ld a, [bc] ; OBJECT_SPRITE
	cp SPRITE_BALL_CUT_TREE
	ld a, FACING_CUT_TREE
	jp z, SetFixedFacing
	ld a, [bc]
	cp SPRITE_PEARL
	ld a, FACING_COMPACT_FARAWAY_ROCK
	jp z, SetFixedFacing
	ld a, FACING_FARAWAY_ROCK
	jp SetFixedFacing

SetFacingCurrent:
	; Compact object graphics have dynamic tile bases. Select their facing from
	; object identity and movement instead of assigning meaning to an address.
	ld a, [bc] ; OBJECT_SPRITE
	cp SPRITE_CAMPFIRE
	jp z, .compact_2x2
	cp SPRITE_FLOATING_BALL
	jp z, .floating_ball
	cp SPRITE_ICE_BOULDER_FOSSILS
	jp z, .ice_boulder_fossils
	cp SPRITE_BOULDER_ROCK
	jp z, .boulder
	cp SPRITE_BALL_CUT_TREE
	jr z, .ball_cut_tree
	cp SPRITE_BLANK_FRUIT
	jr z, .blank_fruit
	cp SPRITE_BOOK_PAPER_POKEDEX
	jp z, .book_paper_pokedex
	cp SPRITE_WEIRD_TREE
	jr z, .weird_tree
	cp SPRITE_SNES
	jp c, .normal
	cp SPRITE_GOLD_TROPHY + 1
	jr c, .console_or_trophy
	cp SPRITE_PEARL
	jp nz, .normal
	jp .compact_2x2
.console_or_trophy
	cp SPRITE_SNES
	jr z, .snes
	cp SPRITE_GAMECUBE
	jr z, .gamecube
	jp .compact_2x2
.snes
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STILL
	jr nz, .compact_2x2
	ld a, FACING_COMPACT_MIRROR_2X2
	jp SetFixedFacing
.gamecube
	ld a, FACING_COMPACT_TOP_MIRROR_3
	jp SetFixedFacing
.weird_tree
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STANDING_LEFT
	jr z, .caitlin
	cp SPRITEMOVEDATA_SUDOWOODO
	jp nz, .normal
	ld a, FACING_COMPACT_WEIRD_TREE_0
	jp SetFixedFacing
.caitlin
	ld a, FACING_COMPACT_MIRROR_2X2
	jp SetFixedFacing
.floating_ball
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_POKECOM_NEWS
	jr z, .compact_2x2
	cp SPRITEMOVEDATA_POKEMON
	jr nz, .normal
	ld a, FACING_COMPACT_FLOATING_BALL_0
	jp SetFixedFacing
.ball_cut_tree
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr nz, .normal
	ld a, FACING_STATIONARY_BALL
	jp SetFixedFacing
.blank_fruit
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STANDING_DOWN
	ld a, STANDING
	jp z, SetFixedFacing
	ld a, [hl]
	cp SPRITEMOVEDATA_POKECOM_NEWS
	ld a, FACING_COMPACT_SILVER_CAVE_ARCH
	jp z, SetFixedFacing
	jr .normal
.ice_boulder_fossils
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STRENGTH_BOULDER
	jr z, .compact_2x2
	sub SPRITEMOVEDATA_STANDING_DOWN
	cp SPRITEMOVEDATA_STANDING_LEFT - SPRITEMOVEDATA_STANDING_DOWN + 1
	jp nc, .normal
.compact_2x2
	ld a, FACING_COMPACT_2X2
	jp SetFixedFacing
.book_paper_pokedex
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	sub SPRITEMOVEDATA_STANDING_DOWN
	cp SPRITEMOVEDATA_STANDING_LEFT - SPRITEMOVEDATA_STANDING_DOWN + 1
	jp nc, .normal
	jr .compact_2x2
.boulder
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_STANDING_LEFT
	ld a, FACING_COMPACT_2X2
	jp z, SetFixedFacing
	ld a, [hl]
	cp SPRITEMOVEDATA_SMASHABLE_ROCK
	ld a, FACING_SMASHABLE_ROCK
	jp z, SetFixedFacing
	ld a, [hl]
	cp SPRITEMOVEDATA_STRENGTH_BOULDER
	jr z, .strength
	cp SPRITEMOVEDATA_STANDING_DOWN
	jr nz, .normal
.strength
	ld a, FACING_STRENGTH_BOULDER
	jr SetFixedFacing
.normal
	call GetSpriteDirection
	jr SetFixedFacing

SetFacingEmote:
	ld a, FACING_EMOTE
	jr SetFixedFacing

SetFacingSailboatTop:
	ld a, FACING_SAILBOAT_TOP
	jr SetFixedFacing

SetFacingSailboatBottom:
	ld a, FACING_SAILBOAT_BOTTOM
	jr SetFixedFacing

SetFacingAlolanExeggutor:
	ld a, FACING_ALOLAN_EXEGGUTOR_0
	jr SetFixedFacing

SetFacingBigDoll:
	ld a, [wVariableSprites + SPRITE_BIG_DOLL - SPRITE_VARS]
	cp SPRITE_BIG_ONIX
	ld a, FACING_BIG_DOLL_ASYM
	jr z, SetFixedFacing
SetFacingBigDollSym:
	ld a, FACING_BIG_DOLL_SYM
	jr SetFixedFacing

SetFacingFish:
	call GetSpriteDirection
	rrca
	rrca
	add FACING_FISH_DOWN
	jr SetFixedFacing

SetFacingMuseumDrill:
	ld a, [bc] ; OBJECT_SPRITE
	cp SPRITE_BALL_CUT_TREE
	jr z, .arch_tree
	cp SPRITE_PEARL
	jr z, .pearl_arch
	cp SPRITE_BLANK_FRUIT
	jr nz, .normal
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	cp SPRITEMOVEDATA_ARCH_TREE_RIGHT
	ld a, FACING_COMPACT_SILVER_CAVE_ARCH_RIGHT
	jr z, SetFixedFacing
	jr .normal
.arch_tree
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	sub SPRITEMOVEDATA_ARCH_TREE_LEFT
	cp 2
	jr nc, .normal
	add FACING_COMPACT_ARCH_TREE_LEFT
	jr SetFixedFacing
.pearl_arch
	ld hl, OBJECT_MOVEMENT_TYPE
	add hl, bc
	ld a, [hl]
	sub SPRITEMOVEDATA_ARCH_TREE_LEFT
	cp 2
	jr nc, .normal
	add FACING_COMPACT_PEARL_ARCH_LEFT
	jr SetFixedFacing
.normal
	call GetSpriteDirection
	rrca
	rrca
	add FACING_MUSEUM_DRILL_DOWN
	jr SetFixedFacing

SetFacingTinyWindows:
	ld hl, OBJECT_RADIUS
	add hl, bc
	ld a, [hl]
	add FACING_TINY_WINDOWS_0 - $11
	jr SetFixedFacing

SetFacingStandFlip:
	call GetSpriteDirection
	rrca
	rrca
	add FACING_STEP_DOWN_FLIP
SetFixedFacing:
	ld hl, OBJECT_FACING
	add hl, bc
	ld [hl], a
	ret

SetFacingStandAction:
	ld hl, OBJECT_FACING
	add hl, bc
	ld a, [hl]
	and 1
	jp z, SetFacingCurrent
	; fallthrough
SetFacingStepAction:
SetFacingBumpAction:
	ld hl, OBJECT_FLAGS1
	add hl, bc
	bit SLIDING_F, [hl]
	jp nz, SetFacingCurrent

	call _GetNextStepFrame
	rrca
	rrca
	rrca
	and %11
	ld d, a
	call GetSpriteDirection
	or d
	ld hl, OBJECT_FACING
	add hl, bc
	ld [hl], a
	ret

SetFacingSkyfall:
	ld hl, OBJECT_FLAGS1
	add hl, bc
	bit SLIDING_F, [hl]
	jmp nz, SetFacingCurrent

	ld hl, OBJECT_STEP_FRAME
	add hl, bc
	ld a, [hl]
	add 2
	ld [hl], a
	rrca
	rrca
	rrca
	and %11
	ld d, a

	call GetSpriteDirection
	or d
	jr SetFixedFacing

SetFacingCounterclockwiseSpin:
	call CounterclockwiseSpinAction
	ld hl, OBJECT_DIRECTION
	add hl, bc
	ld a, [hl]
	jr SetFixedFacing

SetFacingCounterclockwiseSpin2:
	call CounterclockwiseSpinAction
	jmp SetFacingStanding

CounterclockwiseSpinAction:
	ld hl, OBJECT_STEP_FRAME
	add hl, bc
	ld a, [hl]
	and %11110000
	ld e, a

	ld a, [hl]
	inc a
	and %00001111
	ld d, a
	cp 2
	jr c, .ok

	ld d, 0
	ld a, e
	add $10
	and %00110000
	ld e, a

.ok
	ld a, d
	or e
	ld [hl], a

	swap e
	ld d, 0
	ld hl, .Directions
	add hl, de
	ld a, [hl]
	ld hl, OBJECT_DIRECTION
	add hl, bc
	ld [hl], a
	ret

.Directions
	db OW_DOWN, OW_RIGHT, OW_UP, OW_LEFT

AlternateStepFrame:
	ld hl, OBJECT_STEP_FRAME
	add hl, bc
	ld a, [hl]
	inc a
	and %00011111
	ld [hl], a
	and %00010000
	ret

SetFacingBounce:
	ld a, [bc] ; OBJECT_SPRITE
	cp SPRITE_CAMPFIRE
	jp z, SetFacingCampfire
	cp SPRITE_FLOATING_BALL
	jp z, SetFacingFloatingBall
	call AlternateStepFrame
	ld a, FACING_STEP_UP_0
	jmp nz, SetFixedFacing
SetFacingFreezeBounce:
	ld a, [bc] ; OBJECT_SPRITE
	cp SPRITE_FLOATING_BALL
	ld a, FACING_COMPACT_FLOATING_BALL_0
	jmp z, SetFixedFacing
	xor a ; FACING_STEP_DOWN_0
	jmp SetFixedFacing
SetFacingCampfire:
	call AlternateStepFrame
	ld a, FACING_COMPACT_CAMPFIRE_FLIP
	jmp nz, SetFixedFacing
	ld a, FACING_COMPACT_2X2
	jmp SetFixedFacing
SetFacingFloatingBall:
	call AlternateStepFrame
	ld a, FACING_COMPACT_FLOATING_BALL_1
	jmp nz, SetFixedFacing
	ld a, FACING_COMPACT_FLOATING_BALL_0
	jmp SetFixedFacing

SetFacingFreezeUnownEye:
	ld e, 0
	jr SetFacingUnownEye_Select
SetFacingUnownEye:
	call AlternateStepFrame
	ld e, 0
	jr z, SetFacingUnownEye_Select
	inc e
SetFacingUnownEye_Select:
	ld a, [bc] ; OBJECT_SPRITE
	sub SPRITE_GAMECUBE
	add a
	add e
	ld e, a
	ld d, 0
	ld hl, SetFacingUnownEye_Facings
	add hl, de
	ld a, [hl]
	jmp SetFixedFacing
SetFacingUnownEye_Facings:
	db FACING_COMPACT_MIRROR_2X2, FACING_COMPACT_UNOWN_A_CLOSED
	db FACING_COMPACT_MIRROR_2X2, FACING_COMPACT_UNOWN_W_CLOSED
	db FACING_COMPACT_2X2, FACING_COMPACT_UNOWN_P_CLOSED
	db FACING_COMPACT_TOP_MIRROR_3, FACING_COMPACT_UNOWN_R_CLOSED

SetFacingFruit:
	ld hl, OBJECT_RADIUS
	add hl, bc
	ld e, [hl]
	push bc
	ld hl, wFruitTreeFlags
	ld d, 0
	ld b, CHECK_FLAG
	push de
	call FlagAction
	pop de
	pop bc
	and a ; 0 = show fruit, 1 = hide fruit
	ld a, FACING_PICKED_FRUIT
	jr nz, .ok
	ld a, e
	cp FIRST_BERRY_TREE - 1
	; a = carry ? FACING_APRICORN : FACING_BERRY
	assert FACING_APRICORN + 1 == FACING_BERRY
	sbc a
	add FACING_BERRY
.ok
	jmp SetFixedFacing

SetFacingBigGyarados:
	call AlternateStepFrame
	ld a, FACING_BIG_GYARADOS_2
	jmp nz, SetFixedFacing
SetFacingFreezeBigGyarados:
	ld a, FACING_BIG_GYARADOS_1
	jmp SetFixedFacing

SetFacingBigHoOh:
	call AlternateStepFrame
	ld a, FACING_BIG_HO_OH_2
	jmp nz, SetFixedFacing
SetFacingFreezeBigHoOh:
	ld a, FACING_BIG_HO_OH_1
	jmp SetFixedFacing

SetFacingBigLugia:
	call AlternateStepFrame
	ld a, FACING_BIG_LUGIA_2
	jmp nz, SetFixedFacing
SetFacingFreezeBigLugia:
	ld a, FACING_BIG_LUGIA_1
	jmp SetFixedFacing

SetFacingShakeExeggutor:
	call _GetNextStepFrame
	and %110000
	swap a
	add FACING_ALOLAN_EXEGGUTOR_0
	jmp SetFixedFacing

SetFacingWeirdTree:
	call _GetNextStepFrame
	and %1100
	rrca
	rrca
	ld d, a
	ld a, [bc] ; OBJECT_SPRITE
	cp SPRITE_WEIRD_TREE
	ld a, d
	jr nz, .original
	add FACING_COMPACT_WEIRD_TREE_0
	jmp SetFixedFacing
.original
	add FACING_WEIRD_TREE_0
	jmp SetFixedFacing

SetFacingBoulderDust:
	call _GetNextStepFrame
	and %10
	ld a, FACING_BOULDER_DUST_1
	jr z, .ok
	inc a ; FACING_BOULDER_DUST_2
.ok
	jmp SetFixedFacing

SetFacingGrassShake:
	call _GetNextStepFrame
	and %100
	ld a, FACING_GRASS_1
	jr z, .ok
	inc a ; FACING_GRASS_2
.ok
	jmp SetFixedFacing

SetFacingPuddleSplash:
	call _GetNextStepFrame
	and %100
	ld a, FACING_SPLASH_1
	jr z, .ok
	inc a ; FACING_SPLASH_2
.ok
	jmp SetFixedFacing

SetFacingRun:
	ld hl, OBJECT_FLAGS1
	add hl, bc
	bit SLIDING_F, [hl]
	jmp nz, SetFacingCurrent

	call _GetNextStepFrame
	rrca
	rrca
	and %11
	ld d, a
	call GetSpriteDirection
	or d
	ld hl, OBJECT_FACING
	add hl, bc
	ld [hl], a
	ret

_GetNextStepFrame:
	ld hl, OBJECT_STEP_FRAME
	add hl, bc
	inc [hl]
	ld a, [hl]
	ret
