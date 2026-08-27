LoadMapGroupRoof::
	; RedPlusPlus outdoor tilesets use their common graphics in the slots
	; normally reserved for Polished Crystal's map-group roofs. Route 46
	; shares map group 5 with maps that still need the original Azalea roof,
	; so select the matching replacement by tileset during the gradual port.
	ld a, [wMapTileset]
	cp TILESET_AZALEA_BLACKTHORN
	ld a, ROOF_REDPLUSPLUS_NEW_BARK
	jr z, .got_roof

	ld a, [wMapGroup]
	ld e, a
	ld d, 0
	ld hl, MapGroupRoofs
	add hl, de
	ld a, [hl]
.got_roof
	cp -1
	ret z
	ld l, a
	ld h, 0
	add hl, hl
	ld bc, MapGroupRoofGFX
	add hl, bc
	ld a, [hli]
	ld h, [hl]
	ld l, a
	ld de, vTiles2 tile $0a
	lb bc, BANK("Roof Graphics"), 9
	jmp DecompressRequest2bpp

MapGroupRoofGFX:
	table_width 2
	farbank "Roof Graphics"
	fardw NewBarkRoofGFX
	fardw RedPlusPlusNewBarkRoofGFX
	fardw VioletRoofGFX
	fardw AzaleaRoofGFX
	fardw OlivineRoofGFX
	fardw ParkRoofGFX
	fardw SinjohRoofGFX
	assert_table_length NUM_ROOFS

INCLUDE "data/maps/roofs.asm"
