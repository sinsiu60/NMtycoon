"""연구 트리 화면 (T키). 노드 그래프 + 선행관계 선 + 상태별 색. 드래그로 스크롤."""
import pygame

from .. import sprites, fonts, sound
from ..config import C_BG, C_DIM, C_BORDER

NODE_W, NODE_H = 168, 50
COL_W = 2 * (NODE_W + 16) + 30
ROW_H = 2 * (NODE_H + 12) + 18
ERA_COLS = [2, 3, 4, 5, 7]
STATE_COL = {
    "locked": ((48, 50, 58), (90, 92, 100)),
    "available": ((40, 70, 120), (110, 170, 255)),
    "researching": ((120, 95, 30), (255, 210, 80)),
    "done": ((35, 95, 50), (100, 220, 120)),
}


class TechTree:
    def __init__(self, scene):
        self.scene = scene
        self.scroll = [0, 0]
        self.dragging = False
        self.drag_moved = 0
        self.pending_click = None
        self.layout = self._layout()

    def _layout(self):
        g = self.scene.game
        techs = g.data.techs
        fields = [f["id"] for f in g.data.fields]
        cells = {}
        depth = {}

        def dep(t):
            if t not in depth:
                depth[t] = 1 + max((dep(p) for p in techs[t]["prereqs"] if techs[p]["era"] == techs[t]["era"]), default=0)
            return depth[t]

        for tid, t in techs.items():
            cells.setdefault((t["field"], t["era"]), []).append(tid)
        pos = {}
        for (field, era), ids in cells.items():
            ids.sort(key=lambda i: (dep(i), list(techs).index(i)))
            col = ERA_COLS.index(era) if era in ERA_COLS else len(ERA_COLS) - 1
            row = fields.index(field)
            for k, tid in enumerate(ids):
                sub_x, sub_y = k // 2, k % 2
                x = 150 + col * COL_W + sub_x * (NODE_W + 16)
                y = 70 + row * ROW_H + sub_y * (NODE_H + 12)
                pos[tid] = pygame.Rect(x, y, NODE_W, NODE_H)
        return pos

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 2):
            self.dragging = True
            self.drag_moved = 0
        elif e.type == pygame.MOUSEBUTTONUP and e.button in (1, 2):
            self.dragging = False
            if e.button == 1 and self.drag_moved < 6:
                self.pending_click = e.pos
        elif e.type == pygame.MOUSEMOTION and self.dragging:
            self.scroll[0] += e.rel[0]
            self.scroll[1] += e.rel[1]
            self.drag_moved += abs(e.rel[0]) + abs(e.rel[1])
        elif e.type == pygame.MOUSEWHEEL:
            self.scroll[0] += e.y * 60

    def draw(self, surf):
        scene = self.scene
        g, ui = scene.game, scene.ui
        W, H = surf.get_size()
        surf.fill((20, 22, 27))
        ui.block((0, 0, W, H))
        max_x = 150 + len(ERA_COLS) * COL_W - W + 40
        max_y = 70 + len(g.data.fields) * ROW_H - H + 60
        self.scroll[0] = max(-max(0, max_x), min(0, self.scroll[0]))
        self.scroll[1] = max(-max(0, max_y), min(0, self.scroll[1]))
        sx, sy = self.scroll
        res = g.research
        techs = g.data.techs

        # 시대 헤더 / 분야 배경
        for i, era in enumerate(ERA_COLS):
            x = 150 + i * COL_W + sx
            reached = g.era >= era
            pygame.draw.line(surf, (60, 64, 76), (x - 15, 50), (x - 15, H), 1)
            name = g.data.eras[era]["name"] if era in g.data.eras else f"T{era}"
            fonts.draw(surf, name + ("" if reached else " (잠김)"), (x, 48 + min(0, sy) * 0), 16,
                       (240, 220, 140) if reached else (120, 120, 130), True)
        for r, f in enumerate(g.data.fields):
            y = 70 + r * ROW_H + sy
            if r % 2 == 0:
                band = pygame.Surface((W, ROW_H - 6), pygame.SRCALPHA)
                band.fill((255, 255, 255, 10))
                surf.blit(band, (0, y - 8))
        # 선
        for tid, rect in self.layout.items():
            r = rect.move(sx, sy)
            for p in techs[tid]["prereqs"]:
                pr = self.layout[p].move(sx, sy)
                done = p in res.completed
                col = (100, 220, 120) if done else (90, 92, 104)
                a = (pr.right, pr.centery)
                b = (r.left, r.centery)
                mid = max(a[0] + 8, b[0] - 12)
                pygame.draw.lines(surf, col, False, [a, (mid, a[1]), (mid, b[1]), b], 2)
        # 노드
        hover_tid = None
        for tid, rect in self.layout.items():
            t = techs[tid]
            r = rect.move(sx, sy)
            if r.right < 0 or r.left > W or r.bottom < 0 or r.top > H:
                continue
            st = res.state(tid)
            bg, border = STATE_COL[st]
            pygame.draw.rect(surf, bg, r, border_radius=6)
            pygame.draw.rect(surf, border, r, 2 if st != "locked" else 1, border_radius=6)
            name = t["name"]
            if t.get("repeatable"):
                name += f" Lv.{res.levels.get(tid, 0) + 1}"
            fonts.draw(surf, name, (r.x + 8, r.y + 5), 14, (240, 240, 245) if st != "locked" else (150, 150, 160), True)
            px = r.x + 8
            for p in t["packs"]:
                surf.blit(sprites.item(g.data.items[p], 14), (px, r.y + 27))
                px += 15
            fonts.draw(surf, f"x{res.units_needed(tid)}", (px + 2, r.y + 27), 12, C_DIM)
            frac = res.fraction(tid)
            if 0 < frac < 1 and st != "done":
                ui.bar(surf, (r.x + 6, r.bottom - 7, r.w - 12, 4), frac, (255, 210, 80))
            if r.collidepoint(ui.mouse):
                hover_tid = tid
        # 분야 라벨 (고정)
        pygame.draw.rect(surf, C_BG, (0, 40, 130, H))
        for r, f in enumerate(g.data.fields):
            y = 70 + r * ROW_H + sy + ROW_H // 2 - 20
            fonts.draw(surf, f["name"], (16, y), 18, (220, 225, 235), True)
        # 헤더 바
        pygame.draw.rect(surf, (28, 30, 38), (0, 0, W, 40))
        pygame.draw.line(surf, C_BORDER, (0, 40), (W, 40))
        fonts.draw(surf, "연구 트리", (16, 9), 19, (240, 240, 245), True)
        cur = techs[res.current]["name"] if res.current else "없음"
        fonts.draw(surf, f"현재 연구: {cur}    클릭: 연구 선택 · 드래그/휠: 스크롤 · T/Esc: 닫기", (150, 12), 14, C_DIM)
        legend_x = W - 470
        for st, label in (("locked", "잠김"), ("available", "연구 가능"), ("researching", "연구 중"), ("done", "완료")):
            pygame.draw.rect(surf, STATE_COL[st][0], (legend_x, 12, 16, 16), border_radius=3)
            pygame.draw.rect(surf, STATE_COL[st][1], (legend_x, 12, 16, 16), 1, border_radius=3)
            fonts.draw(surf, label, (legend_x + 20, 12), 13)
            legend_x += 80
        if ui.button(surf, (W - 110, 6, 100, 28), "닫기", size=14):
            scene.close_modal()
            return

        if hover_tid:
            t = techs[hover_tid]
            st = res.state(hover_tid)
            packs = " + ".join(g.data.item_name(p) for p in t["packs"])
            tip = [t["name"], t.get("desc", ""),
                   f"비용: ({packs}) x {res.units_needed(hover_tid)}단위, 단위당 {t['unit_time']}초",
                   f"진행: {res.progress.get(hover_tid, 0)}/{res.units_needed(hover_tid)}"]
            if t["prereqs"]:
                tip.append("선행: " + ", ".join(techs[p]["name"] for p in t["prereqs"]))
            if g.era < t["era"]:
                tip.append(f"필요 시대: {g.data.eras[t['era']]['name']}")
            unlocks = [b["name"] for b in g.data.buildings.values() if b.get("unlock") == f"tech:{hover_tid}"]
            unlocks += [r["name"] + " 레시피" for r in g.data.recipes.values() if r.get("unlock") == f"tech:{hover_tid}"]
            if unlocks:
                tip.append("해금: " + ", ".join(unlocks))
            tip.append({"available": "클릭하여 연구 시작", "researching": "연구 중 (클릭하면 취소)", "done": "완료됨",
                        "locked": "아직 연구할 수 없음"}[st])
            ui.tooltip = "\n".join(tip)
            pc = self.pending_click
            if pc and self.layout[hover_tid].move(sx, sy).collidepoint(pc):
                if st == "available":
                    res.set_current(hover_tid)
                    sound.play("click")
                elif st == "researching":
                    res.set_current(None)
        self.pending_click = None
        ui.eat_all()
