LoadTrainerPalette_White_Col1_Col2_Black_Far:
; a = source bank, hl = palette (2 colors), de = destination in GBC Video WRAM
	ld b, a
	ldh a, [rWBK]
	push af
	ld a, BANK("GBC Video")
	ldh [rWBK], a

if !DEF(MONOCHROME)
	ld a, $ff ; RGB 31,31,31
	ld [de], a
	inc de
	ld [de], a
	inc de
else
	ld a, LOW(PAL_MONOCHROME_WHITE)
	ld [de], a
	inc de
	ld a, HIGH(PAL_MONOCHROME_WHITE)
	ld [de], a
	inc de
endc

	ld a, b
	ld bc, 2 * 2
	call FarCopyBytesToColorWRAM

if !DEF(MONOCHROME)
	xor a ; RGB 00, 00, 00
	ld [de], a
	inc de
	ld [de], a
	inc de
else
	ld a, LOW(PAL_MONOCHROME_BLACK)
	ld [de], a
	inc de
	ld a, HIGH(PAL_MONOCHROME_BLACK)
	ld [de], a
	inc de
endc

	pop af
	ldh [rWBK], a
	ret

SetBattlePal_EnemyBG_Far::
	; Default: use enemy Pokemon palette
	farcall SetBattlePal_Enemy
	ret

SetBattlePal2_EnemyBG_Far::
	ld a, [wOtherTrainerClass]
	cp LYRA1
	jr z, .lyra1
	cp RIVAL1
	jr z, .rival1
	cp RIVAL0
	jr z, .rival1
	cp YOUNGSTER
	jr z, .youngster
	cp BUG_CATCHER
	jr z, .bugcatcher
	cp COOLTRAINERM
	jr z, .cooltrainerm
	cp SAGE
	jr z, .sage
	cp ELDER
	jr z, .elder
	cp SCHOOLGIRL
	jr z, .schoolgirl
	cp BIRD_KEEPER
	jr z, .birdkeeper
	; Add more trainers here as needed

	; Default: use status palette
	farcall SetBattlePal_Status
	ret

.lyra1:
	ld hl, Lyra1BGColor2Palette
	ld a, BANK(Lyra1BGColor2Palette)
	jr .load

.rival1:
	ld hl, Rival1BGColor2Palette
	ld a, BANK(Rival1BGColor2Palette)
	jr .load

.youngster:
	ld hl, YoungsterBGColor2Palette
	ld a, BANK(YoungsterBGColor2Palette)
	jr .load
	
.bugcatcher:
	ld hl, BugCatcherBGColor2Palette
	ld a, BANK(BugCatcherBGColor2Palette)
	jr .load

.cooltrainerm:
	ld hl, CooltrainerMBGColor2Palette
	ld a, BANK(CooltrainerMBGColor2Palette)
	jr .load

.sage:
	ld hl, SageBGColor2Palette
	ld a, BANK(SageBGColor2Palette)
	jr .load

.elder:
	ld hl, ElderBGColor2Palette
	ld a, BANK(ElderBGColor2Palette)
	jr .load

.schoolgirl:
	ld hl, SchoolgirlBGColor2Palette
	ld a, BANK(SchoolgirlBGColor2Palette)
	jr .load

.birdkeeper:
	ld hl, BirdKeeperBGColor2Palette
	ld a, BANK(BirdKeeperBGColor2Palette)
	; fallthrough
.load:
	jp LoadTrainerPalette_White_Col1_Col2_Black_Far

SetEnemyTrainerOAMPalettes_Far::
	ld a, [wOtherTrainerClass]
	ld c, a
	ld de, TrainerOAMPaletteSetTable

.loop:
	ld a, [de]
	cp $FF
	jr z, .default
	cp c
	jr z, .found

	; Skip this entry (10 bytes: 1 class + 1 bank + 8 pointer bytes)
	ld a, e
	add 10
	ld e, a
	ld a, d
	adc 0
	ld d, a
	jr .loop

.found:
	inc de
	ld a, [de]
	ld b, a
	inc de

	; Load Color 1 palette (OBJ slot 0)
	ld a, [de]
	ld l, a
	inc de
	ld a, [de]
	ld h, a
	inc de
	push de
	ld a, b
	ld de, wOBPals1 palette PAL_BATTLE_OB_ENEMY
	push bc
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM
	pop bc
	pop de

	; Load Color 2 palette (OBJ slot 2)
	ld a, [de]
	ld l, a
	inc de
	ld a, [de]
	ld h, a
	inc de
	push de
	ld a, b
	ld de, wOBPals1 palette 2
	push bc
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM
	pop bc
	pop de

	; Load Color 3 palette (OBJ slot 6)
	ld a, [de]
	ld l, a
	inc de
	ld a, [de]
	ld h, a
	inc de
	push de
	ld a, b
	ld de, wOBPals1 palette 6
	push bc
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM
	pop bc
	pop de

	; Load Color 4 palette (OBJ slot 7)
	ld a, [de]
	ld l, a
	inc de
	ld a, [de]
	ld h, a
	ld a, b
	ld de, wOBPals1 palette 7
	push bc
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM
	pop bc
	ret

.default:
	; Color 1: use enemy Pokemon palette (slot 0)
	ld de, wOBPals1 palette PAL_BATTLE_OB_ENEMY
	farcall SetBattlePal_Enemy

	; Color 2: gray palette (slot 2)
	ld hl, BattleObjectPals + 4 palettes
	ld a, BANK(BattleObjectPals)
	ld de, wOBPals1 palette 2
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM

	; Color 3: gray palette (slot 6)
	ld hl, BattleObjectPals + 5 palettes
	ld a, BANK(BattleObjectPals)
	ld de, wOBPals1 palette 6
	ld bc, 1 palettes
	call FarCopyBytesToColorWRAM

	; Color 4: gray palette (slot 7)
	ld hl, BattleObjectPals + 6 palettes
	ld a, BANK(BattleObjectPals)
	ld de, wOBPals1 palette 7
	ld bc, 1 palettes
	jmp FarCopyBytesToColorWRAM

Lyra1BGColor2Palette:
INCLUDE "gfx/trainers/colorized/lyra1/bg_secondary.pal"

Lyra1OAMColorPalette:
INCLUDE "gfx/trainers/colorized/lyra1/oam.pal"

Rival1BGColor2Palette:
INCLUDE "gfx/trainers/colorized/rival1/bg_secondary.pal"

Rival1OAMColorPalette:
INCLUDE "gfx/trainers/colorized/rival1/oam.pal"

YoungsterBGColor2Palette:
INCLUDE "gfx/trainers/colorized/youngster/bg_secondary.pal"

YoungsterOAMColorPalette:
INCLUDE "gfx/trainers/colorized/youngster/oam.pal"

BugCatcherBGColor2Palette:
INCLUDE "gfx/trainers/colorized/bug_catcher/bg_secondary.pal"

BugCatcherOAMColorPalette:
INCLUDE "gfx/trainers/colorized/bug_catcher/oam.pal"

CooltrainerMOAMColorPalette:
INCLUDE "gfx/trainers/colorized/cooltrainer_m/oam.pal"

CooltrainerMBGColor2Palette:
INCLUDE "gfx/trainers/colorized/cooltrainer_m/bg_secondary.pal"

SageBGColor2Palette:
INCLUDE "gfx/trainers/colorized/sage/bg_secondary.pal"

SageOAMColorPalette:
INCLUDE "gfx/trainers/colorized/sage/oam.pal"

ElderBGColor2Palette:
INCLUDE "gfx/trainers/colorized/elder/bg_secondary.pal"

ElderOAMColorPalette:
INCLUDE "gfx/trainers/colorized/elder/oam.pal"

SchoolgirlBGColor2Palette:
INCLUDE "gfx/trainers/colorized/schoolgirl/bg_secondary.pal"

SchoolgirlOAMColorPalette:
INCLUDE "gfx/trainers/colorized/schoolgirl/oam.pal"

BirdKeeperBGColor2Palette:
INCLUDE "gfx/trainers/colorized/bird_keeper/bg_secondary.pal"

BirdKeeperOAMColorPalette:
INCLUDE "gfx/trainers/colorized/bird_keeper/oam.pal"

TrainerOAMPaletteSetTable:
; Format: db trainer_class, bank, dw pal1, dw pal2, dw pal3, dw pal4
; Each entry is 10 bytes: 1 byte class + 1 byte bank + 8 bytes (4 pointers)
; Each trainer's oam.pal stores those four palettes consecutively.
	db LYRA1, BANK(Lyra1OAMColorPalette)
	dw Lyra1OAMColorPalette
	dw Lyra1OAMColorPalette + 1 palettes
	dw Lyra1OAMColorPalette + 2 palettes
	dw Lyra1OAMColorPalette + 3 palettes

	db RIVAL0, BANK(Rival1OAMColorPalette)
	dw Rival1OAMColorPalette
	dw Rival1OAMColorPalette + 1 palettes
	dw Rival1OAMColorPalette + 2 palettes
	dw Rival1OAMColorPalette + 3 palettes

	db RIVAL1, BANK(Rival1OAMColorPalette)
	dw Rival1OAMColorPalette
	dw Rival1OAMColorPalette + 1 palettes
	dw Rival1OAMColorPalette + 2 palettes
	dw Rival1OAMColorPalette + 3 palettes

	db YOUNGSTER, BANK(YoungsterOAMColorPalette)
	dw YoungsterOAMColorPalette
	dw YoungsterOAMColorPalette + 1 palettes
	dw YoungsterOAMColorPalette + 2 palettes
	dw YoungsterOAMColorPalette + 3 palettes

	db BUG_CATCHER, BANK(BugCatcherOAMColorPalette)
	dw BugCatcherOAMColorPalette
	dw BugCatcherOAMColorPalette + 1 palettes
	dw BugCatcherOAMColorPalette + 2 palettes
	dw BugCatcherOAMColorPalette + 3 palettes

	db COOLTRAINERM, BANK(CooltrainerMOAMColorPalette)
	dw CooltrainerMOAMColorPalette
	dw CooltrainerMOAMColorPalette + 1 palettes
	dw CooltrainerMOAMColorPalette + 2 palettes
	dw CooltrainerMOAMColorPalette + 3 palettes

	db SAGE, BANK(SageOAMColorPalette)
	dw SageOAMColorPalette
	dw SageOAMColorPalette + 1 palettes
	dw SageOAMColorPalette + 2 palettes
	dw SageOAMColorPalette + 3 palettes

	db ELDER, BANK(ElderOAMColorPalette)
	dw ElderOAMColorPalette
	dw ElderOAMColorPalette + 1 palettes
	dw ElderOAMColorPalette + 2 palettes
	dw ElderOAMColorPalette + 3 palettes

	db SCHOOLGIRL, BANK(SchoolgirlOAMColorPalette)
	dw SchoolgirlOAMColorPalette
	dw SchoolgirlOAMColorPalette + 1 palettes
	dw SchoolgirlOAMColorPalette + 2 palettes
	dw SchoolgirlOAMColorPalette + 3 palettes

	db BIRD_KEEPER, BANK(BirdKeeperOAMColorPalette)
	dw BirdKeeperOAMColorPalette
	dw BirdKeeperOAMColorPalette + 1 palettes
	dw BirdKeeperOAMColorPalette + 2 palettes
	dw BirdKeeperOAMColorPalette + 3 palettes

	db $FF  ; Terminator
