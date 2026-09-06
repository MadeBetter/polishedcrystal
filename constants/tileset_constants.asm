; Tilesets indexes (see data/tilesets.asm)
	const_def 1
	const TILESET_JOHTO_TRADITIONAL    ; 01
	const TILESET_JOHTO_MODERN         ; 02
	const TILESET_JOHTO_COAST          ; 03
	const TILESET_JOHTO_OUTLANDS       ; 04
	const TILESET_JOHTO_ANCIENT        ; 05
	const TILESET_JOHTO_SACRED         ; 06
	const TILESET_BATTLE_TOWER_OUTSIDE ; 07
	const TILESET_SNOWTOP_MOUNTAIN     ; 08
	const TILESET_NEW_BARK_CHERRYGROVE ; 09
	const TILESET_AZALEA_BLACKTHORN    ; 0a
DEF NO_ROOF_TILESETS EQU const_value
	const TILESET_KANTO                ; 0b
	const TILESET_KANTO_NORTH          ; 0c
	const TILESET_KANTO_URBAN          ; 0d
	const TILESET_INDIGO_PLATEAU       ; 0e
	const TILESET_SHAMOUTI_ISLAND      ; 0f
	const TILESET_VALENCIA_ISLAND      ; 10
	const TILESET_FARAWAY_ISLAND       ; 11
	const TILESET_JOHTO_HOUSE          ; 12
	const TILESET_KANTO_HOUSE          ; 13
	const TILESET_TRADITIONAL_HOUSE    ; 14
	const TILESET_POKECENTER           ; 15
	const TILESET_POKECOM_CENTER       ; 16
	const TILESET_MART                 ; 17
	const TILESET_GATE                 ; 18
	const TILESET_GYM                  ; 19
	const TILESET_MAGNET_TRAIN         ; 1a
	const TILESET_CHAMPIONS_ROOM       ; 1b
	const TILESET_PORT                 ; 1c
	const TILESET_LAB                  ; 1d
	const TILESET_FACILITY             ; 1e
	const TILESET_CELADON_MANSION      ; 1f
	const TILESET_GAME_CORNER          ; 20
	const TILESET_HOME_DECOR_STORE     ; 21
	const TILESET_MUSEUM               ; 22
	const TILESET_HOTEL                ; 23
	const TILESET_SPROUT_TOWER         ; 24
	const TILESET_BATTLE_TOWER_INSIDE  ; 25
	const TILESET_RADIO_TOWER          ; 26
	const TILESET_LIGHTHOUSE           ; 27
	const TILESET_UNDERGROUND          ; 28
	const TILESET_CAVE                 ; 29
	const TILESET_QUIET_CAVE           ; 2a
	const TILESET_VOLCANO              ; 2b
	const TILESET_ICE_PATH             ; 2c
	const TILESET_TUNNEL               ; 2d
	const TILESET_FOREST               ; 2e
	const TILESET_PARK                 ; 2f
	const TILESET_SAFARI_ZONE          ; 30
	const TILESET_RUINS_OF_ALPH        ; 31
	const TILESET_POKEMON_MANSION      ; 32
	const TILESET_BATTLE_FACTORY       ; 33
	const TILESET_HIDDEN_GROTTO        ; 34
	const TILESET_PEAKS                ; 35
	const TILESET_HIDEOUT              ; 36
	const TILESET_KANTO_GYM            ; 37
DEF NUM_TILESETS EQU const_value - 1

; wTileset struct size
DEF TILESET_LENGTH EQU 18

; MapGroupRoofs values (see data/maps/roofs.asm)
; MapGroupRoofGFX indexes (see engine/tilesets/mapgroup_roofs.asm)
	const_def
	const ROOF_NEW_BARK ; 0
	const ROOF_REDPLUSPLUS_NEW_BARK ; 1
	const ROOF_VIOLET   ; 2
	const ROOF_AZALEA   ; 3
	const ROOF_OLIVINE  ; 4
	const ROOF_PARK     ; 5
	const ROOF_SINJOH   ; 6
DEF NUM_ROOFS EQU const_value

; roof length (see gfx/tilesets/roofs)
DEF ROOF_LENGTH EQU 9

; coast sand tile IDs in vTiles4
	const_def $f0
	const COAST_SAND_TILE         ; $f0
	const COAST_SAND_TILE_FOOT_V1 ; $f1
	const COAST_SAND_TILE_FOOT_V2 ; $f2
	const COAST_SAND_TILE_FOOT_H1 ; $f3
	const COAST_SAND_TILE_FOOT_H2 ; $f4
	const COAST_SAND_TILE_BIKE_H  ; $f5
	const COAST_SAND_TILE_BIKE_V  ; $f6
DEF NUM_COAST_SAND_TILES EQU const_value - COAST_SAND_TILE

; bg palette values
; TilesetBGPalette indexes (see gfx/tilesets/bg_tiles.pal)
	const_def
	const PAL_BG_GRAY   ; 0
	const PAL_BG_RED    ; 1
	const PAL_BG_GREEN  ; 2
	const PAL_BG_WATER  ; 3
	const PAL_BG_YELLOW ; 4
	const PAL_BG_BROWN  ; 5
	const PAL_BG_ROOF   ; 6
	const PAL_BG_TEXT   ; 7
