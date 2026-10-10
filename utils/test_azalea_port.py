#!/usr/bin/env python3
"""Azalea's native reference layout, original story events, and Route 33 seam."""

import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def collisions(family):
    return [tuple(line.split(';')[0].strip().removeprefix('tilecoll ').split(', '))
            for line in (ROOT / f'data/tilesets/{family}_collision.asm').read_text().splitlines()]


class AzaleaPortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dry = (ROOT / 'maps/AzaleaTown.ablk').read_bytes()
        cls.wet = (ROOT / 'maps/AzaleaTownRaining.ablk').read_bytes()
        cls.events = (ROOT / 'maps/AzaleaTown.asm').read_text()
        cls.meta = (ROOT / 'data/tilesets/redplusplus_azalea_metatiles.bin').read_bytes()
        cls.attrs = (ROOT / 'data/tilesets/redplusplus_azalea_attributes.bin').read_bytes()
        cls.collisions = collisions('redplusplus_azalea')

    def collision(self, x, y, wet=False):
        layout = self.wet if wet else self.dry
        return self.collisions[layout[y // 2 * 20 + x // 2]][y % 2 * 2 + x % 2]

    def test_dimensions_reference_layout_and_native_family(self):
        self.assertEqual(len(self.dry), 20 * 13)
        self.assertEqual(len(self.wet), 20 * 13)
        self.assertEqual(hashlib.sha256(self.dry).hexdigest(),
                         '3d825b2e553946a1f0b969197a3c73618d16bc0859121ad89cddd0fe88b4ed97')
        self.assertRegex((ROOT / 'constants/map_constants.asm').read_text(),
                         r'map_const AZALEA_TOWN,\s+20,\s*13\b')
        self.assertIn('map AzaleaTown, TILESET_REDPLUSPLUS_AZALEA,',
                      (ROOT / 'data/maps/maps.asm').read_text())
        self.assertEqual(len(self.meta), 4096)
        self.assertEqual(len(self.attrs), 4096)
        self.assertEqual(len(self.collisions), 256)

    def test_original_warp_order_and_entrances(self):
        warps = re.findall(r'^\s*warp_event\s+(\d+),\s*(\d+),\s*(\w+),\s*(\d+)', self.events, re.M)
        self.assertEqual(warps, [
            ('15', '11', 'AZALEA_POKECENTER_1F', '1'),
            ('21', '15', 'CHARCOAL_KILN', '1'),
            ('21', '7', 'AZALEA_MART', '2'),
            ('9', '7', 'KURTS_HOUSE', '1'),
            ('10', '18', 'AZALEA_GYM', '1'),
            ('31', '10', 'SLOWPOKE_WELL_ENTRANCE', '1'),
            ('2', '12', 'ILEX_FOREST_AZALEA_GATE', '3'),
            ('2', '13', 'ILEX_FOREST_AZALEA_GATE', '4'),
        ])
        for wet in (False, True):
            for x, y, collision in [(15, 11, 'DOOR'), (21, 15, 'DOOR'), (21, 7, 'DOOR'),
                                    (9, 7, 'DOOR'), (10, 18, 'DOOR'), (31, 10, 'CAVE'),
                                    (2, 12, 'WARP_CARPET_LEFT'), (2, 13, 'WARP_CARPET_LEFT')]:
                self.assertEqual(self.collision(x, y, wet), collision)
        self.assertRegex((ROOT / 'data/maps/spawn_points.asm').read_text(), r'spawn AZALEA_TOWN,\s+15,\s*12\b')

    def test_backgrounds_and_original_objects_retained(self):
        self.assertEqual(len(re.findall(r'^\s*bg_event ', self.events, re.M)), 8)
        self.assertEqual(len(re.findall(r'^\s*(?:object_event|pokemon_event|fruittree_event) ', self.events, re.M)), 14)
        for x, y, label in [(19, 11, 'AzaleaTownSignText'), (10, 11, 'KurtsHouseSignText'),
                            (8, 18, 'AzaleaGymSignText'), (29, 10, 'SlowpokeWellSignText'),
                            (19, 15, 'CharcoalKilnSignText'), (3, 11, 'AzaleaTownIlexForestSignText'),
                            (5, 11, 'AzaleaTownAdvancedTipsSignText')]:
            self.assertRegex(self.events, rf'bg_event\s+{x},\s*{y}, BGEVENT_JUMPTEXT, {label}')
        self.assertRegex(self.events, r'bg_event\s+32,\s*9, BGEVENT_ITEM \+ FULL_HEAL, EVENT_AZALEA_TOWN_HIDDEN_FULL_HEAL')
        self.assertRegex(self.events, r'fruittree_event\s+8,\s*3, FRUITTREE_AZALEA_TOWN, WHT_APRICORN, PAL_NPC_ENV_WHITE')
        for x, y in [(11, 12), (6, 7), (21, 11), (15, 15), (7, 11), (31, 11), (10, 19),
                     (8, 20), (18, 11), (30, 11), (16, 19), (14, 14), (8, 3)]:
            self.assertEqual(self.collision(x, y), 'FLOOR', (x, y))
        self.assertEqual(self.collision(32, 9), 'WALL')
        self.assertEqual(self.collision(33, 9), 'FLOOR')

    def test_story_movements_and_blockers(self):
        self.assertRegex(self.events, r'coord_event\s+5,\s*12, SCENE_AZALEATOWN_RIVAL_BATTLE, AzaleaTownRivalBattleTrigger1')
        self.assertRegex(self.events, r'coord_event\s+5,\s*13, SCENE_AZALEATOWN_RIVAL_BATTLE, AzaleaTownRivalBattleTrigger2')
        self.assertRegex(self.events, r'coord_event\s+9,\s*8, SCENE_AZALEATOWN_CELEBI_EVENT, AzaleaTown_CelebiTrigger')
        self.assertIn('moveobject AZALEATOWN_RIVAL, 11, 13', self.events)
        approach = self.events.split('.ApproachMovement:', 1)[1].split('.ExitMovement:', 1)[0]
        exit_move = self.events.split('.ExitMovement:', 1)[1].split('AzaleaTown_CelebiTrigger:', 1)[0]
        self.assertEqual(approach.count('step_left'), 6)
        self.assertEqual(exit_move.count('step_left'), 3)
        for wet in (False, True):
            for y in (12, 13):
                for x in range(3, 12):self.assertEqual(self.collision(x, y, wet), 'FLOOR')
            for x, y in [(9, 8), (8, 8), (7, 8), (7, 7)]:
                self.assertIn(self.collision(x, y, wet), ('FLOOR', 'LEDGE_DOWN'))
            # The guards remain the only walkable approach to each entrance.
            for x, y in [(30, 10), (32, 10), (31, 9), (9, 18), (11, 18), (10, 17)]:
                self.assertEqual(self.collision(x, y, wet), 'WALL')
        self.assertIn('verbosegivekeyitem GS_BALL', self.events)
        self.assertIn('setflag ENGINE_FLYPOINT_AZALEA', self.events)
        self.assertIn('verbosegiveitem CLEAR_AMULET, iffalse_endtext', self.events)

    def test_rain_preserves_all_puddles_at_updated_positions(self):
        self.assertEqual([(i % 20, i // 20, b, self.wet[i])
                          for i, b in enumerate(self.dry) if b != self.wet[i]],
                         [(11, 4, 5, 0xe6), (3, 5, 2, 0xe1),
                          (15, 7, 2, 0xe6), (9, 9, 2, 0xe0)])
        self.assertEqual(self.wet[2 * 20 + 3], self.dry[2 * 20 + 3])
        self.assertRegex(self.events, r'object_event\s+7,\s*11, SPRITE_CAMPER,')
        self.assertEqual(self.collision(7, 11, wet=True), 'PUDDLE')
        for block in (0xe0, 0xe1):
            self.assertEqual(self.collisions[block], ('PUDDLE',) * 4)
            self.assertEqual(self.meta[block * 16 + 5], 0x86)
            self.assertEqual(self.attrs[block * 16 + 5], 0x0b)
        self.assertIn('callback MAPCALLBACK_TILES, AzaleaTownRainScript', self.events)
        self.assertIn('changemapblocks AzaleaTownRaining_BlockData', self.events)

    def test_mart_puddle_half_block_shift_preserves_art_and_animation(self):
        # Preserve the two original visible halves; do not move the grass
        # padding from the old E2/E3 blocks over the Mart's approach.
        for table in (self.meta, self.attrs):
            expected = b''.join(table[0xe2 * 16 + row * 4 + 2:0xe2 * 16 + row * 4 + 4]
                                + table[0xe3 * 16 + row * 4:0xe3 * 16 + row * 4 + 2]
                                for row in range(4))
            self.assertEqual(table[0xe6 * 16:0xe7 * 16], expected)
        self.assertEqual(self.wet[5 * 20 + 12:5 * 20 + 14], self.dry[5 * 20 + 12:5 * 20 + 14])
        self.assertEqual(self.wet[4 * 20 + 11], 0xe6)
        self.assertEqual(self.meta[0xe6 * 16 + 10], 0x86)
        self.assertEqual(self.attrs[0xe6 * 16 + 10], 0x0b)
        self.assertEqual(self.collisions[0xe6], ('PUDDLE',) * 4)
        for x in (22, 23):
            for y in (8, 9):self.assertEqual(self.collision(x, y, wet=True), 'PUDDLE')

    def test_puddles_use_original_single_ripple_animation(self):
        for block in (0xe0, 0xe1, 0xe3, 0xe6):
            tiles = [tile for tile, attr in zip(self.meta[block * 16:(block + 1) * 16],
                                                self.attrs[block * 16:(block + 1) * 16]) if attr & 8]
            self.assertEqual(tiles.count(0x86), 1)
            self.assertNotIn(0x93, tiles)
        for block, cell in ((0xe1, 10), (0xe3, 4), (0xe6, 6)):
            self.assertEqual(self.meta[block * 16 + cell], 0x0f)
            self.assertEqual(self.attrs[block * 16 + cell], 0x0b)
        self.assertEqual(self.meta[0x68 * 16 + 13:0x69 * 16], b'\x93' * 3)

    def test_well_puddle_half_block_shift_reuses_full_variant(self):
        self.assertEqual(self.wet[7 * 20 + 14], self.dry[7 * 20 + 14])
        self.assertEqual(self.wet[7 * 20 + 15], 0xe6)
        for y in (14, 15):
            self.assertEqual(self.collision(29, y, wet=True), 'FLOOR')
            for x in (30, 31):self.assertEqual(self.collision(x, y, wet=True), 'PUDDLE')

    def test_tree_priority_headbutt_and_native_roofs(self):
        self.assertEqual([i for i, a in enumerate(self.attrs[0xa7 * 16:0xa8 * 16]) if a & 128], [12, 13])
        common_attrs = (ROOT / 'data/tilesets/redplusplus_route32_attributes.bin').read_bytes()
        for block in (0x1a, 0x1c, 0x1b, 0x24, 0xe4, 0xe5):
            self.assertEqual(self.attrs[block * 16:(block + 1) * 16], common_attrs[block * 16:(block + 1) * 16])
        self.assertEqual(self.collisions[0x1a], ('HEADBUTT_TREE',) * 4)
        self.assertIn('dbw TILESET_REDPLUSPLUS_AZALEA, .new_bark_cherrygrove',
                      (ROOT / 'data/collision/field_move_blocks.asm').read_text())
        self.assertIn('cp TILESET_REDPLUSPLUS_AZALEA', (ROOT / 'engine/tilesets/mapgroup_roofs.asm').read_text())

    def test_both_route33_connection_strips(self):
        attributes = (ROOT / 'data/maps/attributes.asm').read_text()
        self.assertRegex(attributes, r'connection east, Route33, ROUTE_33, 0\b')
        self.assertRegex(attributes, r'connection west, AzaleaTown, AZALEA_TOWN, 0\b')
        route = (ROOT / 'maps/Route33.ablk').read_bytes()
        blocks = set()
        # Azalea east: 12 rows x 3 columns; Route 33 west: 13 x 3.
        for row in range(12):blocks.update(route[row * 10:row * 10 + 3])
        for row in range(13):blocks.update(self.dry[row * 20 + 17:row * 20 + 20])
        other_meta = (ROOT / 'data/tilesets/redplusplus_route32_metatiles.bin').read_bytes()
        other_attrs = (ROOT / 'data/tilesets/redplusplus_route32_attributes.bin').read_bytes()
        other_coll = collisions('redplusplus_route32')
        compiled = ROOT / 'gfx/tilesets/redplusplus_azalea.redplusplus_johto_common.2bpp'
        other_compiled = ROOT / 'gfx/tilesets/redplusplus_route32.redplusplus_johto_common.2bpp'
        for b in blocks:
            self.assertEqual(self.meta[b * 16:(b + 1) * 16], other_meta[b * 16:(b + 1) * 16])
            self.assertEqual(self.attrs[b * 16:(b + 1) * 16], other_attrs[b * 16:(b + 1) * 16])
            self.assertEqual(self.collisions[b], other_coll[b])
            if compiled.exists() and other_compiled.exists():
                for tile, attr in zip(self.meta[b * 16:(b + 1) * 16], self.attrs[b * 16:(b + 1) * 16]):
                    if attr & 8:
                        self.assertEqual(compiled.read_bytes()[tile * 16:(tile + 1) * 16],
                                         other_compiled.read_bytes()[tile * 16:(tile + 1) * 16])


if __name__ == '__main__':
    unittest.main()
