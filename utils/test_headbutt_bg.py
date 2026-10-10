#!/usr/bin/env python3
"""Guard Headbutt BG artwork, collision eligibility, and rendering contracts.

Run after `make` to include the generated 2bpp graphics check.
"""

import hashlib
from pathlib import Path
import re
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HeadbuttBGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.moves = (ROOT / 'engine/events/field_moves.asm').read_text()
        cls.animation = cls.moves.split('ShakeHeadbuttTree:', 1)[1].split('OWCutAnimation:', 1)[0]

    def test_seven_tile_asset_and_color_indices(self):
        png = (ROOT / 'gfx/overworld/headbutt_tree_bg.png').read_bytes()
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', png[16:24]), (56, 8))
        compiled = ROOT / 'gfx/overworld/headbutt_tree_bg.2bpp'
        if not compiled.exists():
            self.skipTest('run make to check the compiled graphics')
        data = compiled.read_bytes()
        self.assertEqual(len(data), 7 * 16)
        # Original strip, with grass/light green/dark green/outline as indices 0-3.
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         '380dfc7a826676d6ad9c57ac0842b8e15bb8dab8f8a18eede3f981b84904a98d')

    def test_font_workspace_not_used_by_metatiles(self):
        for path in (ROOT / 'data/tilesets').glob('*_metatiles.bin'):
            attrs = path.with_name(path.name.replace('_metatiles', '_attributes')).read_bytes()
            tiles = path.read_bytes()
            self.assertEqual(len(tiles), len(attrs))
            for i, (tile, attr) in enumerate(zip(tiles, attrs)):
                self.assertFalse(0xe0 <= tile <= 0xe6 and not attr & 8,
                                 (path.name, hex(i // 16), i % 16))

    def test_native_tree_signatures_and_flips(self):
        for name, body, base in [('new_bark_cherrygrove', 0xf, 0x13),
                                 ('redplusplus_ecruteak', 0xf, 0x13),
                                 ('redplusplus_route32', 0x1a, 0x1c)]:
            tiles = (ROOT / f'data/tilesets/{name}_metatiles.bin').read_bytes()
            attrs = (ROOT / f'data/tilesets/{name}_attributes.bin').read_bytes()
            for block, variant in [(body, 0x20), (base, 0x61), (0xaa, 0x20)]:
                start = block * 16
                expected = bytes([0x40, 0x41, 0x41, 0x40, 0x50, 0x51, 0x51, 0x50,
                                  0x60, variant, variant, 0x60])
                edge = block == 0xaa
                if edge:
                    expected = bytes([0xfb]) + expected[1:]
                self.assertEqual(tiles[start:start+12], expected, (name, block))
                self.assertEqual(bytes(a & 0x68 for a in attrs[start:start+12]),
                                 bytes([8 if edge else 0, 0, 32, 32] + [0, 0, 32, 32] * 2))

    def test_bushes_and_tree_caps_are_not_headbutt_targets(self):
        # Exact 16x16 quadrants from the supplied bush and two tree-cap halves.
        # Match bank/orientation as well as IDs, since IDs alone are ambiguous.
        excluded = {
            (0x12, 0x12, 0x22, 0x22): (0, 32, 0, 32),
            (0x12, 0x13, 0x23, 0x31): (0, 0, 0, 0),
            (0x13, 0x12, 0x31, 0x23): (32, 32, 32, 32),
        }
        for name in ('new_bark_cherrygrove', 'redplusplus_ecruteak', 'redplusplus_route32'):
            tiles = (ROOT / f'data/tilesets/{name}_metatiles.bin').read_bytes()
            attrs = (ROOT / f'data/tilesets/{name}_attributes.bin').read_bytes()
            collisions = self.collisions(name)
            matched = set()
            for block in range(256):
                for quadrant in range(4):
                    start = block * 16 + quadrant // 2 * 8 + quadrant % 2 * 2
                    indices = (start, start + 1, start + 4, start + 5)
                    pattern = tuple(tiles[i] for i in indices)
                    if pattern in excluded and tuple(attrs[i] & 0x68 for i in indices) == excluded[pattern]:
                        self.assertNotEqual(collisions[block][quadrant], 'HEADBUTT_TREE',
                                            (name, hex(block), quadrant))
                        matched.add(pattern)
            self.assertEqual(matched, set(excluded), name)

    @staticmethod
    def collisions(name):
        return [tuple(line.split(';')[0].strip().removeprefix('tilecoll ').split(', '))
                for line in (ROOT / f'data/tilesets/{name}_collision.asm').read_text().splitlines()
                if line.lstrip().startswith('tilecoll ')]

    def test_excluded_cells_stay_solid_and_tree_bodies_stay_headbuttable(self):
        for name in ('new_bark_cherrygrove', 'redplusplus_ecruteak', 'redplusplus_route32'):
            collisions = self.collisions(name)
            self.assertEqual(collisions[0x80], ('WALL', 'WALL', 'FLOOR', 'FLOOR'))
            self.assertEqual(collisions[0x85], ('FLOOR', 'WALL', 'FLOOR', 'WALL'))
            self.assertEqual(collisions[0xaa], ('HEADBUTT_TREE',) * 4)
        forest = self.collisions('redplusplus_ecruteak')
        for block in (0xf, 0x13):
            self.assertEqual(forest[block], ('HEADBUTT_TREE',) * 4)
        for block in (0x25, 0x7b, 0x9d, 0xda):
            self.assertEqual(forest[block].count('HEADBUTT_TREE'), 2)
        route = self.collisions('redplusplus_route32')
        for block in (0x1a, 0x1c):
            self.assertEqual(route[block], ('HEADBUTT_TREE',) * 4)
        self.assertEqual(route[0xd][2:], ('FLOOR', 'FLOOR'))

    def test_only_bg_queue_is_modified(self):
        for prohibited in ['wShadowOAM', 'InitSpriteAnimStruct', 'ClearSpriteAnims',
                           'CopyBGGreenToOBPal7', 'wOverworldMapBlocks', 'RandomRange']:
            self.assertNotIn(prohibited, self.animation)
        self.assertIn('wBGMapBufferPtrs', self.animation)
        self.assertIn('ldh [hBGMapTileCount], a', self.animation)
        self.assertIn('and ~(BG_BANK1 | BG_YFLIP)', self.animation)
        self.assertNotIn('and $7f', self.animation)  # Never strip tree priority.

    def test_three_shakes_and_exact_queue_size(self):
        routine = self.animation.split('FindHeadbuttTree:', 1)[0]
        states = re.findall(r'(ld a, TRUE|xor a)\s+call QueueHeadbuttTree', routine)
        self.assertEqual(states, ['ld a, TRUE', 'xor a'] * 3)
        delays = re.findall(r'ld c, (\d+)\s+call HeadbuttDelayFrames', routine)
        self.assertEqual(delays, ['4', '4', '4', '3', '3', '14'])
        self.assertEqual(sum(map(int, delays)), 32)
        queue = self.animation.split('QueueHeadbuttTree:', 1)[1]
        self.assertRegex(queue, r'ld a, 6\s+ldh \[hBGMapTileCount\], a')

    def test_no_legacy_fallback_and_gameplay_entry_unchanged(self):
        self.assertIn('cp BANK(TilesetNewBarkCherrygroveGFX0)', self.animation)
        self.assertIn('cp LOW(TilesetNewBarkCherrygroveGFX0)', self.animation)
        self.assertIn('cp HIGH(TilesetNewBarkCherrygroveGFX0)', self.animation)
        self.assertNotIn('HeadbuttTree2GFX', self.animation)
        script = (ROOT / 'engine/events/overworld.asm').read_text()
        self.assertRegex(script, r'AutoHeadbuttScript:\s+reanchormap\s+callasm ShakeHeadbuttTree\s+callasm TreeMonEncounter')
        self.assertIn('callasm TreeItemEncounter', script)

    def test_selected_font_restored_in_existing_scratch_union(self):
        font = (ROOT / 'engine/gfx/load_font.asm').read_text()
        restore = font.split('RestoreHeadbuttFontTiles::', 1)[1].split('LoadStandardFontPointer::', 1)[0]
        self.assertIn('call LoadStandardFontPointer', restore)
        self.assertIn("(HEADBUTT_BG_TILE - 'A') * TILE_1BPP_SIZE", restore)
        self.assertIn('NUM_HEADBUTT_BG_TILES', restore)
        self.assertIn('jmp Get1bpp', restore)
        ram = (ROOT / 'ram/wramx.asm').read_text()
        self.assertRegex(ram, r'wFieldMoveDataEnd::\s+NEXTU\s+;[^\n]+\s+wHeadbuttTilemapPointer:: dw')
        self.assertRegex(ram, r'wHeadbuttShakeState:: db\s+NEXTU')


if __name__ == '__main__':
    unittest.main()
