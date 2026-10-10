#!/usr/bin/env python3
"""Route 36/31 gate shrubs and the Route 36 grotto's shared block variants."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ('new_bark_cherrygrove', 'redplusplus_ecruteak', 'redplusplus_route32')


class Route36BGUpdateTests(unittest.TestCase):
    def table(self, family, kind):
        return (ROOT / f'data/tilesets/{family}_{kind}.bin').read_bytes()

    def collisions(self, family):
        return [tuple(line.split(';')[0].strip().removeprefix('tilecoll ').split(', '))
                for line in (ROOT / f'data/tilesets/{family}_collision.asm').read_text().splitlines()
                if line.lstrip().startswith('tilecoll ')]

    def test_map_positions_and_normal_tree(self):
        route = (ROOT / 'maps/Route36.ablk').read_bytes()
        self.assertEqual(len(route), 24 * 10)
        for (x, y), block in {(20, 2): 0x8b, (20, 3): 0xf3,
                              (22, 5): 0xa4, (23, 5): 0xee, (9, 7): 0x13}.items():
            self.assertEqual(route[y * 24 + x], block)
        route = (ROOT / 'maps/Route31.ablk').read_bytes()
        self.assertEqual(len(route), 22 * 9)
        self.assertEqual(route[3 * 22:3 * 22 + 2], b'\xa4\xee')

    def test_shared_variants_preserve_source_attributes_and_priority(self):
        for family in FAMILIES:
            meta = self.table(family, 'metatiles')
            attrs = self.table(family, 'attributes')
            for new, source in [(0xa4, 0x88), (0xee, 0x8a), (0x8b, 0x1f), (0xf3, 0x23)]:
                expected_meta = bytearray(meta[source * 16:(source + 1) * 16])
                expected_attrs = bytearray(attrs[source * 16:(source + 1) * 16])
                patches = {13: (0x31, 0x02), 14: (0x31, 0x22)} if new in (0xa4, 0xee) else (
                    {14: (0xef, 0x0a), 15: (0xf7, 0x0a)} if new == 0x8b else
                    {2: (0xf8, 0x0a), 3: (0xf9, 0x0a)})
                for index, (tile, attr) in patches.items():
                    expected_meta[index] = tile
                    expected_attrs[index] = (expected_attrs[index] & 0x90) | attr
                self.assertEqual(meta[new * 16:(new + 1) * 16], expected_meta)
                self.assertEqual(attrs[new * 16:(new + 1) * 16], expected_attrs)
                self.assertEqual([a & 128 for a in expected_attrs],
                                 [a & 128 for a in attrs[source * 16:(source + 1) * 16]])
            self.assertEqual(meta[0x88 * 16 + 13:0x88 * 16 + 15], b'\x7e\x7e')
            self.assertEqual(meta[0x8a * 16 + 13:0x8a * 16 + 15], b'\x7e\x7e')

    def test_boundary_ids_and_collisions_match_across_blocksets(self):
        for block, collision in [(0xa4, ('WALL',) * 4), (0xee, ('WALL',) * 4),
                                 (0x8b, ('HEADBUTT_TREE',) * 4),
                                 (0xf3, ('HEADBUTT_TREE', 'HEADBUTT_TREE', 'FLOOR', 'FLOOR'))]:
            for kind in ('metatiles', 'attributes'):
                expected = self.table(FAMILIES[0], kind)[block * 16:(block + 1) * 16]
                for family in FAMILIES[1:]:
                    self.assertEqual(self.table(family, kind)[block * 16:(block + 1) * 16], expected)
            for family in FAMILIES:
                self.assertEqual(self.collisions(family)[block], collision)

    def test_gate_reuses_existing_common_graphic_with_mirroring(self):
        for family in FAMILIES:
            meta = self.table(family, 'metatiles')
            attrs = self.table(family, 'attributes')
            for block in (0xa4, 0xee):
                self.assertEqual(meta[block * 16 + 13:block * 16 + 15], b'\x31\x31')
                self.assertEqual(attrs[block * 16 + 13:block * 16 + 15], b'\x02\x22')
        shared = ROOT / 'gfx/tilesets/redplusplus_johto_common.2bpp'
        if not shared.exists():
            self.skipTest('run make to check the generated common BG graphics')
        self.assertEqual(shared.read_bytes()[0x31 * 16:0x32 * 16],
                         bytes.fromhex('f7f8ef906f900ff047f8b3ccb1ce80ff'))


if __name__ == '__main__':
    unittest.main()
