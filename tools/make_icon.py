"""게임 아이콘을 코드로 생성: assets/icon.png, assets/icon.ico (PyInstaller --icon 용)."""
import io
import os
import struct
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

pygame.display.init()
pygame.display.set_mode((1, 1))
from src import sprites  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(surf):
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "icon.png")
    return buf.getvalue()


def main():
    out = os.path.join(ROOT, "assets")
    os.makedirs(out, exist_ok=True)
    big = sprites.make_icon(256)
    pygame.image.save(big, os.path.join(out, "icon.png"))
    images = [png_bytes(pygame.transform.smoothscale(big, (s, s))) for s in SIZES]
    # ICO 파일: 헤더 + 디렉터리 + PNG 데이터 (Vista 이후 PNG 내장 ICO 지원)
    header = struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    entries = b""
    for s, data in zip(SIZES, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(os.path.join(out, "icon.ico"), "wb") as f:
        f.write(header + entries + b"".join(images))
    print("icon generated:", out)


if __name__ == "__main__":
    main()
