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
; Clear OAM sprites while preserving color layer when player back pic is visible
; - If back pic visible: clear only animation slots 19-39 (21 sprites)
; - Otherwise: clear all OAM sprites (slots 0-39)
	ld a, [wPlayerBackpicVisible]
	and a
	jr z, .clear_all
	; Clear only animation OAM slots (19-39)
	ld hl, wShadowOAM + 19 * 4
	ld bc, (OAM_COUNT - 19) * 4  ; 21 sprites * 4 bytes = 84 bytes
	xor a
	rst ByteFill
	ret
.clear_all
	; Clear all OAM sprites
	jmp ClearSprites
