#!/usr/bin/env python3
"""Exercise the built LZP tool's CLI and compression-format boundaries."""

from pathlib import Path
import random
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/lzpcompress"
PACK16 = bytes((0, 255, 1, 2, 3, 254, 128, 7, 192, 127, 4, 15, 31, 63, 8, 252))


class LZPCompressorTests(unittest.TestCase):
    def run_tool(self, *args, data=b"", success=True):
        result = subprocess.run([str(TOOL), *args], input=data,
                                capture_output=True, cwd=ROOT)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        else:
            self.assertNotEqual(result.returncode, 0)
        return result.stdout

    def test_long_options_without_equals(self):
        self.run_tool("--help")
        self.assertEqual(self.run_tool("--binary", data=b""), b"\xff")
        packed = self.run_tool("--binary", data=b"hello")
        self.assertEqual(self.run_tool("--uncompress", data=packed), b"hello")

    def test_long_options_with_equals(self):
        packed = self.run_tool("--align=0", data=b"hello")
        self.assertEqual(packed, self.run_tool("-a0", data=b"hello"))
        self.run_tool("--binary=unexpected", success=False)
        self.run_tool("--align=invalid", success=False)
        self.run_tool("--align=13", success=False)
        self.run_tool("--align", success=False)

    def test_round_trips_patterns_and_command_length_boundaries(self):
        rng = random.Random(0)
        for length in (0, 1, 2, 3, 31, 32, 33, 255, 256, 257, 511, 512, 513):
            for name, data in (
                ("random", bytes(rng.randrange(256) for _ in range(length))),
                ("zeros", bytes(length)),
                ("repeat", b"\xa5" * length),
                ("alternate", (b"\x5a\xa5" * length)[:length]),
                ("low nibbles", bytes(rng.randrange(16) for _ in range(length))),
            ):
                with self.subTest(length=length, pattern=name):
                    packed = self.run_tool(data=data)
                    self.assertEqual(self.run_tool("-u", data=packed), data)

    def test_special_pack_commands_accept_full_256_byte_length(self):
        for length in (1, 2, 255, 256):
            for opcode in (0xfc, 0xfd, 0xfe):
                with self.subTest(length=length, opcode=opcode):
                    payload = bytes(range((length + 1) // 2))
                    nibbles = [n for value in payload for n in (value >> 4, value & 15)][:length]
                    expected = bytes((n << 4) if opcode == 0xfc else
                                     PACK16[n] if opcode == 0xfd else n for n in nibbles)
                    packed = bytes((opcode, length - 1)) + payload + b"\xff"
                    self.assertEqual(self.run_tool("-u", data=packed), expected)
                    self.run_tool("--dump", data=packed)

    def test_binary_alignment_and_padding_round_trip(self):
        raw = bytes(range(40))
        for args in (("--align=4",), ("--align", "4"), ("-a4",)):
            with self.subTest(args=args):
                packed = self.run_tool(*args, data=raw)
                self.assertEqual(len(packed) % 16, 0)
                self.assertEqual(self.run_tool("-u", data=packed), raw)

    def test_text_alignment_matches_dump_and_nonzero_trailing_data_is_rejected(self):
        raw = bytes(range(40))
        packed = self.run_tool("--align=4", data=raw)
        text = self.run_tool("--text", "--align=4", data=raw)
        self.assertEqual(text, self.run_tool("--dump", data=packed))
        self.assertIn(b"\tdb 0", text)
        self.run_tool("-u", data=packed + b"\x01", success=False)

    def test_truncated_input_is_rejected(self):
        for data in (b"", b"\xfc", b"\xfc\xff\x00", b"\x02\x01"):
            with self.subTest(data=data):
                self.run_tool("-u", data=data, success=False)


if __name__ == "__main__":
    unittest.main()
