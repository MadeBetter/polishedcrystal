#!/usr/bin/env python3
"""Route 33's reference layout, retained events, rain, and Route 32 seam."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Route33PortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dry = (ROOT / 'maps/Route33.ablk').read_bytes()
        cls.wet = (ROOT / 'maps/Route33Raining.ablk').read_bytes()
        cls.events = (ROOT / 'maps/Route33.asm').read_text()
        cls.attrs = (ROOT / 'data/tilesets/redplusplus_route32_attributes.bin').read_bytes()
        cls.meta = (ROOT / 'data/tilesets/redplusplus_route32_metatiles.bin').read_bytes()
        cls.collisions = [tuple(line.split(';')[0].strip().removeprefix('tilecoll ').split(', '))
                          for line in (ROOT / 'data/tilesets/redplusplus_route32_collision.asm').read_text().splitlines()]

    def collision(self, layout, width, x, y):
        return self.collisions[layout[y // 2 * width + x // 2]][y % 2 * 2 + x % 2]

    def test_reference_layout_and_dimensions(self):
        self.assertRegex((ROOT / 'constants/map_constants.asm').read_text(),
                         r'map_const ROUTE_33,\s+10,\s*12\b')
        self.assertEqual(self.dry, bytes.fromhex('''
            4d 4d 4c 4c 4c 4c 53 4d 47 1c
            4e 4e 4e 4e 4e 51 4d 53 4d 47
            2c 2c 2c 2c 51 48 4d 4d 53 49
            1a 1a 1a 1a 48 4a 51 4d 49 49
            1a 1a 1a 1a 48 4d 4a 4e 4b 4d
            1a 1a 1c 1c 4a a6 4e 51 4d 4d
            1a 1a 02 02 34 33 02 48 07 4d
            1c 1c 02 02 38 39 35 4a 51 52
            05 05 05 05 05 02 02 e0 48 48
            e5 e5 e5 03 03 03 02 e1 48 48
            e4 e4 e4 e5 e5 e5 e5 e5 48 48
            e4 e4 e4 e4 e4 e4 e4 e4 48 48
        '''))
        self.assertIn('map Route33, TILESET_REDPLUSPLUS_ROUTE32,',
                      (ROOT / 'data/maps/maps.asm').read_text())

    def test_events_and_cave_return(self):
        self.assertRegex(self.events, r'warp_event\s+11,\s*11, UNION_CAVE_1F, 3')
        self.assertRegex(self.events, r'bg_event\s+11,\s*13, BGEVENT_JUMPTEXT, Route33SignText')
        self.assertRegex(self.events, r'object_event\s+6,\s*13,.*TrainerHikerAnthony, -1')
        self.assertRegex(self.events, r'object_event\s+12,\s*19,.*TrainerSchoolgirlImogen, -1')
        self.assertRegex(self.events, r'fruittree_event\s+14,\s*18, FRUITTREE_ROUTE_33, PECHA_BERRY, PAL_NPC_PINK')
        for layout in (self.dry, self.wet):
            for x, y, collision in [(11, 11, 'CAVE'), (11, 13, 'WALL'),
                                    (6, 13, 'FLOOR'), (12, 19, 'FLOOR'),
                                    (14, 18, 'WALL'), (14, 19, 'FLOOR')]:
                self.assertEqual(self.collision(layout, 10, x, y), collision)
        self.assertRegex((ROOT / 'maps/UnionCave1F.asm').read_text(),
                         r'warp_event\s+17,\s*43, ROUTE_33, 1')
        self.assertEqual(len(re.findall(r'^\s*warp_event ', self.events, re.M)), 1)
        self.assertEqual(len(re.findall(r'^\s*bg_event ', self.events, re.M)), 1)
        self.assertEqual(len(re.findall(r'^\s*(?:object_event|fruittree_event) ', self.events, re.M)), 3)

    def test_weather_changes_only_puddles(self):
        self.assertEqual(len(self.wet), 120)
        self.assertEqual([(i % 10, i // 10, b, self.wet[i])
                          for i, b in enumerate(self.dry) if b != self.wet[i]],
                         [(5, 8, 2, 0xe6)])
        self.assertEqual(self.collisions[0xe2], ('FLOOR', 'PUDDLE', 'FLOOR', 'PUDDLE'))
        self.assertEqual(self.collisions[0xe3], ('PUDDLE', 'FLOOR', 'PUDDLE', 'FLOOR'))
        self.assertIn('callback MAPCALLBACK_TILES, Route33RainScript', self.events)
        self.assertIn('changemapblocks Route33Raining_BlockData', self.events)
        anim = (ROOT / 'data/tileset_anims.asm').read_text().split('TilesetRedPlusPlusRoute32Anim::', 1)[1].split('TilesetJohtoTraditionalAnim::', 1)[0]
        self.assertEqual(anim.count('tileframe AnimateRainTiles,                $1:86'), 2)
        route32 = (ROOT / 'maps/Route32.ablk').read_bytes()
        for block in set(route32) | set(self.dry):
            for tile, attr in zip(self.meta[block * 16:(block + 1) * 16],
                                  self.attrs[block * 16:(block + 1) * 16]):
                self.assertFalse(attr & 8 and tile in (0x86, 0x87))
        self.assertEqual(self.meta[0xe3 * 16 + 8], 0x86)
        self.assertEqual(self.attrs[0xe3 * 16 + 8] & 0x68, 8)

    def test_puddle_half_block_shift_preserves_outline_and_animation(self):
        for table in (self.meta, self.attrs):
            expected = b''.join(table[0xe2 * 16 + row * 4 + 2:0xe2 * 16 + row * 4 + 4]
                                + table[0xe3 * 16 + row * 4:0xe3 * 16 + row * 4 + 2]
                                for row in range(4))
            self.assertEqual(table[0xe6 * 16:0xe7 * 16], expected)
        self.assertEqual(self.wet[8 * 10 + 6], self.dry[8 * 10 + 6])
        self.assertEqual(self.collisions[0xe6], ('PUDDLE',) * 4)
        self.assertEqual(self.meta[0xe6 * 16 + 10], 0x86)
        self.assertEqual(self.attrs[0xe6 * 16 + 10], 0x0b)
        for y in (16, 17):
            for x in (10, 11):self.assertEqual(self.collision(self.wet, 10, x, y), 'PUDDLE')
            self.assertEqual(self.collision(self.wet, 10, 12, y), 'FLOOR')

    def test_puddles_use_one_ripple_without_changing_other_block_graphics(self):
        self.assertEqual(self.meta[0xe6 * 16 + 6], 0x0f)
        self.assertEqual(self.attrs[0xe6 * 16 + 6], 0x0b)
        self.assertEqual(self.meta[0xe3 * 16 + 4], 0x0f)
        for block in (0xe3, 0xe6):
            tiles = [tile for tile, attr in zip(self.meta[block * 16:(block + 1) * 16],
                                                self.attrs[block * 16:(block + 1) * 16]) if attr & 8]
            self.assertEqual(tiles.count(0x86), 1)
            self.assertNotIn(0x93, tiles)
        # Preserve other definitions which reference the imported static graphic.
        self.assertEqual(self.meta[0x68 * 16 + 13:0x69 * 16], b'\x93' * 3)

    def test_cave_approaches_and_ledge_landings(self):
        # Keep the normal Union Cave exit route; do not force a new shortcut
        # through the reference cliffs to the northeast connection passage.
        for layout in (self.dry, self.wet):
            for x, y in [(11, 12), (12, 12), (13, 12), (13, 13),
                         (13, 14), (13, 15), (13, 16),
                         (6, 16), (6, 15), (6, 14), (6, 13),
                         (13, 17), (13, 18), (13, 19), (12, 19), (14, 19)]:
                self.assertEqual(self.collision(layout, 10, x, y), 'FLOOR', (x, y))
            # The jump starts on the ledge cell and skips its wall row.
            self.assertEqual(self.collision(layout, 10, 11, 14), 'LEDGE_DOWN')
            self.assertEqual(self.collision(layout, 10, 11, 16),
                             'PUDDLE' if layout == self.wet else 'FLOOR')

    def test_berry_priority_and_tree_eligibility(self):
        self.assertEqual([i for i, attr in enumerate(self.attrs[0xe0 * 16:0xe1 * 16]) if attr & 128], [12, 13])
        self.assertFalse(any(attr & 128 for attr in self.attrs[0xe1 * 16:0xe2 * 16]))
        for new, source in [(0xe4, 0x1f), (0xe5, 0x25)]:
            self.assertEqual(self.meta[new * 16:(new + 1) * 16], self.meta[source * 16:(source + 1) * 16])
            self.assertEqual(self.attrs[new * 16:(new + 1) * 16], self.attrs[source * 16:(source + 1) * 16])
        self.assertEqual(self.collisions[0xe4], ('HEADBUTT_TREE',) * 4)
        self.assertEqual(self.collisions[0xe5], ('WALL', 'WALL', 'HEADBUTT_TREE', 'HEADBUTT_TREE'))

    def test_route32_seam(self):
        attributes = (ROOT / 'data/maps/attributes.asm').read_text()
        self.assertRegex(attributes, r'connection south, Route33, ROUTE_33, 2\b')
        self.assertRegex(attributes, r'connection north, Route32, ROUTE_32, -2\b')
        self.assertRegex(attributes, r'map_attributes Route33, ROUTE_33, \$f\s+connection north')
        self.assertRegex(attributes, r'connection west, AzaleaTown, AZALEA_TOWN, 0\b')
        route32 = (ROOT / 'maps/Route32.ablk').read_bytes()
        # The open eastern passage maps x=18 to x=14 in both directions.
        self.assertEqual(self.collision(route32, 12, 18, 91), 'FLOOR')
        self.assertEqual(self.collision(self.dry, 10, 14, 0), 'FLOOR')


if __name__ == '__main__':
    unittest.main()
