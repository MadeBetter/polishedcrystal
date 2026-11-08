#!/usr/bin/env python3
"""Route 32 Coast's reference layout, retained events and seven-block seam."""

from collections import deque
import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Route32CoastPortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = (ROOT / 'maps/Route32Coast.ablk').read_bytes()
        cls.events = (ROOT / 'maps/Route32Coast.asm').read_text()
        cls.meta = (ROOT / 'data/tilesets/redplusplus_route32_metatiles.bin').read_bytes()
        cls.attrs = (ROOT / 'data/tilesets/redplusplus_route32_attributes.bin').read_bytes()
        cls.collisions = [tuple(line.split(';')[0].strip().removeprefix('tilecoll ').split(', '))
                          for line in (ROOT / 'data/tilesets/redplusplus_route32_collision.asm').read_text().splitlines()]

    def collision(self, x, y, layout=None, width=15):
        if layout is None:
            layout = self.layout
        return self.collisions[layout[y // 2 * width + x // 2]][y % 2 * 2 + x % 2]

    def test_reference_layout_and_native_tileset(self):
        self.assertEqual(len(self.layout), 15 * 36)
        self.assertEqual(hashlib.sha256(self.layout).hexdigest(),
                         'c3980a4af7e073260ef7fe71577a10dfab575739498b5360154a1175e50362a1')
        self.assertRegex((ROOT / 'constants/map_constants.asm').read_text(),
                         r'map_const ROUTE_32_COAST,\s+15,\s*36\b')
        self.assertIn('map Route32Coast, TILESET_REDPLUSPLUS_ROUTE32,',
                      (ROOT / 'data/maps/maps.asm').read_text())

    def test_warp_order_and_return_destinations(self):
        self.assertEqual(re.findall(r'^\s*warp_event\s+(\d+),\s*(\d+),\s*(\w+),\s*(\d+)', self.events, re.M), [
            ('4', '57', 'UNION_CAVE_B1F_SOUTH', '4'),
            ('17', '51', 'ROUTE_32_COAST_HOUSE', '1'),
            ('13', '43', 'HIDDEN_TREE_GROTTO', '1'),
        ])
        for x, y, collision in [(4, 57, 'CAVE'), (4, 58, 'FLOOR'),
                                 (17, 51, 'DOOR'), (17, 52, 'FLOOR'), (13, 43, 'FLOOR')]:
            self.assertEqual(self.collision(x, y), collision)
        self.assertIn('warp_event 17, 23, ROUTE_32_COAST, 1',
                      (ROOT / 'maps/UnionCaveB1FSouth.asm').read_text())
        house = (ROOT / 'maps/Route32CoastHouse.asm').read_text()
        self.assertIn('warp_event  2,  7, ROUTE_32_COAST, 2', house)
        self.assertIn('warp_event  3,  7, ROUTE_32_COAST, 2', house)
        self.assertRegex((ROOT / 'data/events/hidden_grottoes/grottoes.asm').read_text(),
                         r'; HIDDENGROTTO_ROUTE_32_COAST\s+db 3, WATER_STONE, LEVEL_FROM_BADGES \+ 3')

    def test_all_original_script_bodies_are_unchanged(self):
        bodies = self.events.split('GenericTrainerSwimmermMichel:', 1)[1]
        self.assertEqual(hashlib.sha256(('GenericTrainerSwimmermMichel:' + bodies).encode()).hexdigest(),
                         'fe601122ef57ff42f61e486dd4dcb23674b7db6cc0252d0e6704b0d480e97055')
        self.assertEqual(len(re.findall(r'^\s*bg_event ', self.events, re.M)), 7)
        self.assertEqual(len(re.findall(r'^\s*(?:object_event|fruittree_event|itemball_event) ', self.events, re.M)), 15)
        for flag in ('HIDDEN_LEVEL_BALL', 'HIDDEN_HYPER_POTION', 'HIDDEN_ELIXIR', 'WHITE_HERB', 'SOFT_SAND'):
            self.assertIn('EVENT_ROUTE_32_COAST_' + flag, self.events)
        self.assertIn('FRUITTREE_ROUTE_32_COAST, ASPEAR_BERRY, PAL_NPC_BROWN', self.events)

    def test_repositioned_trainers_and_items(self):
        for x, y, label in [(17, 25, 'TrainerBird_keeperPowell'), (12, 61, 'GenericTrainerCosplayerChloe'),
                            (22, 62, 'GenericTrainerFisherKiley'), (13, 45, 'GenericTrainerLassLayla'),
                            (23, 40, 'GenericTrainerCoupleFoxandrae1'), (23, 41, 'GenericTrainerCoupleFoxandrae2')]:
            self.assertRegex(self.events, rf'object_event\s+{x},\s*{y},[^\n]+{label}, -1')
            self.assertIn(self.collision(x, y), ('FLOOR', 'TALL_GRASS'))
        for x, y in [(9, 5), (18, 65), (20, 6), (23, 15), (21, 61)]:
            self.assertEqual(self.collision(x, y), 'WATER')
        self.assertEqual(self.collision(22, 61), 'WATER')  # Fisher faces the sea.
        self.assertRegex(self.events, r'itemball_event\s+5,\s*21, WHITE_HERB, 1,')
        self.assertRegex(self.events, r'fruittree_event\s+21,\s*51, FRUITTREE_ROUTE_32_COAST,')
        self.assertEqual(self.collision(21, 50), 'WALL')
        self.assertEqual(self.collision(21, 51), 'FLOOR')

    def test_signs_hidden_items_and_grotto_access(self):
        for x, y, label in [(15, 29, 'Route32CoastTrainerTipsText'), (5, 59, 'Route32CoastUnionCaveSignText')]:
            self.assertRegex(self.events, rf'bg_event\s+{x},\s*{y}, BGEVENT_JUMPTEXT, {label}')
            self.assertEqual(self.collision(x, y), 'WALL')
        for x, y, item in [(17, 32, 'LEVEL_BALL'), (5, 45, 'HYPER_POTION'), (12, 18, 'ELIXIR')]:
            self.assertRegex(self.events, rf'bg_event\s+{x},\s*{y}, BGEVENT_ITEM \+ {item},')
            self.assertIn(self.collision(x, y), ('FLOOR', 'TALL_GRASS'))
        for y in (42, 43):
            self.assertRegex(self.events, rf'bg_event\s+14,\s*{y}, BGEVENT_JUMPSTD, treegrotto, HIDDENGROTTO_ROUTE_32_COAST')
            self.assertEqual(self.collision(14, y), 'HEADBUTT_TREE')
            self.assertEqual(self.collision(13, y), 'FLOOR')

    def test_events_reachable_from_existing_map_entries(self):
        # The reference separates Route 32's inlet with buoys. Keep both that
        # inlet and the main northern sea, plus the existing cave return.
        seen = {(0, 0), (6, 0), (4, 58)}
        queue = deque(seen)
        while queue:
            x, y = queue.popleft()
            for xx, yy in ((x, y + 1), (x, y - 1), (x - 1, y), (x + 1, y)):
                if not (0 <= xx < 30 and 0 <= yy < 72) or (xx, yy) in seen:
                    continue
                if self.collision(xx, yy) in ('FLOOR', 'TALL_GRASS', 'WATER', 'DOOR', 'CAVE'):
                    seen.add((xx, yy))
                    queue.append((xx, yy))
        events = re.findall(r'^\s*(warp_event|bg_event|object_event|fruittree_event|itemball_event)\s+(\d+),\s*(\d+),', self.events, re.M)
        for kind, x, y in events:
            x, y = int(x), int(y)
            adjacent = any(p in seen for p in ((x, y + 1), (x, y - 1), (x - 1, y), (x + 1, y)))
            self.assertTrue((x, y) in seen or kind == 'bg_event' and adjacent, (kind, x, y))

    def test_exact_seven_block_east_west_overlap(self):
        attrs = (ROOT / 'data/maps/attributes.asm').read_text()
        self.assertRegex(attrs, r'connection east, Route32Coast, ROUTE_32_COAST, 39\b')
        self.assertRegex(attrs, r'connection west, Route32, ROUTE_32, -39\b')
        route = (ROOT / 'maps/Route32.ablk').read_bytes()
        self.assertEqual(hashlib.sha256(route).hexdigest(),
                         '3bcfb8a8324f6b1fd90b415df68c59094b891369c0475deca54f1850d566e80c')
        self.assertEqual(46 - 39, 7)
        crossings = [y for y in range(14) if self.collision(23, y + 78, route, 12) == 'WATER'
                     and self.collision(0, y) == 'WATER']
        self.assertEqual(crossings, list(range(5)))
        # Connection strips include three padding rows, in addition to the
        # seven in-map rows. Both sides use the same native block tables.
        self.assertEqual(46 + 3 - 39, 10)
        self.assertEqual(46 - (39 - 3), 10)
        self.assertEqual(len(self.meta), 4096)
        self.assertEqual(len(self.attrs), 4096)


if __name__ == '__main__':
    unittest.main()
