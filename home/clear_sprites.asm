ClearSprites::
; Erase OAM data
	ld hl, wShadowOAM
	ld bc, wShadowOAMEnd - wShadowOAM
	xor a
	rst ByteFill
	ret

ClearNormalSprites::
	ldh a, [hUsedOAMIndex]
	ld l, a              ; l = start offset (e.g. 76 for slot 19)
	; Calculate byte count: OAM_SIZE - hUsedOAMIndex
	ld a, OAM_SIZE
	sub l
	ld c, a              ; c = byte count (e.g. 160-92 = 68 bytes)
	ld h, HIGH(wShadowOAM)  ; h = $c1
	; hl now points to wShadowOAM + hUsedOAMIndex
	xor a
	ld b, a
	rst ByteFill
	ret

HideSprites::
; Set all OAM y-positions to 160 to hide them offscreen
	ld hl, wShadowOAM
	ld b, OAM_COUNT
HideSpritesInRange::
	ld de, OBJ_SIZE
	ld a, OAM_YCOORD_HIDDEN
.loop
	ld [hl], a
	add hl, de
	dec b
	jr nz, .loop
	ret

HidePlayerSprite::
; Set player sprite to 160 to hide it offscreen
	ld h, HIGH(wShadowOAM)
	ld a, [wPlayerCurrentOAMSlot]
	ld l, a
	ld de, OBJ_SIZE
	ld b, 4
	ld a, OAM_YCOORD_HIDDEN
.loop
	ld [hl], a
	add hl, de
	dec b
	jr nz, .loop
	ret


FadeToMenu_BackupSprites::
	call FadeToMenu
BackupSprites::
; Copy wShadowOAM to wShadowOAMBackup
	ldh a, [rWBK]
	push af
	ld a, BANK(wShadowOAMBackup)
	ldh [rWBK], a
	ld hl, wShadowOAM
	ld de, wShadowOAMBackup
	ld bc, wShadowOAMEnd - wShadowOAM
	rst CopyBytes
	pop af
	ldh [rWBK], a
	ret

RestoreSprites::
	; Copy wShadowOAMBackup to wShadowOAM
	ldh a, [rWBK]
	push af
	ld a, BANK(wShadowOAMBackup)
	ldh [rWBK], a
	ld hl, wShadowOAMBackup
	ld de, wShadowOAM
	ld bc, wShadowOAMEnd - wShadowOAM
	rst CopyBytes
	pop af
	ldh [rWBK], a
	ret

UpdateSprites_PreserveColorLayer::
; Wrapper for _UpdateSprites that preserves color layer OAM (slots 0-18) during battle
; When player's back pic is visible, this skips OAM rebuild to avoid clearing color layer
; Otherwise calls _UpdateSprites normally for overworld sprite updates
	ld a, [wPlayerBackpicVisible]
	and a
	ret nz  ; If back pic visible, skip _UpdateSprites to preserve color layer
	farcall _UpdateSprites
	ret

ClearOAMSprites_PreserveColorLayer::
; Check if Pokemon are battling first (most common case)
; If both species loaded: clear all OAM for animations
; Otherwise: check visibility flags for intro sequences

	; Check if both Pokemon are on screen (species != 0)
	ld a, [wBattleMonSpecies]
	and a
	jr z, .check_visibility_flags  ; Player Pokemon not on screen

	ld a, [wEnemyMonSpecies]
	and a
	jr z, .check_visibility_flags  ; Enemy Pokemon not on screen

	; Both Pokemon battling - clear all OAM
	jmp ClearSprites

.check_visibility_flags
	; Intro/transition - check visibility flags
	ld a, [wPlayerBackpicVisible]
	and a
	jr z, .check_trainer

	; Player is visible, so we must preserve OAM slots 0-18.
	; Battle animations use slots 19-39, so those should be cleared.
	; The trainer color layer also uses slots 19-39, but if a battle
	; animation was just playing, it would have overwritten the trainer's
	; graphics anyway, so it's safe to clear.
	ld hl, wShadowOAM + 19 * 4
	ld bc, (OAM_COUNT - 19) * 4
	xor a
	rst ByteFill
	ret

.check_trainer
	ld a, [wTrainerSpriteVisible]
	and a
	jr z, .clear_all

	; Only trainer - clear 0-18
	ld hl, wShadowOAM
	ld bc, 19 * 4
	xor a
	rst ByteFill
	ret

.clear_all
	jmp ClearSprites
