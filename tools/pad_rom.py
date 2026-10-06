#!/usr/bin/env python3
"""Pad a linked ROM without silently truncating an oversized build."""

import argparse
from pathlib import Path


def pad_rom(path: Path, size: int, filler: int) -> None:
    actual = path.stat().st_size
    if actual > size:
        raise ValueError(f"{path}: linked ROM is {actual} bytes; limit is {size}")
    if not 0 <= filler <= 255:
        raise ValueError("padding byte must be between 0 and 255")
    with path.open("ab") as rom:
        rom.write(bytes([filler]) * (size - actual))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("size", type=lambda value: int(value, 0))
    parser.add_argument("filler", type=lambda value: int(value, 0))
    args = parser.parse_args()
    try:
        pad_rom(args.rom, args.size, args.filler)
    except ValueError as error:
        parser.exit(1, f"error: {error}\n")
