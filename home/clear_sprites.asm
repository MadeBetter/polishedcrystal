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
; Skip overworld OAM rebuilds while either trainer color layer is visible.
	ld a, [wPlayerBackpicVisible]
	and a
	ret nz
	ld a, [wTrainerSpriteVisible]
	and a
	ret nz
	farjp _UpdateSprites

ClearOAMSprites_PreserveColorLayer::
; Clear only the contiguous OAM range not occupied by visible trainer layers.
	ld a, [wPlayerBackpicVisible]
	and a
	jr z, .player_hidden

	; Both layers fill OAM, so there is no animation range to clear.
	ld a, [wTrainerSpriteVisible]
	and a
	ret nz

	; Only the player layer is visible: clear the range after it.
	ld hl, wShadowOAM + PLAYER_COLOR_LAYER_OAM_COUNT * OBJ_SIZE
	ld bc, TRAINER_COLOR_LAYER_OAM_COUNT * OBJ_SIZE
	xor a
	rst ByteFill
	ret

.player_hidden
	ld a, [wTrainerSpriteVisible]
	and a
	jr z, .clear_all

	; Only the enemy trainer layer is visible: clear the range before it.
	ld hl, wShadowOAM
	ld bc, PLAYER_COLOR_LAYER_OAM_COUNT * OBJ_SIZE
	xor a
	rst ByteFill
	ret

.clear_all
	jmp ClearSprites
