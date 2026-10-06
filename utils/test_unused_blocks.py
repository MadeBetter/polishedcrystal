#!/usr/bin/env python3
"""Check the block-usage utility against current map tileset assignments."""

import ast
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UnusedBlockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((ROOT / "utils/unused_blocks.py").read_text())
        cls.tileset_maps = next(
            ast.literal_eval(node.value)
            for node in tree.body if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "tileset_maps"
                for target in node.targets
            )
        )
        cls.actual_maps = dict(re.findall(
            r"^\s*map\s+(\w+),\s*TILESET_(\w+),",
            (ROOT / "data/maps/maps.asm").read_text(), re.M,
        ))
        # These are alternate/shared block layouts, not separate map headers.
        cls.actual_maps["LuckyIslandHidden"] = cls.actual_maps["LuckyIsland"]
        cls.actual_maps["ElementalIsland"] = cls.actual_maps["FireIslandRoof"]

    def test_assignments_match_map_headers_without_duplicates(self):
        seen = set()
        for tileset, names in self.tileset_maps.items():
            for name in names.split():
                with self.subTest(map=name, tileset=tileset):
                    self.assertNotIn(name, seen)
                    seen.add(name)
                    # Rain/flood block layouts use their base map's header.
                    base = re.sub(r"(?:Raining|Flooded)$", "", name)
                    self.assertIn(base, self.actual_maps)
                    self.assertEqual(self.actual_maps[base].lower(), tileset)

    def test_every_ported_tileset_map_is_included(self):
        for name, tileset in self.actual_maps.items():
            key = tileset.lower()
            if key not in {
                "new_bark_cherrygrove", "azalea_blackthorn", "redplusplus_ecruteak",
            }:
                continue
            with self.subTest(map=name):
                self.assertIn(name, self.tileset_maps[key].split())

    def test_report_matches_raw_block_usage(self):
        expected = []
        for tileset, names in self.tileset_maps.items():
            blocks = (ROOT / f"data/tilesets/{tileset}_metatiles.bin").read_bytes()
            self.assertEqual(len(blocks) % 16, 0)
            used = set()
            for name in names.split():
                used.update((ROOT / f"maps/{name}.ablk").read_bytes())
            unused = sorted(set(range(1, len(blocks) // 16)) - used)
            values = " ".join(f"{block:02x}" for block in unused)
            expected.append(f"# {tileset}: {values}")
        result = subprocess.run(
            [sys.executable, str(ROOT / "utils/unused_blocks.py")],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), expected)


if __name__ == "__main__":
    unittest.main()
