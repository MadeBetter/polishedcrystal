VioletOutskirts_MapScriptHeader:
	def_scene_scripts

	def_callbacks
	callback MAPCALLBACK_TILES, VioletOutskirtsAvalanche
	callback MAPCALLBACK_CMDQUEUE, VioletOutskirtsSetUpPaletteSwap

	def_warp_events
	warp_event  9, 12, HIDDEN_TREE_GROTTO, 1
	warp_event 21,  9, VIOLET_OUTSKIRTS_HOUSE, 1

	def_coord_events

	def_bg_events
	bg_event  8, 11, BGEVENT_JUMPSTD, treegrotto, HIDDENGROTTO_VIOLET_OUTSKIRTS
	bg_event  9, 11, BGEVENT_JUMPSTD, treegrotto, HIDDENGROTTO_VIOLET_OUTSKIRTS
	bg_event 19,  9, BGEVENT_JUMPTEXT, VioletOutskirtsCemeterySignText
	bg_event 25,  8, BGEVENT_JUMPTEXT, VioletOutskirtsHeadstoneText
	bg_event 27,  8, BGEVENT_JUMPTEXT, VioletOutskirtsHeadstoneText
	bg_event 29,  8, BGEVENT_JUMPTEXT, VioletOutskirtsHeadstoneText
	bg_event 31,  8, BGEVENT_JUMPTEXT, VioletOutskirtsHeadstoneText
	bg_event 25, 10, BGEVENT_JUMPTEXT, VioletOutskirtsHeadstoneText
	bg_event 27, 10, BGEVENT_JUMPTEXT, VioletOutskirtsHeadstoneText
	bg_event 29, 10, BGEVENT_JUMPTEXT, VioletOutskirtsHeadstoneText
	bg_event 31, 10, BGEVENT_JUMPTEXT, VioletOutskirtsHeadstoneText

	def_object_events
	object_event 16, -2, SPRITE_MON_ICON, SPRITEMOVEDATA_POKEMON, 0, SUICUNE, -1, PAL_MON_AZURE, OBJECTTYPE_SCRIPT, NO_FORM, ObjectEvent, EVENT_SAW_SUICUNE_ON_ROUTE_42
	; Keep the Rawst Berry on the small tree in the western clearing.
	fruittree_event  2,  9, FRUITTREE_VIOLET_OUTSKIRTS, RAWST_BERRY, PAL_NPC_TEAL
	fruittree_event 17, -2, FRUITTREE_ROUTE_42_1, PNK_APRICORN, PAL_NPC_PINK
	fruittree_event 18, -2, FRUITTREE_ROUTE_42_2, GRN_APRICORN, PAL_NPC_GREEN
	fruittree_event 19, -2, FRUITTREE_ROUTE_42_3, YLW_APRICORN, PAL_NPC_ENV_YELLOW
	cuttree_event 14, -5, EVENT_ROUTE_42_CUT_TREE
	; Mirror Violet City's item at (14,6), now 18 tiles below this map.
	itemball_event 14, 24, PP_UP, 1, EVENT_VIOLET_CITY_PP_UP

VioletOutskirtsAvalanche:
	callasm VioletOutskirtsPrepareNorthConnection
	checkevent EVENT_GOT_HM05_WHIRLPOOL
	iftruefwd .end
	changeblock 4, -2, $1f
	changeblock 6, -2, $1f
.end
	endcallback

VioletOutskirtsSetUpPaletteSwap:
	usepaletteswap .PaletteSwap
	endcallback

.PaletteSwap:
	; Retain the reference's bright red flowers and violet cottage roofs.
	paletteswap 0, 255, 0, 255, PAL_BG_ROOF, NULL, VioletCityRoofPalettes
	db -1 ; end

VioletOutskirtsPrepareNorthConnection:
	; Route 42 still has PC block IDs. Preserve their exact collision and
	; headbutt semantics in this map's northern preview, using native terrain.
	; Skip this compatibility step automatically once Route 42 is ported.
	lb bc, GROUP_ROUTE_42, MAP_ROUTE_42
	call GetAnyMapTileset
	cp TILESET_JOHTO_TRADITIONAL
	ret nz
	ld hl, wOverworldMapBlocks
	ld b, 3 * (VIOLET_OUTSKIRTS_WIDTH + 6)
.block
	ld e, [hl]
	push hl
	ld hl, .BlockPairs
.find
	ld a, [hli]
	cp -1
	jr z, .store
	cp e
	jr z, .found
	inc hl
	jr .find
.found
	ld e, [hl]
.store
	pop hl
	ld [hl], e
	inc hl
	dec b
	jr nz, .block
	ret

.BlockPairs:
	db $01, $02, $02, $02, $03, $03, $05, $0f, $0a, $1f
	db $35, $a3, $3e, $7c, $3f, $7f, $55, $a3, $58, $a3
	db $59, $a3, $5d, $80, $5e, $81, $61, $82, $62, $85
	db $65, $89, $66, $8b, $68, $30, $6a, $a4, $6b, $47
	db $70, $55, $71, $02, $7a, $a3, $df, $23, $e1, $bd
	db -1 ; end

VioletOutskirtsCemeterySignText:
	text "Violet Cemetery"
	line "Caretaker's House"
	done

VioletOutskirtsHeadstoneText:
	text "It's too faded"
	line "to read…"
	done
