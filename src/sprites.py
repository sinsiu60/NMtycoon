"""모든 그래픽 그리기 코드. 에셋 이미지 없이 도형으로 그린다.

나중에 이미지로 교체하려면 assets/buildings/<건물ID>.png, assets/items/<아이템ID>.png 를 넣으면
자동으로 그 이미지를 사용한다 (방향 있는 건물은 '동쪽(→)을 보는' 그림을 넣으면 회전됨).
"""
import math
import os

import pygame

from . import fonts
from .paths import resource_path

_bcache = {}
_icache = {}
_img_cache = {}

ORE_COLORS = {
    "iron_ore": (110, 120, 140),
    "copper_ore": (165, 95, 55),
    "coal": (30, 30, 34),
    "sand": (190, 172, 120),
    "crude_oil": (25, 20, 30),
    "uranium_ore": (80, 160, 60),
}

DIRECTIONAL = {"belt", "underground_in", "underground_out", "splitter", "filter_splitter", "miner", "crafter", "sensor"}


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _image(kind, ident, px):
    key = (kind, ident, px)
    if key in _img_cache:
        return _img_cache[key]
    path = resource_path("assets", kind, f"{ident}.png")
    img = None
    if os.path.exists(path):
        try:
            img = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), (px, px))
        except Exception:
            img = None
    _img_cache[key] = img
    return img


def _arrow(s, cx, cy, d, size, color):
    """d 방향을 가리키는 삼각형."""
    ang = d * math.pi / 2
    pts = []
    for a, r in ((0, size), (2.4, size * 0.8), (-2.4, size * 0.8)):
        pts.append((cx + math.cos(ang + a) * r, cy + math.sin(ang + a) * r))
    pygame.draw.polygon(s, color, pts)


def _rot(surf, d):
    return pygame.transform.rotate(surf, -90 * d) if d else surf


# ======================================================================
# 건물
# ======================================================================
def building(defn, px_tile, d, net_tripped=False):
    """건물 한 채의 Surface (크기 = size*px_tile)."""
    bid = defn["id"]
    size = defn.get("size", 1)
    px = size * px_tile
    key = (bid, px, d)
    s = _bcache.get(key)
    if s is not None:
        return s
    img = _image("buildings", bid, px)
    if img is not None:
        s = _rot(img, d) if defn["kind"] in DIRECTIONAL else img
    else:
        s = _draw_building(defn, px, px_tile, d)
    _bcache[key] = s
    return s


def _draw_building(defn, px, t, d):
    kind = defn["kind"]
    col = tuple(defn.get("color", (120, 120, 120)))
    s = pygame.Surface((px, px), pygame.SRCALPHA)
    m = max(1, px // 16)
    rect = pygame.Rect(m, m, px - 2 * m, px - 2 * m)
    rad = max(2, px // 8)
    dark = _shade(col, 0.55)
    light = _shade(col, 1.3)
    cx, cy = px / 2, px / 2

    if kind == "belt":
        # 동쪽 기준으로 그리고 회전
        b = pygame.Surface((px, px), pygame.SRCALPHA)
        pygame.draw.rect(b, (52, 52, 56), (0, px * 0.12, px, px * 0.76))
        pygame.draw.rect(b, col, (0, px * 0.12, px, px * 0.1))
        pygame.draw.rect(b, col, (0, px * 0.78, px, px * 0.1))
        for k in range(2):
            x0 = px * (0.18 + 0.45 * k)
            pygame.draw.lines(b, (85, 85, 92), False,
                              [(x0, px * 0.32), (x0 + px * 0.18, px * 0.5), (x0, px * 0.68)], max(1, px // 12))
        return _rot(b, d)

    if kind in ("underground_in", "underground_out"):
        b = pygame.Surface((px, px), pygame.SRCALPHA)
        pygame.draw.rect(b, (52, 52, 56), (0, px * 0.12, px, px * 0.76))
        pygame.draw.rect(b, col, (0, px * 0.12, px, px * 0.1))
        pygame.draw.rect(b, col, (0, px * 0.78, px, px * 0.1))
        hole = pygame.Rect(px * 0.45, px * 0.2, px * 0.5, px * 0.6) if kind == "underground_in" else pygame.Rect(px * 0.05, px * 0.2, px * 0.5, px * 0.6)
        pygame.draw.rect(b, (15, 15, 18), hole, border_radius=max(2, px // 6))
        pygame.draw.rect(b, light, hole, max(1, px // 16), border_radius=max(2, px // 6))
        _arrow(b, px * 0.5, px * 0.5, 0, px * 0.18, (220, 220, 220))
        return _rot(b, d)

    if kind in ("splitter", "filter_splitter"):
        pygame.draw.rect(s, dark, rect, border_radius=rad)
        pygame.draw.rect(s, col, rect.inflate(-px // 5, -px // 5), border_radius=rad)
        for k in (3, 0, 1):
            od = (d + k) % 4
            _arrow(s, cx + math.cos(od * math.pi / 2) * px * 0.28, cy + math.sin(od * math.pi / 2) * px * 0.28, od, px * 0.13, (30, 30, 30))
        if kind == "filter_splitter":
            pygame.draw.circle(s, (250, 250, 250), (cx, cy), px * 0.12)
        return s

    pygame.draw.rect(s, dark, rect, border_radius=rad)
    inner = rect.inflate(-max(2, px // 8), -max(2, px // 8))
    pygame.draw.rect(s, col, inner, border_radius=rad)
    lw = max(1, px // 20)

    if kind == "miner":
        pygame.draw.circle(s, dark, (cx, cy), px * 0.3)
        pygame.draw.circle(s, light, (cx, cy), px * 0.3, lw)
        for k in range(3):
            a = k * math.tau / 3
            pygame.draw.line(s, light, (cx, cy), (cx + math.cos(a) * px * 0.26, cy + math.sin(a) * px * 0.26), lw + 1)
        if defn["id"] == "pumpjack":
            pygame.draw.rect(s, (20, 20, 25), (cx - px * 0.1, cy - px * 0.1, px * 0.2, px * 0.2))
    elif kind == "crafter":
        cat = defn.get("crafts")
        if cat == "smelter":
            pygame.draw.rect(s, (40, 25, 20), inner.inflate(-px // 3, -px // 3), border_radius=rad)
            pygame.draw.rect(s, (255, 150, 40), (cx - px * 0.15, cy, px * 0.3, px * 0.16), border_radius=max(1, px // 12))
        elif cat == "assembler":
            _gear(s, (cx, cy), px * 0.28, dark, light)
            tier = defn["id"][-1]
            if tier.isdigit():
                fonts.draw(s, "Mk" + tier, (inner.right - 2, inner.bottom), max(8, px // 7), (240, 240, 240), True, "bottomright")
        elif cat == "refinery":
            for k, h in ((0.3, 0.55), (0.55, 0.7)):
                pygame.draw.rect(s, light, (px * k, px * (0.85 - h), px * 0.16, px * h), border_radius=max(1, px // 16))
        elif cat == "chemical":
            for k, c in ((0.33, (120, 230, 160)), (0.66, (230, 230, 120))):
                pygame.draw.circle(s, c, (px * k, cy + px * 0.08), px * 0.13)
                pygame.draw.rect(s, c, (px * k - px * 0.04, cy - px * 0.2, px * 0.08, px * 0.16))
    elif kind == "lab":
        pygame.draw.circle(s, (235, 240, 255), (cx, cy), px * 0.3)
        for k, c in enumerate(((225, 55, 55), (60, 205, 85), (60, 115, 235), (165, 75, 210))):
            a = k * math.tau / 4 + 0.6
            pygame.draw.circle(s, c, (cx + math.cos(a) * px * 0.17, cy + math.sin(a) * px * 0.17), px * 0.07)
    elif kind == "sink":
        pygame.draw.rect(s, _shade(col, 0.8), inner.inflate(-px // 4, -px // 4), border_radius=rad)
        fonts.draw(s, "$", (cx, cy), int(px * 0.5), (250, 220, 90), True, "center")
    elif kind == "generator":
        bid = defn["id"]
        if bid == "nuclear":
            pygame.draw.circle(s, (200, 200, 205), (cx, cy), px * 0.33)
            pygame.draw.circle(s, (120, 240, 120), (cx, cy), px * 0.18)
            for k in range(3):
                a = k * math.tau / 3 - math.pi / 2
                pygame.draw.polygon(s, (40, 40, 40), [(cx, cy), (cx + math.cos(a - 0.4) * px * 0.15, cy + math.sin(a - 0.4) * px * 0.15),
                                                       (cx + math.cos(a + 0.4) * px * 0.15, cy + math.sin(a + 0.4) * px * 0.15)])
        else:
            pygame.draw.rect(s, dark, (px * 0.15, px * 0.45, px * 0.7, px * 0.4), border_radius=rad)
            pygame.draw.rect(s, (70, 70, 75), (px * 0.62, px * 0.12, px * 0.16, px * 0.4))
            _bolt(s, (px * 0.38, px * 0.62), px * 0.22, (255, 220, 60))
            if bid != "coal_gen":
                pygame.draw.circle(s, light, (px * 0.3, px * 0.28), px * 0.12, lw)
    elif kind == "pole":
        s.fill((0, 0, 0, 0))
        bid = defn["id"]
        if bid == "tower":
            pygame.draw.polygon(s, (170, 170, 185), [(cx, px * 0.08), (px * 0.25, px * 0.92), (px * 0.75, px * 0.92)], lw + 1)
            pygame.draw.line(s, (170, 170, 185), (px * 0.2, px * 0.3), (px * 0.8, px * 0.3), lw + 1)
        elif bid == "transformer":
            pygame.draw.rect(s, col, rect, border_radius=rad)
            for k in (0.33, 0.66):
                pygame.draw.circle(s, (230, 160, 60), (px * k, cy), px * 0.13, lw + 1)
        else:
            pygame.draw.rect(s, (110, 75, 45), (cx - px * 0.07, px * 0.15, px * 0.14, px * 0.75))
            pygame.draw.rect(s, (110, 75, 45), (px * 0.2, px * 0.22, px * 0.6, px * 0.1))
            for k in (0.22, 0.78):
                pygame.draw.circle(s, (200, 200, 210), (px * k, px * 0.2), max(1, px * 0.06))
    elif kind == "solar":
        pygame.draw.rect(s, (25, 35, 80), inner)
        n = 4
        for k in range(1, n):
            pygame.draw.line(s, (120, 140, 200), (inner.x + inner.w * k / n, inner.y), (inner.x + inner.w * k / n, inner.bottom), lw)
            pygame.draw.line(s, (120, 140, 200), (inner.x, inner.y + inner.h * k / n), (inner.right, inner.y + inner.h * k / n), lw)
    elif kind == "battery":
        pygame.draw.rect(s, (30, 40, 40), (px * 0.25, px * 0.22, px * 0.5, px * 0.62), border_radius=max(1, px // 12))
        pygame.draw.rect(s, (200, 200, 200), (px * 0.4, px * 0.14, px * 0.2, px * 0.08))
        _bolt(s, (cx, cy + px * 0.04), px * 0.18, (120, 255, 200))
    elif kind == "sensor":
        b = pygame.Surface((px, px), pygame.SRCALPHA)
        pygame.draw.rect(b, dark, (px * 0.15, px * 0.25, px * 0.45, px * 0.5), border_radius=rad)
        pygame.draw.circle(b, (255, 255, 200), (px * 0.45, cy), px * 0.1)
        pygame.draw.polygon(b, (255, 240, 120, 140), [(px * 0.55, cy), (px * 0.98, px * 0.2), (px * 0.98, px * 0.8)])
        return _rot(b, d)
    elif kind == "relay":
        fonts.draw(s, "R", (cx, cy), int(px * 0.5), (30, 30, 30), True, "center")
    elif kind == "plc":
        pygame.draw.rect(s, (25, 35, 25), inner.inflate(-px // 6, -px // 3))
        for k in range(4):
            pygame.draw.circle(s, (90, 255, 90) if k % 2 == 0 else (60, 90, 60), (px * (0.28 + k * 0.15), px * 0.32), max(1, px * 0.05))
        fonts.draw(s, "PLC", (cx, px * 0.68), max(7, int(px * 0.26)), (220, 240, 220), True, "center")
    elif kind == "core":
        pts = [(cx + math.cos(a) * px * 0.38, cy + math.sin(a) * px * 0.38) for a in [k * math.tau / 6 + math.pi / 6 for k in range(6)]]
        pygame.draw.polygon(s, (60, 50, 30), pts)
        pygame.draw.polygon(s, (255, 230, 120), pts, max(2, px // 30))
        pygame.draw.circle(s, (120, 220, 255), (cx, cy), px * 0.15)

    if kind in ("miner", "crafter"):
        # 출력 방향 표시
        size = defn.get("size", 1)
        from .buildings import out_tile_for
        ox, oy = out_tile_for(0, 0, size, d)
        ax = (ox + 0.5) * t - math.cos(d * math.pi / 2) * t * 0.62
        ay = (oy + 0.5) * t - math.sin(d * math.pi / 2) * t * 0.62
        _arrow(s, ax, ay, d, max(3, t * 0.16), (250, 250, 250))
    return s


def _gear(s, c, r, col, rim):
    cx, cy = c
    pts = []
    for k in range(16):
        a = k * math.tau / 16
        rr = r if k % 2 == 0 else r * 0.75
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, rim, pts, max(1, int(r / 8)))
    pygame.draw.circle(s, rim, c, r * 0.3)


def _bolt(s, c, h, col):
    cx, cy = c
    pts = [(cx + h * 0.15, cy - h), (cx - h * 0.4, cy + h * 0.1), (cx, cy + h * 0.1),
           (cx - h * 0.15, cy + h), (cx + h * 0.4, cy - h * 0.1), (cx, cy - h * 0.1)]
    pygame.draw.polygon(s, col, pts)


# ======================================================================
# 아이템
# ======================================================================
def item(idef, px):
    key = (idef["id"], px)
    s = _icache.get(key)
    if s is not None:
        return s
    s = _image("items", idef["id"], px) or _draw_item(idef, px)
    _icache[key] = s
    return s


def _draw_item(idef, px):
    s = pygame.Surface((px, px), pygame.SRCALPHA)
    col = tuple(idef["color"])
    dark = _shade(col, 0.5)
    light = _shade(col, 1.35)
    sh = idef.get("shape", "ore")
    c = (px / 2, px / 2)
    r = px * 0.42
    lw = max(1, px // 10)
    if sh == "ore":
        pts = [(c[0] + math.cos(a) * r * f, c[1] + math.sin(a) * r * f)
               for a, f in zip([k * math.tau / 7 for k in range(7)], (1, 0.8, 0.95, 0.75, 1, 0.85, 0.9))]
        pygame.draw.polygon(s, col, pts)
        pygame.draw.polygon(s, dark, pts, lw)
    elif sh == "plate":
        rr = pygame.Rect(px * 0.12, px * 0.22, px * 0.76, px * 0.56)
        pygame.draw.rect(s, col, rr, border_radius=max(1, px // 8))
        pygame.draw.rect(s, dark, rr, lw, border_radius=max(1, px // 8))
        pygame.draw.line(s, light, (rr.x + lw * 2, rr.y + lw * 2), (rr.right - lw * 3, rr.y + lw * 2), lw)
    elif sh == "gear":
        _gear(s, c, r, col, dark)
    elif sh == "rod":
        pygame.draw.line(s, dark, (px * 0.2, px * 0.8), (px * 0.8, px * 0.2), max(2, px // 4))
        pygame.draw.line(s, col, (px * 0.2, px * 0.8), (px * 0.8, px * 0.2), max(1, px // 6))
    elif sh == "wire":
        pygame.draw.circle(s, col, c, r, max(2, px // 6))
        pygame.draw.circle(s, dark, c, r * 0.45, max(1, px // 10))
    elif sh == "pack":
        pygame.draw.polygon(s, col, [(px * 0.5, px * 0.1), (px * 0.85, px * 0.88), (px * 0.15, px * 0.88)])
        pygame.draw.polygon(s, dark, [(px * 0.5, px * 0.1), (px * 0.85, px * 0.88), (px * 0.15, px * 0.88)], lw)
        pygame.draw.rect(s, light, (px * 0.4, px * 0.06, px * 0.2, px * 0.15))
    elif sh == "box":
        rr = pygame.Rect(px * 0.14, px * 0.14, px * 0.72, px * 0.72)
        pygame.draw.rect(s, col, rr, border_radius=max(1, px // 6))
        pygame.draw.rect(s, dark, rr, lw, border_radius=max(1, px // 6))
        pygame.draw.circle(s, light, c, px * 0.15)
    elif sh == "chip":
        rr = pygame.Rect(px * 0.2, px * 0.2, px * 0.6, px * 0.6)
        for k in range(3):
            y = px * (0.3 + k * 0.2)
            pygame.draw.line(s, (200, 200, 200), (px * 0.08, y), (px * 0.92, y), max(1, px // 14))
        pygame.draw.rect(s, col, rr)
        pygame.draw.rect(s, light, rr, lw)
    elif sh == "disc":
        pygame.draw.circle(s, col, c, r)
        pygame.draw.circle(s, light, c, r * 0.6, lw)
    elif sh == "barrel":
        rr = pygame.Rect(px * 0.22, px * 0.1, px * 0.56, px * 0.8)
        pygame.draw.rect(s, col, rr, border_radius=max(1, px // 6))
        for y in (0.33, 0.66):
            pygame.draw.line(s, light, (rr.x, px * y), (rr.right, px * y), lw)
    elif sh == "robot":
        pygame.draw.rect(s, dark, (px * 0.15, px * 0.7, px * 0.7, px * 0.2))
        pygame.draw.line(s, col, (px * 0.4, px * 0.72), (px * 0.3, px * 0.35), max(2, px // 6))
        pygame.draw.line(s, col, (px * 0.3, px * 0.35), (px * 0.75, px * 0.2), max(2, px // 6))
        pygame.draw.circle(s, light, (px * 0.3, px * 0.35), px * 0.1)
    else:
        pygame.draw.circle(s, col, c, r)
    return s


# ======================================================================
# 광맥 타일 / 상태 아이콘 / 앱 아이콘
# ======================================================================
def ore_tile(ore, px, variant):
    key = ("ore", ore, px, variant)
    s = _bcache.get(key)
    if s is not None:
        return s
    s = pygame.Surface((px, px), pygame.SRCALPHA)
    col = ORE_COLORS.get(ore, (200, 0, 200))
    if ore == "crude_oil":
        pygame.draw.ellipse(s, col, (px * 0.08, px * 0.2, px * 0.84, px * 0.6))
        pygame.draw.ellipse(s, (70, 50, 90), (px * 0.25, px * 0.32, px * 0.3, px * 0.15))
    else:
        import random
        rng = random.Random(variant * 7919 + sum(map(ord, ore)))
        for _ in range(5):
            x, y = rng.uniform(0.15, 0.85) * px, rng.uniform(0.15, 0.85) * px
            r = rng.uniform(0.08, 0.16) * px
            pygame.draw.circle(s, col, (x, y), r)
            pygame.draw.circle(s, _shade(col, 1.4), (x - r * 0.3, y - r * 0.3), max(1, r * 0.35))
    _bcache[key] = s
    return s


def status_icon(status, px):
    key = ("status", status, px)
    s = _bcache.get(key)
    if s is not None:
        return s
    s = pygame.Surface((px, px), pygame.SRCALPHA)
    c = (px / 2, px / 2)
    bg = {"no_power": (220, 60, 50), "shed": (220, 60, 50), "no_input": (230, 150, 40), "blocked": (200, 80, 200),
          "disabled": (120, 120, 130), "no_recipe": (90, 140, 230), "no_fuel": (230, 150, 40), "no_research": (90, 140, 230)}.get(status, (120, 120, 120))
    pygame.draw.circle(s, (20, 20, 20), c, px / 2)
    pygame.draw.circle(s, bg, c, px / 2 - 1)
    if status in ("no_power", "shed"):
        _bolt(s, c, px * 0.32, (255, 240, 80))
    elif status in ("no_input", "no_fuel"):
        fonts.draw(s, "!", c, int(px * 0.8), (255, 255, 255), True, "center")
    elif status == "blocked":
        pygame.draw.rect(s, (255, 255, 255), (px * 0.3, px * 0.3, px * 0.4, px * 0.4))
    elif status == "disabled":
        pygame.draw.line(s, (255, 255, 255), (px * 0.28, px * 0.72), (px * 0.72, px * 0.28), max(2, px // 7))
    else:
        fonts.draw(s, "?", c, int(px * 0.8), (255, 255, 255), True, "center")
    _bcache[key] = s
    return s


def make_icon(px=64):
    """창/실행파일 아이콘: 톱니 + 번개."""
    s = pygame.Surface((px, px), pygame.SRCALPHA)
    pygame.draw.rect(s, (30, 40, 60), (0, 0, px, px), border_radius=px // 5)
    _gear(s, (px * 0.45, px * 0.55), px * 0.32, (150, 160, 180), (220, 225, 235))
    _bolt(s, (px * 0.7, px * 0.33), px * 0.26, (255, 210, 50))
    return s


def clear_cache():
    _bcache.clear()
    _icache.clear()
