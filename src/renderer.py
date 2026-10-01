"""맵 렌더링 (화면에 보이는 타일만 그린다)."""
import math

import pygame

from . import sprites, fonts
from .buildings import PROBLEM_STATUS, out_tile_for
from .config import ZOOM_LEVELS, DEFAULT_ZOOM, C_GROUND, C_GROUND2, C_GRID, DX, DY


class Camera:
    def __init__(self, cx, cy, screen_size):
        self.zoom_i = DEFAULT_ZOOM
        self.sw, self.sh = screen_size
        self.x = cx - self.sw / 2 / self.tp
        self.y = cy - self.sh / 2 / self.tp

    @property
    def tp(self):
        return ZOOM_LEVELS[self.zoom_i]

    def resize(self, size):
        self.sw, self.sh = size

    def to_screen(self, tx, ty):
        return (tx - self.x) * self.tp, (ty - self.y) * self.tp

    def to_tile(self, sx, sy):
        return self.x + sx / self.tp, self.y + sy / self.tp

    def tile_at(self, sx, sy):
        fx, fy = self.to_tile(sx, sy)
        return math.floor(fx), math.floor(fy)

    def zoom(self, step, anchor):
        fx, fy = self.to_tile(*anchor)
        self.zoom_i = max(0, min(len(ZOOM_LEVELS) - 1, self.zoom_i + step))
        self.x = fx - anchor[0] / self.tp
        self.y = fy - anchor[1] / self.tp

    def pan_pixels(self, dx, dy):
        self.x -= dx / self.tp
        self.y -= dy / self.tp

    def clamp(self, w, h):
        self.x = max(-10, min(w + 10 - self.sw / self.tp, self.x))
        self.y = max(-10, min(h + 10 - self.sh / self.tp, self.y))


class WorldRenderer:
    def __init__(self, game):
        self.game = game
        self.anim = 0.0

    def draw(self, surf, cam, scene):
        g = self.game
        w = g.world
        tp = cam.tp
        sw, sh = surf.get_size()
        surf.fill((18, 20, 22))
        x0 = max(0, math.floor(cam.x))
        y0 = max(0, math.floor(cam.y))
        x1 = min(w.w - 1, math.floor(cam.x + sw / tp))
        y1 = min(w.h - 1, math.floor(cam.y + sh / tp))
        ox, oy = cam.to_screen(0, 0)

        # 바닥 + 광맥
        ground = pygame.Rect(ox + x0 * tp, oy + y0 * tp, (x1 - x0 + 1) * tp, (y1 - y0 + 1) * tp)
        surf.fill(C_GROUND, ground)
        ore = w.ore
        for ty in range(y0, y1 + 1):
            row = ore[ty]
            sy = oy + ty * tp
            for tx in range(x0, x1 + 1):
                o = row[tx]
                if o is not None:
                    surf.blit(sprites.ore_tile(o, tp, (tx * 31 + ty * 17) % 4), (ox + tx * tp, sy))
                elif (tx // 8 + ty // 8) % 2 == 0:
                    surf.fill(C_GROUND2, (ox + tx * tp, sy, tp, tp))
        if scene.settings.get("show_grid", True) and tp >= 20:
            for tx in range(x0, x1 + 2):
                pygame.draw.line(surf, C_GRID, (ox + tx * tp, ground.top), (ox + tx * tp, ground.bottom))
            for ty in range(y0, y1 + 2):
                pygame.draw.line(surf, C_GRID, (ground.left, oy + ty * tp), (ground.right, oy + ty * tp))

        # 건물 (큰 건물이 화면 밖에서 시작해도 그려지도록 여유 3칸)
        grid = w.grid
        seen = set()
        visible = []
        for ty in range(max(0, y0 - 2), y1 + 1):
            row = grid[ty]
            for tx in range(max(0, x0 - 2), x1 + 1):
                b = row[tx]
                if b is not None and b.uid not in seen:
                    seen.add(b.uid)
                    visible.append(b)
        data_items = g.data.items
        ipx = max(4, int(tp * 0.5))
        half = ipx / 2
        for b in visible:
            sx, sy = ox + b.x * tp, oy + b.y * tp
            surf.blit(sprites.building(b.defn, tp, b.dir), (sx, sy))
            if b.kind == "belt" and b.items:
                dx, dy = DX[b.dir], DY[b.dir]
                cx, cy = sx + tp / 2, sy + tp / 2
                for it, p in b.items:
                    off = (p - 0.5) * tp
                    surf.blit(sprites.item(data_items[it], ipx), (cx + dx * off - half, cy + dy * off - half))
            elif b.kind == "pole" and b.net is not None and b.net.tripped:
                pygame.draw.circle(surf, (255, 60, 50), (sx + tp / 2, sy + tp / 2), tp * 0.45, max(2, tp // 10))

        # 전선
        for a, b2, long_ in g.power.edges:
            if a.uid in seen or b2.uid in seen:
                ax, ay = cam.to_screen(*a.center())
                bx, by = cam.to_screen(*b2.center())
                tripped = a.net is not None and a.net.tripped
                col = (220, 70, 60) if tripped else ((150, 170, 230) if long_ else (200, 170, 110))
                pygame.draw.line(surf, col, (ax, ay - tp * 0.3), (bx, by - tp * 0.3), 2 if long_ else 1)

        # 신호선
        bs = g.buildings
        for l in g.control.links:
            s, d = bs.get(l["src"]), bs.get(l["dst"])
            if s is None or d is None or (s.uid not in seen and d.uid not in seen):
                continue
            on = g.control.source_value(s, l["port"])
            ax, ay = cam.to_screen(*s.center())
            bx, by = cam.to_screen(*d.center())
            _dashed(surf, (90, 255, 120) if on else (130, 130, 150), (ax, ay), (bx, by), max(4, tp // 4))
            if s.kind == "plc" and tp >= 24:
                fonts.draw(surf, f"Y{l['port']}", ((ax + bx) / 2, (ay + by) / 2), 12, (200, 255, 200), anchor="center")

        # 상태 아이콘
        if tp >= 16:
            ipx2 = max(10, int(tp * 0.45))
            for b in visible:
                if b.status in PROBLEM_STATUS and b.kind not in ("belt",):
                    sx, sy = cam.to_screen(b.x + b.w, b.y)
                    surf.blit(sprites.status_icon(b.status, ipx2), (sx - ipx2, sy))

        # 선택 표시
        sel = scene.selected_building()
        if sel is not None:
            r = pygame.Rect(cam.to_screen(sel.x, sel.y), (sel.w * tp, sel.h * tp))
            pygame.draw.rect(surf, (255, 255, 255), r.inflate(4, 4), 2)
            if sel.kind == "pole":
                self._supply_area(surf, cam, sel)

        self._draw_preview(surf, cam, scene)

        # 낮밤
        dl = g.daylight()
        dark = int((1 - dl) * 120)
        if dark > 0:
            ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
            ov.fill((10, 15, 45, dark))
            surf.blit(ov, (0, 0))

    def _supply_area(self, surf, cam, p, color=(120, 200, 255, 40)):
        r = p.supply
        if r <= 0:
            return
        tp = cam.tp
        rect = pygame.Rect(cam.to_screen(p.x - r, p.y - r), ((2 * r + 1) * tp, (2 * r + 1) * tp))
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill(color)
        pygame.draw.rect(s, (color[0], color[1], color[2], 160), s.get_rect(), 1)
        surf.blit(s, rect)

    def _draw_preview(self, surf, cam, scene):
        g = self.game
        tool = scene.tool
        mx, my = scene.ui.mouse
        if scene.ui.over_ui():
            return
        tx, ty = cam.tile_at(mx, my)
        tp = cam.tp
        if tool and tool[0] == "build":
            bid = tool[1]
            defn = g.data.buildings[bid]
            size = defn.get("size", 1)
            bx, by = tx - (size - 1) // 2, ty - (size - 1) // 2
            ok, reason, _ = g.check_place(bid, bx, by, scene.dir)
            ghost = sprites.building(defn, tp, scene.dir).copy()
            if ok:
                ghost.fill((255, 255, 255, 150), special_flags=pygame.BLEND_RGBA_MULT)
            else:
                ghost.fill((255, 70, 70, 150), special_flags=pygame.BLEND_RGBA_MULT)
            sx, sy = cam.to_screen(bx, by)
            surf.blit(ghost, (sx, sy))
            if defn["kind"] == "pole":
                class P:  # 미리보기용 임시 객체
                    pass
                p = P()
                p.x, p.y, p.supply = bx, by, defn.get("supply", 0)
                self._supply_area(surf, cam, p)
                reach = max(defn.get("reach", 0), defn.get("long_reach", 0))
                pygame.draw.circle(surf, (200, 200, 120), (sx + tp / 2, sy + tp / 2), reach * tp, 1)
            if defn["kind"] in ("miner", "crafter", "belt", "splitter", "underground_out"):
                ox, oy = out_tile_for(bx, by, size, scene.dir)
                r = pygame.Rect(cam.to_screen(ox, oy), (tp, tp))
                pygame.draw.rect(surf, (255, 255, 255), r, 1)
            if not ok:
                fonts.draw(surf, reason, (mx + 18, my - 6), 14, (255, 120, 110))
            else:
                fonts.draw(surf, f"${defn['cost']:,}", (mx + 18, my - 6), 14, (250, 220, 120))
        elif tool and tool[0] == "remove":
            b = g.world.at(tx, ty)
            if b is not None:
                r = pygame.Rect(cam.to_screen(b.x, b.y), (b.w * tp, b.h * tp))
                s = pygame.Surface(r.size, pygame.SRCALPHA)
                s.fill((255, 50, 50, 90))
                surf.blit(s, r)
        elif tool and tool[0] == "link":
            src = g.buildings.get(scene.link_src) if scene.link_src else None
            if src is not None:
                a = cam.to_screen(*src.center())
                pygame.draw.line(surf, (255, 255, 120), a, (mx, my), 2)
            b = g.world.at(tx, ty)
            if b is not None:
                r = pygame.Rect(cam.to_screen(b.x, b.y), (b.w * tp, b.h * tp))
                pygame.draw.rect(surf, (255, 255, 120), r, 2)


def _dashed(surf, col, a, b, dash):
    ax, ay = a
    bx, by = b
    d = math.hypot(bx - ax, by - ay)
    if d < 1:
        return
    n = int(d / dash)
    for i in range(0, n, 2):
        t0, t1 = i / n, min(1, (i + 1) / n)
        pygame.draw.line(surf, col, (ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1), 2)
