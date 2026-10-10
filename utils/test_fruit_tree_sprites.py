#!/usr/bin/env python3
"""Shared fruit-tree sprite placement, independent of map and fruit color."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FruitTreeSpriteTests(unittest.TestCase):
    def facing(self, name):
        source = (ROOT / 'data/sprites/facings.asm').read_text()
        section = source.split(name + ':', 1)[1].split('\nFacing', 1)[0]
        return [line.strip() for line in section.splitlines() if line.strip()]

    def test_apricorn_fruit_is_four_pixels_higher(self):
        self.assertEqual(self.facing('FacingApricorn'), [
            'db 2 ; #',
            'db -4,  4, 0, $05',
            'db 10,  4, FIXED_BROWN_PALETTE, $06',
        ])

    def test_berries_and_picked_trunks_keep_their_positions(self):
        self.assertEqual(self.facing('FacingBerry'), [
            'db 2 ; #',
            'db  4,  3, 0, $04',
            'db 10,  4, FIXED_BROWN_PALETTE, $06',
        ])
        self.assertEqual(self.facing('FacingPickedFruit'), [
            'db 1 ; #',
            'db 10,  4, FIXED_BROWN_PALETTE, $06',
        ])

    def test_all_apricorn_tree_ids_select_the_shared_facing(self):
        source = (ROOT / 'engine/overworld/map_object_action.asm').read_text()
        section = source.split('SetFacingFruit:', 1)[1].split('SetFacingBigGyarados:', 1)[0]
        self.assertRegex(section, r'cp FIRST_BERRY_TREE - 1')
        self.assertRegex(section, r'assert FACING_APRICORN \+ 1 == FACING_BERRY')
        self.assertRegex(section, r'sbc a\s+add FACING_BERRY')
        self.assertIn('ld a, FACING_PICKED_FRUIT', section)


if __name__ == '__main__':
    unittest.main()
