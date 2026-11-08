#!/usr/bin/env python3
"""Assemble real audio macros and check the compact operand encodings."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRELUDE = '''INCLUDE "macros/const.asm"
INCLUDE "macros/data.asm"
INCLUDE "macros/scripts/audio.asm"
SECTION "Audio encoding fixture", ROM0[$100]
Fixture:
'''


class AudioEncodingTests(unittest.TestCase):
    def assemble(self, body, rejection=None):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fixture.asm"
            obj = source.with_suffix(".o")
            rom = source.with_suffix(".gbc")
            symbols = source.with_suffix(".sym")
            source.write_text(PRELUDE + body + "\nFixtureEnd:\n")
            assembled = subprocess.run(
                ["rgbasm", "-o", str(obj), str(source)], cwd=ROOT,
                capture_output=True, text=True,
            )
            if rejection is not None:
                self.assertNotEqual(assembled.returncode, 0)
                self.assertIn(rejection, assembled.stderr)
                return
            self.assertEqual(assembled.returncode, 0, assembled.stderr)
            subprocess.run(
                ["rgblink", "-o", str(rom), "-n", str(symbols), str(obj)],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            end = int(re.search(
                r"^00:([0-9a-fA-F]+) FixtureEnd$", symbols.read_text(), re.M,
            )[1], 16)
            return rom.read_bytes()[0x100:end]

    def test_short_pitch_offsets(self):
        for value in (0, 1, 2, 32, 127):
            with self.subTest(value=value):
                self.assertEqual(self.assemble(f"pitch_offset {value}\n"),
                                 bytes((0xe7, value)))

    def test_pitch_offsets_with_marker_bit_use_extended_encoding(self):
        for value in (128, 129, 255):
            with self.subTest(value=value):
                self.assertEqual(self.assemble(f"pitch_offset {value}\n"),
                                 bytes((0xe7, 0x80, value)))

    def test_wide_pitch_offsets_include_existing_radio_values(self):
        for value in (256, 280, 4376, 0x7fff):
            with self.subTest(value=value):
                self.assertEqual(self.assemble(f"pitch_offset {value}\n"),
                                 bytes((0xe7, 0x80 | (value >> 8), value & 255)))

    def test_out_of_range_pitch_offset_is_rejected(self):
        self.assemble("pitch_offset $8000\n", rejection="out of range")

    def test_relative_loop_offset_supports_page_borrow(self):
        # Target is $1f0, next command is $213: the decoder must borrow a page.
        data = self.assemble("ds $f0\n.target:\nds $20\nsound_loop 2, .target\n")
        self.assertEqual(data[-3:], bytes((0xfd, 2, 0x23)))
        self.assertEqual(0x100 + len(data) - data[-1], 0x1f0)

    def test_maximum_relative_loop_distance(self):
        data = self.assemble(".target:\nds 252\nsound_loop 255, .target\n")
        self.assertEqual(data[-3:], bytes((0xfd, 255, 255)))

    def test_overlong_and_forward_loops_are_rejected(self):
        self.assemble(".target:\nds 253\nsound_loop 2, .target\n",
                      rejection="cannot go that far")
        self.assemble("sound_loop 2, .target\nds 1\n.target:\n",
                      rejection="cannot go forwards")

    def test_pointless_loop_counts_are_rejected(self):
        for count in (0, 1):
            with self.subTest(count=count):
                self.assemble(f".target:\nsound_loop {count}, .target\n",
                              rejection=f"sound_loop {count}")


if __name__ == "__main__":
    unittest.main()
