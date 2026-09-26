; Each descriptor associates one trainer class with every resource used by
; the colorized trainer battle system.
MACRO trainer_color_descriptor
	db \1
	db BANK(\2)
	db \3
	dw \2
	dw \4
	dw \5
	dw \6
	dw \7
ENDM

TrainerColorDescriptors:
	table_width TRAINER_COLOR_DESCRIPTOR_SIZE
	; class, OAM graphics bank, tile count, OAM graphics, OAM grid,
	; BG map, secondary BG palette, OAM palettes
	trainer_color_descriptor LYRA1, Lyra1TrainerOAM, 18, Lyra1GridData, Lyra1BGPaletteMap, Lyra1BGColor2Palette, Lyra1OAMColorPalette
	trainer_color_descriptor RIVAL0, Rival1TrainerOAM, 19, Rival1GridData, Rival1BGPaletteMap, Rival1BGColor2Palette, Rival1OAMColorPalette
	trainer_color_descriptor RIVAL1, Rival1TrainerOAM, 19, Rival1GridData, Rival1BGPaletteMap, Rival1BGColor2Palette, Rival1OAMColorPalette
	trainer_color_descriptor YOUNGSTER, YoungsterTrainerOAM, 21, YoungsterGridData, YoungsterBGPaletteMap, YoungsterBGColor2Palette, YoungsterOAMColorPalette
	trainer_color_descriptor BUG_CATCHER, BugCatcherTrainerOAM, 21, BugCatcherGridData, BugCatcherBGPaletteMap, BugCatcherBGColor2Palette, BugCatcherOAMColorPalette
	trainer_color_descriptor COOLTRAINERM, CooltrainerMTrainerOAM, 15, CooltrainerMGridData, CooltrainerMBGPaletteMap, CooltrainerMBGColor2Palette, CooltrainerMOAMColorPalette
	trainer_color_descriptor SAGE, SageTrainerOAM, 22, SageGridData, SageBGPaletteMap, SageBGColor2Palette, SageOAMColorPalette
	trainer_color_descriptor ELDER, ElderTrainerOAM, 22, ElderGridData, ElderBGPaletteMap, ElderBGColor2Palette, ElderOAMColorPalette
	trainer_color_descriptor SCHOOLGIRL, SchoolgirlTrainerOAM, 17, SchoolgirlGridData, SchoolgirlBGPaletteMap, SchoolgirlBGColor2Palette, SchoolgirlOAMColorPalette
	trainer_color_descriptor BIRD_KEEPER, BirdKeeperTrainerOAM, 22, BirdKeeperGridData, BirdKeeperBGPaletteMap, BirdKeeperBGColor2Palette, BirdKeeperOAMColorPalette
	assert_table_length 10
	db -1

PURGE trainer_color_descriptor


; Color data

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


; BG palette assignments for each 7x7 trainer frontpic.
; Palette 1 is the primary trainer palette, 5 is the secondary palette,
; and 6 is the shared skin palette.

Lyra1BGPaletteMap:
	; Each byte represents the palette number for that tile position
	; Palette 1 = Enemy BG, Palette 6 = Skin, Palette 5 = Clothing
	db 1, 1, 1, 1, 1, 1, 1  ; Row 0
	db 1, 1, 6, 6, 1, 1, 1  ; Row 1
	db 1, 1, 6, 6, 6, 1, 1  ; Row 2
	db 1, 6, 6, 1, 5, 5, 1  ; Row 3
	db 1, 1, 6, 6, 6, 5, 1  ; Row 4
	db 1, 1, 1, 1, 1, 1, 1  ; Row 5
	db 1, 1, 1, 1, 1, 1, 1  ; Row 6

Rival1BGPaletteMap:
	db 1, 1, 1, 1, 1, 1, 1  ; Row 0
	db 1, 1, 1, 6, 6, 1, 1  ; Row 1
	db 1, 6, 1, 6, 6, 1, 1  ; Row 2
	db 1, 1, 1, 1, 1, 1, 1  ; Row 3
	db 1, 1, 1, 5, 5, 1, 1  ; Row 4
	db 1, 1, 1, 5, 5, 1, 1  ; Row 5
	db 1, 1, 1, 5, 5, 1, 1  ; Row 6

YoungsterBGPaletteMap:
	db 1, 1, 1, 1, 1, 1, 1  ; Row 0
	db 1, 1, 1, 6, 6, 1, 1  ; Row 1
	db 1, 6, 6, 6, 6, 6, 1  ; Row 2
	db 1, 6, 6, 5, 5, 6, 6  ; Row 3
	db 1, 1, 1, 5, 5, 6, 6  ; Row 4
	db 1, 1, 1, 6, 6, 1, 1  ; Row 5
	db 1, 1, 1, 1, 1, 1, 1  ; Row 6

BugCatcherBGPaletteMap:
  db 1, 1, 1, 1, 1, 1, 1  ; Row 0
  db 1, 1, 1, 1, 1, 5, 5  ; Row 1
  db 1, 1, 1, 1, 1, 5, 5  ; Row 2
  db 1, 6, 6, 6, 6, 5, 5  ; Row 3
  db 1, 6, 6, 6, 6, 5, 5  ; Row 4
  db 1, 6, 6, 6, 1, 1, 1  ; Row 5
  db 1, 6, 6, 6, 1, 1, 1  ; Row 6

CooltrainerMBGPaletteMap:
  db 1, 1, 1, 1, 1, 1, 1  ; Row 0
  db 1, 6, 1, 6, 6, 1, 1  ; Row 1
  db 1, 6, 5, 5, 5, 5, 5  ; Row 2
  db 1, 1, 1, 5, 5, 5, 5  ; Row 3
  db 1, 1, 1, 5, 5, 6, 6  ; Row 4
  db 1, 1, 5, 5, 5, 5, 1  ; Row 5
  db 1, 1, 5, 5, 5, 5, 1  ; Row 6

SageBGPaletteMap:
  db 6, 6, 6, 6, 6, 6, 6  ; Row 0
  db 6, 6, 6, 6, 6, 6, 6  ; Row 1
  db 6, 6, 6, 6, 1, 1, 1 ; Row 2
  db 1, 1, 6, 6, 1, 1, 1  ; Row 3
  db 1, 1, 5, 5, 1, 1, 1  ; Row 4
  db 5, 5, 5, 5, 5, 5, 5  ; Row 5
  db 5, 5, 5, 5, 5, 5, 5  ; Row 6

ElderBGPaletteMap:
  db 6, 6, 6, 6, 6, 6, 6  ; Row 0
  db 6, 6, 6, 6, 6, 6, 6  ; Row 1
  db 1, 1, 1, 1, 5, 1, 1  ; Row 2
  db 1, 1, 6, 6, 5, 1, 1  ; Row 3
  db 1, 1, 5, 5, 1, 1, 1  ; Row 4
  db 1, 1, 5, 5, 1, 1, 1  ; Row 5
  db 1, 1, 1, 5, 1, 1, 1  ; Row 6

SchoolgirlBGPaletteMap:
  db 1, 1, 1, 1, 1, 1, 1  ; Row 0
  db 1, 1, 1, 1, 1, 1, 1  ; Row 1
  db 1, 1, 5, 6, 6, 1, 1  ; Row 2
  db 1, 1, 6, 6, 1, 1, 1  ; Row 3
  db 1, 1, 5, 5, 1, 1, 1  ; Row 4
  db 1, 6, 6, 6, 1, 1, 1  ; Row 5
  db 1, 1, 5, 6, 1, 1, 1  ; Row 6

BirdKeeperBGPaletteMap:
  db 1, 1, 1, 1, 1, 1, 1  ; Row 0
  db 1, 1, 6, 6, 6, 1, 1  ; Row 1
  db 6, 6, 6, 6, 6, 6, 6  ; Row 2
  db 6, 6, 5, 5, 6, 6, 6  ; Row 3
  db 1, 1, 5, 5, 6, 6, 1  ; Row 4
  db 6, 5, 5, 5, 1, 6, 1  ; Row 5
  db 1, 5, 5, 5, 5, 6, 6  ; Row 6


; OAM overlay records: tile ID, X offset, Y offset, OBJ palette.

Lyra1GridData:
	; 1st digit is tile number in vram order
	; 2nd is move left or right, 3rd is up or down
	; 4th digit is what OBJ palette to assign (0, 2, 6, 7)
	; x: 0           1          2             3          4           5           6
	db 0,0,0,0 ,  0,0,0,0 ,  1,0,-3,0 , 2,-3,-6,0 ,  3,-3,-4,0 ,  0,0,0,0 ,   0,0,0,0   ; y = 0
	db 0,0,0,0 ,  0,0,0,0 ,  4,0,-3,2 , 5,0,-4,2 ,   6,0,-4,2 ,   0,0,0,0 ,   0,0,0,0   ; y = 1
	db 0,0,0,0 ,  0,0,0,0 ,  7,6,0,6 ,  8,0,-2,0 ,   9,0,-2,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 2
	db 0,0,0,0 ,  0,0,0,0 ,  10,0,3,0 , 11,0,0,6 ,   12,0,0,6 ,   0,0,0,0 ,   0,0,0,0   ; y = 3
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  13,-1,0,6 ,  14,-1,0,6 ,  15,-4,2,7 , 0,0,0,0   ; y = 4
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,    0,0,0,0 ,    0,0,0,0 ,   0,0,0,0   ; y = 5
	db 0,0,0,0 ,  0,0,0,0 ,  16,0,2,0 , 17,0,0,0 ,   0,0,0,0 ,    0,0,0,0 ,   0,0,0,0   ; y = 6

Rival1GridData:
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,   0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 0
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  1,0,1,0 ,   2,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 1
	db 0,0,0,0 ,  3,0,0,0 ,  4,1,0,2 ,  5,1,1,2 ,   6,1,0,2 ,   7,-5,0,0 ,  0,0,0,0   ; y = 2
	db 0,0,0,0 ,  8,0,1,7 ,  9,0,0,2 ,  10,0,0,2 ,  11,0,0,2 ,  0,0,0,0 ,   0,0,0,0   ; y = 3
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  12,-3,0,2 , 13,-2,0,6 , 0,0,0,0 ,   0,0,0,0   ; y = 4
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  14,0,5,0 ,  0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 5
	db 0,0,0,0 ,  0,0,0,0 ,  15,8,0,0 , 16,0,0,7 ,  17,0,0,7 ,  18,-7,0,0 , 0,0,0,0   ; y = 6

YoungsterGridData:
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  1,-2,-4,0 , 0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 0
	db 0,0,0,0 ,  0,0,0,0 ,  2,0,-2,0 , 3,0,0,0 ,   4,0,0,0 ,   5,-9,-4,2 , 0,0,0,0   ; y = 1
	db 0,0,0,0 ,  6,2,-3,7 , 7,7,2,2 ,  8,2,0,2 ,   9,-1,0,0 ,  0,0,0,0 ,   0,0,0,0   ; y = 2
	db 0,0,0,0 ,  10,2,0,0 , 11,7,3,0 , 12,-1,2,6 , 13,1,2,6 ,  14,-1,3,0 , 0,0,0,0   ; y = 3
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  15,1,2,6 ,  16,0,-1,0 , 17,-2,4,2 , 0,0,0,0   ; y = 4
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  18,0,5,0 ,  0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 5
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  19,-1,0,0 , 20,1,0,0 ,  0,0,0,0 ,   0,0,0,0   ; y = 6

BugCatcherGridData:
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,   0,0,0,0 ,   0,0,0,0 ,  0,0,0,0 ,  0,0,0,0   ; y = 0
	db 0,0,0,0 ,  1,5,-4,0 , 2,-2,-5,6 , 3,-2,-6,0 , 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0   ; y = 1
	db 0,0,0,0 ,  0,0,0,0 ,  4,-1,0,2 ,  0,0,0,0 ,   0,0,0,0 ,  0,0,0,0 ,  0,0,0,0   ; y = 2
	db 5,6,3,0 ,  6,6,2,0 ,  7,5,1,0 ,   8,5,1,0 ,   9,0,0,6 ,  0,0,0,0 ,  0,0,0,0   ; y = 3
	db 0,0,0,0 ,  10,3,0,0 , 11,0,3,7 ,  12,0,0,6 ,  13,0,3,0 , 0,0,0,0 ,  0,0,0,0   ; y = 4
	db 0,0,0,0 ,  14,3,3,7 , 15,0,2,7 ,  0,0,0,0 ,   0,0,0,0 ,  0,0,0,0 ,  0,0,0,0   ; y = 5
	db 16,3,0,2 , 17,0,6,2 , 18,0,5,2 ,  19,0,0,2 ,  20,0,0,0 , 0,0,0,0 ,  0,0,0,0   ; y = 6

CooltrainerMGridData:
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  1,0,0,2 ,   0,0,0,0 ,   0,0,0,0 ,  0,0,0,0   ; y = 0
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  2,-1,4,0 ,  3,-1,2,0 ,  4,-1,1,0 , 0,0,0,0   ; y = 1
	db 0,0,0,0 ,  5,2,0,2 ,  0,0,0,0 ,  6,4,0,2 ,   0,0,0,0 ,   0,0,0,0 ,  0,0,0,0   ; y = 2
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  7,0,2,6 ,   0,0,0,0 ,   8,-1,0,2 , 0,0,0,0   ; y = 3
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  9,0,0,6 ,   10,0,1,6 ,  11,0,0,6 , 0,0,0,0   ; y = 4
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,   0,0,0,0 ,   0,0,0,0 ,  0,0,0,0   ; y = 5
	db 0,0,0,0 ,  0,0,0,0 ,  12,6,0,7 , 13,-2,0,6 , 14,2,0,7 ,  0,0,0,0 ,  0,0,0,0   ; y = 6

SageGridData:
	db 0,0,0,0 ,  0,0,0,0 ,   1,1,0,0 ,  2,1,-2,0 ,  0,0,0,0 ,    0,0,0,0 ,  0,0,0,0   ; y = 0
	db 0,0,0,0 ,  3,5,0,7 ,   4,0,0,0 ,  5,1,0,0 ,   6,-2,-1,7 ,  0,0,0,0 ,  0,0,0,0   ; y = 1
	db 0,0,0,0 ,  7,7,-3,2 ,  8,0,0,0 ,  9,0,0,0 ,   10,-5,-3,2 , 0,0,0,0 ,  0,0,0,0   ; y = 2
	db 0,0,0,0 ,  0,0,0,0 ,   11,0,0,0 , 12,-2,0,2 , 13,-1,0,0 ,  0,0,0,0 ,  0,0,0,0   ; y = 3
	db 0,0,0,0 ,  14,2,4,2 ,  15,0,0,0 , 16,-1,0,6 , 17,-5,0,0 ,  0,0,0,0 ,  0,0,0,0   ; y = 4
	db 0,0,0,0 ,  0,0,0,0 ,   0,0,0,0 ,  18,0,5,7 ,  19,0,1,2 ,   0,0,0,0 ,  0,0,0,0   ; y = 5
	db 0,0,0,0 ,  0,0,0,0 ,   20,2,0,0 , 0,0,0,0 ,   21,-2,0,0 ,  0,0,0,0 ,  0,0,0,0   ; y = 6

ElderGridData:
	db 0,0,0,0 ,  0,0,0,0 ,  0,0,0,0 ,   0,0,0,0 ,   1,-5,-5,0 ,   0,0,0,0 ,  0,0,0,0   ; y = 0
	db 0,0,0,0 ,  0,0,0,0 ,  2,1,1,0 ,   3,-4,-5,0 , 4,-4,-3,0 ,   0,0,0,0 ,  0,0,0,0   ; y = 1
	db 0,0,0,0 ,  5,10,0,0 , 6,0,1,2 ,   7,0,0,2 ,   8,-3,-3,6 ,   0,0,0,0 ,  0,0,0,0   ; y = 2
	db 9,10,1,0 , 10,8,0,0 , 11,-1,0,7 , 12,0,0,7 ,  0,0,0,0 ,     0,0,0,0 ,  0,0,0,0   ; y = 3
	db 0,0,0,0 ,  13,2,2,0 , 14,0,0,7 ,  15,-1,0,6 , 16,-4,0,0 ,   0,0,0,0 ,  0,0,0,0   ; y = 4
	db 0,0,0,0 ,  0,0,0,0 ,  17,0,0,7 ,  18,-3,0,6 , 19,-10,-1,6 , 0,0,0,0 ,  0,0,0,0   ; y = 5
	db 0,0,0,0 ,  0,0,0,0 ,  20,-3,0,0 , 21,1,0,0 ,  0,0,0,0 ,     0,0,0,0 ,  0,0,0,0   ; y = 6

SchoolgirlGridData:
	db 0,0,0,0 ,  0,0,0,0 ,   0,0,0,0 ,  0,0,0,0 ,    0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 0
	db 0,0,0,0 ,  0,0,0,0 ,   1,0,0,2 ,  0,0,0,0 ,    2,0,-3,6 ,  0,0,0,0 ,   0,0,0,0   ; y = 1
	db 0,0,0,0 ,  0,0,0,0 ,   3,0,0,6 ,  4,0,1,0 ,    5,0,0,0 ,   6,-5,0,2 ,  0,0,0,0   ; y = 2
	db 0,0,0,0 ,  0,0,0,0 ,   7,6,1,7 ,  8,-1,0,2 ,   0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 3
	db 0,0,0,0 ,  9,0,0,2 ,   10,0,0,6 , 11,0,0,6 ,   0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 4
	db 0,0,0,0 ,  12,4,0,7 ,  13,0,3,7 , 14,0,0,7 ,   0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 5
	db 0,0,0,0 ,  0,0,0,0 ,   15,4,0,6 , 16,-3,1,2 ,  0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 6

BirdKeeperGridData:
	db 0,0,0,0 ,  0,0,0,0 ,   0,0,0,0 ,   1,-1,-3,0 , 2,-1,-2,0 , 0,0,0,0 ,   0,0,0,0   ; y = 0
	db 0,0,0,0 ,  0,0,0,0 ,   3,0,-1,0 ,  4,0,-4,2 ,  0,0,0,0 ,   0,0,0,0 ,   0,0,0,0   ; y = 1
	db 0,0,0,0 ,  5,-1,-3,0 , 6,0,0,6 ,   7,0,0,6 ,   8,-7,-5,2 , 0,0,0,0 ,   0,0,0,0   ; y = 2
	db 0,0,0,0 ,  9,0,5,0 ,   10,-2,4,7 , 11,0,1,7 ,  12,0,1,7 ,  0,0,0,0 ,   0,0,0,0   ; y = 3
	db 0,0,0,0 ,  0,0,0,0 ,   13,0,3,6 ,  14,7,0,6 ,  15,0,1,7 ,  16,0,0,7 ,  0,0,0,0   ; y = 4
	db 0,0,0,0 ,  0,0,0,0 ,   17,0,0,6 ,  0,0,0,0 ,   18,0,0,6 ,  19,0,-3,7 , 0,0,0,0   ; y = 5
	db 0,0,0,0 ,  20,1,0,7 ,  0,0,0,0 ,   0,0,0,0 ,   21,2,0,7 ,  0,0,0,0 ,   0,0,0,0   ; y = 6
