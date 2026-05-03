"""Generate icon.ico using only the standard library.

The icon mirrors the brand mark in the UI: a 2x2 grid where the
top-left cell is amber and the others are cream, on a dark charcoal
background with rounded corners.

Run from the repo root:  python assets/icon_gen.py
Produces:                assets/icon.ico  (Windows ICO with 16/32/48/64)
"""
import os
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INK    = (26, 24, 22)
CREAM  = (246, 243, 238)
AMBER  = (242, 168, 50)


def render_brand(size: int):
    """Return a flat list of (b, g, r, a) tuples, top-down rows."""
    pixels = [(0, 0, 0, 0)] * (size * size)
    radius = max(2, size // 8)

    def in_rounded_rect(x, y, w, h, r):
        if x < r and y < r and (r - x) ** 2 + (r - y) ** 2 > r * r: return False
        if x >= w - r and y < r and (x - (w - r - 1)) ** 2 + (r - y) ** 2 > r * r: return False
        if x < r and y >= h - r and (r - x) ** 2 + (y - (h - r - 1)) ** 2 > r * r: return False
        if x >= w - r and y >= h - r and (x - (w - r - 1)) ** 2 + (y - (h - r - 1)) ** 2 > r * r: return False
        return True

    pad   = max(2, size // 6)
    cell  = (size - pad * 3) // 2
    cells = [
        (pad,                    pad,                    AMBER),
        (pad * 2 + cell,         pad,                    CREAM),
        (pad,                    pad * 2 + cell,         CREAM),
        (pad * 2 + cell,         pad * 2 + cell,         CREAM),
    ]
    cell_radius = max(1, cell // 5)

    for y in range(size):
        for x in range(size):
            if not in_rounded_rect(x, y, size, size, radius):
                continue
            r, g, b = INK
            for cx, cy, color in cells:
                if cx <= x < cx + cell and cy <= y < cy + cell:
                    lx, ly = x - cx, y - cy
                    if in_rounded_rect(lx, ly, cell, cell, cell_radius):
                        r, g, b = color
                    break
            pixels[y * size + x] = (b, g, r, 255)
    return pixels


def encode_bmp(size: int, pixels) -> bytes:
    """Return a BMP-format image (without file header) with AND mask
    appended — the format ICO files expect for non-PNG images."""
    # BITMAPINFOHEADER. Note: height is doubled to accommodate the
    # AND (transparency) mask that follows the XOR pixel data.
    header = struct.pack(
        "<IIIHHIIIIII",
        40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0,
    )
    xor = bytearray()
    for y in range(size - 1, -1, -1):  # BMP is bottom-up
        for x in range(size):
            b, g, r, a = pixels[y * size + x]
            xor += bytes((b, g, r, a))
    # AND mask: 1 bit per pixel, padded to 4-byte rows. We use the
    # alpha channel from XOR data: 0 alpha → transparent → AND bit 1.
    and_row_bytes = ((size + 31) // 32) * 4
    and_mask = bytearray(and_row_bytes * size)
    for y in range(size - 1, -1, -1):
        for x in range(size):
            _, _, _, a = pixels[y * size + x]
            if a == 0:
                row = (size - 1 - y) * and_row_bytes
                and_mask[row + x // 8] |= (1 << (7 - (x % 8)))
    return bytes(header) + bytes(xor) + bytes(and_mask)


def main():
    sizes = [16, 32, 48, 64]
    images = [(s, encode_bmp(s, render_brand(s))) for s in sizes]

    out = bytearray()
    out += struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for size, data in images:
        w = size if size < 256 else 0
        h = size if size < 256 else 0
        out += struct.pack(
            "<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)
    for _, data in images:
        out += data

    target = ROOT / "icon.ico"
    target.write_bytes(bytes(out))
    print(f"wrote {target}  ({target.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
