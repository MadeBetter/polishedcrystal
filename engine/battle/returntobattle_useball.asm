_ReturnToBattle_UseBall:
	call ClearBGPalettes
	call ClearTileMap
	ld a, [wBattleType]
	cp BATTLETYPE_TUTORIAL
	jr z, .gettutorialbackpic
	farcall GetMonBackpic
	jr .continue

.gettutorialbackpic
	farcall GetTrainerBackpic
	; Reload color layer OAM sprites for Lyra
	farcall CreateLyraColorLayerOAM
.continue
	farcall GetMonFrontpic
	farcall _LoadBattleFontsHPBar
	call GetMemCGBLayout
	call CloseWindow
	call LoadStandardMenuHeader
	call ApplyTilemapInVBlank
	call SetDefaultBGPAndOBP
	farcall LoadPlayerStatusIcon
	farcall LoadEnemyStatusIcon
	farjp FinishBattleAnim
