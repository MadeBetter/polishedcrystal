#!/usr/bin/env python3
"""Check MBC30 build output and safe padding. Run after make; no saves are used."""

import argparse
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROM = ROOT / "polishedcrystal-3.2.3.gbc"
pad_rom = runpy.run_path(str(ROOT / "tools/pad_rom.py"))["pad_rom"]


class MBC30BuildTests(unittest.TestCase):
    rom = DEFAULT_ROM

    def test_rom_header_and_checksums(self):
        rom = self.rom.read_bytes()
        self.assertEqual(len(rom), 0x400000)
        self.assertEqual(rom[0x147:0x14a], bytes((0x10, 0x07, 0x03)))
        self.assertEqual(rom[0x14d], (-sum(rom[0x134:0x14d]) - 25) & 255)
        self.assertEqual(
            int.from_bytes(rom[0x14e:0x150], "big"),
            (sum(rom[:0x14e]) + sum(rom[0x150:])) & 0xffff,
        )

    def test_all_linked_banks_fit_and_checker_accepts_them(self):
        banks = [
            int(n) for n in re.findall(
                r"^ROMX bank #(\d+):", self.rom.with_suffix(".map").read_text(), re.M,
            )
        ]
        self.assertTrue(banks)
        self.assertLess(max(banks), 256)
        result = subprocess.run(
            [str(ROOT / "tools/bankends"), "-q", str(self.rom.with_suffix(".map"))],
            capture_output=True, text=True, check=True,
        )
        self.assertIn("/4194304", result.stdout)

    def test_padding_preserves_data_and_fills_with_ff(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.gbc"
            path.write_bytes(bytes((0, 1, 128, 255)))
            pad_rom(path, 8, 255)
            self.assertEqual(
                path.read_bytes(), bytes((0, 1, 128, 255, 255, 255, 255, 255)),
            )
            pad_rom(path, 8, 255)
            self.assertEqual(path.stat().st_size, 8)

    def test_oversized_rom_is_not_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.gbc"
            original = bytes(range(16))
            path.write_bytes(original)
            with self.assertRaises(ValueError):
                pad_rom(path, 8, 255)
            self.assertEqual(path.read_bytes(), original)

    def test_padding_rejects_invalid_filler_without_modifying_rom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.gbc"
            path.write_bytes(b"unchanged")
            with self.assertRaises(ValueError):
                pad_rom(path, 16, 256)
            self.assertEqual(path.read_bytes(), b"unchanged")

    def test_bank_checker_rejects_bank_256(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overflow.map"
            path.write_text(
                'ROMX bank #256:\n\tSECTION: $4000-$4001 ($0002 bytes) ["overflow"]\n',
            )
            result = subprocess.run(
                [str(ROOT / "tools/bankends"), "-q", str(path)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown ROM bank $100", result.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", nargs="?", type=Path, default=DEFAULT_ROM)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    MBC30BuildTests.rom = args.rom
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MBC30BuildTests)
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
