#!/usr/bin/env python3
# Quantize a PNG to 4-shade grayscale (0, 85, 170, 255).

import sys
from pathlib import Path

sys.path.append("utils")
import png


def to_gray(rgb):
    r, g, b = rgb
    return (299 * r + 587 * g + 114 * b) // 1000


def quantize_gray(value):
    levels = (0, 85, 170, 255)
    return min(levels, key=lambda lv: abs(value - lv))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: tools/quantize_gray4.py path/to/image.png")
        return 2

    path = Path(sys.argv[1])
    reader = png.Reader(filename=str(path))
    width, height, rows, info = reader.read()
    rows = list(rows)

    palette = info.get("palette")
    if palette is None:
        raise SystemExit("expected a paletted PNG")

    gray_palette = [to_gray(rgb) for rgb in palette]

    qrows = []
    for row in rows:
        new_row = []
        for idx in row:
            new_row.append(quantize_gray(gray_palette[idx]))
        qrows.append(new_row)

    with path.open("wb") as f:
        writer = png.Writer(width, height, greyscale=True, bitdepth=8)
        writer.write(f, qrows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
