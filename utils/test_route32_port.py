#!/usr/bin/env python3
"""Regression checks for Route 32's native blockset and Violet City boundary."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def collisions(tileset):
    return [tuple(line.split(';')[0].strip().removeprefix('tilecoll ').split(', '))
            for line in (ROOT / f'data/tilesets/{tileset}_collision.asm').read_text().splitlines()]


class Route32PortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = (ROOT / 'maps/Route32.ablk').read_bytes()
        cls.events = (ROOT / 'maps/Route32.asm').read_text()
        cls.collisions = collisions('redplusplus_route32')
        cls.attributes = (ROOT / 'data/tilesets/redplusplus_route32_attributes.bin').read_bytes()

    def collision(self, x, y):
        block = self.layout[y // 2 * 12 + x // 2]
        return self.collisions[block][y % 2 * 2 + x % 2]

    def test_native_dimensions_and_tables(self):
        constants = (ROOT / 'constants/map_constants.asm').read_text()
        self.assertRegex(constants, r'map_const ROUTE_32,\s+12,\s*46\b')
        self.assertEqual(len(self.layout), 12 * 46)
        self.assertEqual(len(self.collisions), 256)
        self.assertEqual(len(self.attributes), 4096)
        self.assertEqual((ROOT / 'data/tilesets/redplusplus_route32_metatiles.bin').stat().st_size, 4096)
        self.assertIn('map Route32, TILESET_REDPLUSPLUS_ROUTE32,', (ROOT / 'data/maps/maps.asm').read_text())

    def test_warps_and_fly_spawn(self):
        warps = re.findall(r'^\s*warp_event\s+(\d+),\s*(\d+),\s*(\w+),\s*(\d+)', self.events, re.M)
        self.assertEqual(warps, [
            ('15', '77', 'ROUTE_32_POKECENTER_1F', '1'),
            ('8', '6', 'ROUTE_32_RUINS_OF_ALPH_GATE', '3'),
            ('8', '7', 'ROUTE_32_RUINS_OF_ALPH_GATE', '4'),
            ('10', '83', 'UNION_CAVE_1F', '4'),
            ('9', '28', 'HIDDEN_TREE_GROTTO', '1'),
            ('17', '1', 'VIOLET_CITY', '12'),
        ])
        for x, y, expected in [(15, 77, 'DOOR'), (8, 6, 'WARP_CARPET_LEFT'),
                               (8, 7, 'WARP_CARPET_LEFT'), (10, 83, 'CAVE'),
                               (9, 28, 'FLOOR'), (17, 1, 'DOOR')]:
            self.assertEqual(self.collision(x, y), expected)
        self.assertNotIn(('6', '19'), [warp[:2] for warp in warps])
        self.assertRegex((ROOT / 'data/maps/spawn_points.asm').read_text(), r'spawn ROUTE_32,\s+15,\s*78\b')

    def test_both_connection_strips(self):
        connections = (ROOT / 'data/maps/attributes.asm').read_text()
        self.assertRegex(connections, r'connection south, Route32, ROUTE_32, -2\b')
        self.assertRegex(connections, r'connection north, VioletCity, VIOLET_CITY, 2\b')
        violet = (ROOT / 'maps/VioletCity.ablk').read_bytes()
        # Same slices as the engine's connection macro: 13 blocks per northern
        # row, 12 per southern row. Source offset is zero in both directions.
        blocks = set(self.layout[:36])
        for row in range(3):
            blocks.update(violet[(17 + row) * 20:(17 + row) * 20 + 13])
        for kind, width in [('metatiles.bin', 16), ('attributes.bin', 16)]:
            route = (ROOT / f'data/tilesets/redplusplus_route32_{kind}').read_bytes()
            city = (ROOT / f'data/tilesets/new_bark_cherrygrove_{kind}').read_bytes()
            for block in blocks:
                self.assertEqual(route[block * width:(block + 1) * width],
                                 city[block * width:(block + 1) * width], (kind, block))
        city_collisions = collisions('new_bark_cherrygrove')
        for block in blocks:
            self.assertEqual(self.collisions[block], city_collisions[block])
        # The six route-only graphics must never replace a connection tile.
        meta = (ROOT / 'data/tilesets/redplusplus_route32_metatiles.bin').read_bytes()
        for block in blocks:
            for tile, attr in zip(meta[block * 16:block * 16 + 16], self.attributes[block * 16:block * 16 + 16]):
                self.assertFalse(attr & 8 and 0x80 <= tile <= 0x85)

    def test_tree_priority_and_field_moves(self):
        shared = (ROOT / 'data/tilesets/new_bark_cherrygrove_attributes.bin').read_bytes()
        self.assertEqual(self.attributes[0xb * 16:0xc * 16], shared[0xb * 16:0xc * 16])
        self.assertTrue(any(attr & 128 for attr in self.attributes[0xb * 16:0xc * 16]))
        for alias, original in [(0x1a, 0xf), (0x1c, 0x13)]:
            self.assertEqual(self.collisions[alias], ('HEADBUTT_TREE',) * 4)
            self.assertEqual(self.attributes[alias * 16:alias * 16 + 16], self.attributes[original * 16:original * 16 + 16])
        field_moves = (ROOT / 'data/collision/field_move_blocks.asm').read_text()
        self.assertIn('dbw TILESET_REDPLUSPLUS_ROUTE32, .new_bark_cherrygrove', field_moves)
        for block in [3, 0xb, 0x1b, 0x23, 0x24, 0x56, 0x57, 0x74, 0x75, 0x76, 0x77, 0x96, 0x97, 0xf6, 0xf7]:
            self.assertEqual(self.collisions[block], collisions('new_bark_cherrygrove')[block])

    def test_gate_approach_grass_has_no_priority(self):
        # Priority belongs to a tile's use in a block, not its reused graphic.
        # Keep palette/bank/flip bits while clearing only the foreground flag.
        expected = {
            0xf0: bytes.fromhex('020a00000a020000020a00000a020000'),
            0xf1: bytes.fromhex('0000020a00000a020000020a00000a02'),
        }
        for tileset in ('new_bark_cherrygrove', 'redplusplus_route32'):
            attrs = (ROOT / f'data/tilesets/{tileset}_attributes.bin').read_bytes()
            for block, values in expected.items():
                with self.subTest(tileset=tileset, block=block):
                    self.assertEqual(attrs[block * 16:(block + 1) * 16], values)

    def test_northwest_path_block_has_no_priority(self):
        self.assertEqual(self.attributes[0xd * 16:0xe * 16],
                         bytes.fromhex('00000000000000000202222202022222'))

    def test_additional_ground_blocks_have_no_priority(self):
        for block in (0x17, 0x2a, 0x01, 0x44, 0x45, 0x46, 0x0a):
            with self.subTest(block=block):
                self.assertFalse(any(attr & 128 for attr in
                                     self.attributes[block * 16:(block + 1) * 16]))

    def test_cut_event_exception_and_grotto_return(self):
        self.assertNotIn('EVENT_CHERRYGROVE_BAY_CUT_TREE_1', self.events)
        self.assertRegex(self.events, r'cuttree_event\s+14,\s*23, EVENT_ROUTE_32_CUT_TREE')
        self.assertRegex(self.events, r'cuttree_event\s+-1,\s*30, EVENT_MAGNET_TUNNEL_EAST_CUT_TREE')
        self.assertRegex(self.events, r'bg_event\s+9,\s*27, BGEVENT_JUMPSTD, treegrotto, HIDDENGROTTO_ROUTE_32')
        self.assertRegex((ROOT / 'data/events/hidden_grottoes/grottoes.asm').read_text(), r'; HIDDENGROTTO_ROUTE_32\s+db 5, EVERSTONE, 5')
        violet = (ROOT / 'maps/VioletCity.asm').read_text()
        for x in (13, 14):
            self.assertRegex(violet, rf'(?m)^\s*warp_event\s+{x},\s*37, ROUTE_32, 6')

    def test_petrie_position_and_pushback_path(self):
        self.assertRegex(self.events, r'object_event\s+23,\s*14, SPRITE_ACE_TRAINER_M, SPRITEMOVEDATA_STANDING_LEFT,.*Route32CooltrainermPetrieScript')
        triggers = re.findall(r'^\s*coord_event\s+(\d+),\s*(\d+), SCENE_ROUTE32_COOLTRAINER_M_BLOCKS, Route32CooltrainerMStopsYou', self.events, re.M)
        self.assertEqual(triggers, [('22', '14')])
        for x, y in [(23, 14), (22, 14), (22, 13), (22, 12)]:
            self.assertEqual(self.collision(x, y), 'FLOOR')
        self.assertRegex(self.events, r'Movement_Route32CooltrainerMPushesYouBackToViolet:\s+step_up\s+step_up\s+step_end')
        self.assertRegex(self.events, r'Movement_Route32CooltrainerMReset:\s+step_down\s+step_right\s+step_end')
        self.assertNotIn('Movement_Route32CooltrainerMLeft', self.events)
        self.assertNotIn('Movement_Route32CooltrainerMRight', self.events)


if __name__ == '__main__':
    unittest.main()
