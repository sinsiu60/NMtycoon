"""한글 폰트 로딩 + 텍스트 렌더 캐시. Windows는 맑은 고딕, 없으면 시스템의 다른 한글 폰트."""
import os
import sys

import pygame

from .paths import resource_path

_CANDIDATE_FILES = [
    resource_path("assets", "font.ttf"),                     # 직접 넣은 폰트가 있으면 최우선
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]
_CANDIDATE_NAMES = ["malgungothic", "맑은고딕", "applesdgothicneo", "nanumgothic", "notosanscjkkr",
                    "notosanskr", "notosanscjk", "gulim", "dotum", "unifont"]

_path = None
_fonts = {}
_cache = {}


def _find():
    global _path
    if _path is not None:
        return _path
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        _CANDIDATE_FILES.insert(1, os.path.join(windir, "Fonts", "malgun.ttf"))
    for f in _CANDIDATE_FILES:
        if os.path.exists(f):
            _path = f
            return _path
    for n in _CANDIDATE_NAMES:
        p = pygame.font.match_font(n)
        if p:
            _path = p
            return _path
    _path = ""
    return _path


def get(size, bold=False):
    key = (size, bold)
    f = _fonts.get(key)
    if f is None:
        p = _find()
        try:
            f = pygame.font.Font(p or None, size)
        except Exception:
            f = pygame.font.Font(None, size)
        if bold:
            f.set_bold(True)
        _fonts[key] = f
    return f


def render(text, size=16, color=(230, 232, 238), bold=False):
    key = (text, size, color, bold)
    s = _cache.get(key)
    if s is None:
        if len(_cache) > 3000:
            _cache.clear()
        s = get(size, bold).render(str(text), True, color)
        _cache[key] = s
    return s


def draw(surf, text, pos, size=16, color=(230, 232, 238), bold=False, anchor="topleft"):
    s = render(text, size, color, bold)
    r = s.get_rect(**{anchor: pos})
    surf.blit(s, r)
    return r


def width(text, size=16, bold=False):
    return render(text, size, (255, 255, 255), bold).get_width()


def wrap(text, size, max_w):
    """한글은 띄어쓰기 없이도 줄바꿈 되도록 글자 단위 폴백."""
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = (cur + " " + word) if cur else word
            if width(cand, size) <= max_w:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            cur = ""
            for ch in word:
                if width(cur + ch, size) > max_w and cur:
                    lines.append(cur)
                    cur = ""
                cur += ch
        lines.append(cur)
    return lines
