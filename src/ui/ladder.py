"""PLC 래더 다이어그램 편집기."""
import pygame

from .. import fonts, sound
from ..config import C_DIM, C_BORDER, C_PANEL
from ..plc import COLS, MAX_ROWS, Rung, ADDR_COUNT
from .widgets import dim_screen

CW, RH = 96, 50          # 접점 칸 폭, 행 높이
OUT_W = 120
ON = (90, 240, 110)
OFF = (150, 155, 170)
TOOLS = [("NO", "A접점 -| |-"), ("NC", "B접점 -|/|-"), ("COIL", "코일 ( )"), ("TON", "타이머 TON"),
         ("CTU", "카운터 CTU"), ("RST", "리셋 RST"), ("ERASE", "지우기")]
VALID_DEV = {"NO": "XYMTC", "NC": "XYMTC", "COIL": "YM", "TON": "T", "CTU": "C", "RST": "TC"}


class LadderEditor:
    def __init__(self, scene, plc):
        self.scene = scene
        self.plc = plc
        self.tool = "NO"
        self.dev = "X"
        self.idx = 0
        self.preset = 3
        self.sel_rung = 0
        self.scroll = 0

    @property
    def prog(self):
        return self.plc.program

    def set_tool(self, t):
        self.tool = t
        v = VALID_DEV.get(t)
        if v and self.dev not in v:
            self.dev = v[0]
        self.idx = min(self.idx, ADDR_COUNT[self.dev] - 1)

    def handle_event(self, e):
        if e.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - e.y * 40)

    def _element(self):
        el = {"t": self.tool, "a": f"{self.dev}{self.idx}"}
        if self.tool in ("TON", "CTU"):
            el["p"] = self.preset
        return el

    def draw(self, surf):
        scene, ui = self.scene, self.scene.ui
        g = scene.game
        if self.plc.uid not in g.buildings:
            scene.close_modal()
            return
        W, H = surf.get_size()
        dim_screen(surf, 170)
        ww, wh = min(1180, W - 20), min(660, H - 20)
        win = pygame.Rect((W - ww) // 2, (H - wh) // 2, ww, wh)
        ui.panel(surf, win, C_PANEL, alpha=250)
        ui.block((0, 0, W, H))
        fonts.draw(surf, f"PLC 래더 편집기  ({self.plc.x}, {self.plc.y})", (win.x + 16, win.y + 10), 18, bold=True)
        if ui.button(surf, (win.right - 90, win.y + 8, 80, 28), "닫기", size=14):
            scene.close_modal()
            return

        # ---- 팔레트 ----
        px, py = win.x + 16, win.y + 44
        for t, label in TOOLS:
            w = fonts.width(label, 13) + 18
            if ui.button(surf, (px, py, w, 28), label, selected=self.tool == t, size=13):
                self.set_tool(t)
            px += w + 4
        px, py = win.x + 16, win.y + 78
        fonts.draw(surf, "주소:", (px, py + 5), 14, C_DIM)
        px += 44
        valid = VALID_DEV.get(self.tool, "XYMTC")
        for dv in "XYMTC":
            if ui.button(surf, (px, py, 30, 28), dv, enabled=dv in valid, selected=self.dev == dv, size=14):
                self.dev = dv
                self.idx = min(self.idx, ADDR_COUNT[dv] - 1)
            px += 33
        px += 6
        if ui.button(surf, (px, py, 28, 28), "-", size=15):
            self.idx = (self.idx - 1) % ADDR_COUNT[self.dev]
        fonts.draw(surf, f"{self.dev}{self.idx}", (px + 52, py + 14), 16, (255, 240, 160), True, "center")
        px += 76
        if ui.button(surf, (px, py, 28, 28), "+", size=15):
            self.idx = (self.idx + 1) % ADDR_COUNT[self.dev]
        px += 44
        if self.tool in ("TON", "CTU"):
            unit = "초" if self.tool == "TON" else "회"
            fonts.draw(surf, "프리셋:", (px, py + 5), 14, C_DIM)
            px += 56
            if ui.button(surf, (px, py, 28, 28), "-", size=15):
                self.preset = max(1, self.preset - 1)
            fonts.draw(surf, f"{self.preset}{unit}", (px + 46, py + 14), 15, (255, 240, 160), True, "center")
            px += 64
            if ui.button(surf, (px, py, 28, 28), "+", size=15):
                self.preset = min(999, self.preset + 1)
            px += 40
        # 렁 조작
        bx = win.x + 16
        by = win.bottom - 40
        prog = self.prog
        if ui.button(surf, (bx, by, 100, 30), "렁 추가", size=14):
            prog.rungs.insert(self.sel_rung + 1, Rung())
            self.sel_rung += 1
        if ui.button(surf, (bx + 106, by, 100, 30), "렁 삭제", enabled=len(prog.rungs) > 1, size=14):
            prog.rungs.pop(self.sel_rung)
            self.sel_rung = max(0, min(self.sel_rung, len(prog.rungs) - 1))
        rung = prog.rungs[self.sel_rung]
        if ui.button(surf, (bx + 212, by, 110, 30), "병렬 분기 +", enabled=len(rung.rows) < MAX_ROWS, size=14,
                     tooltip="선택한 렁에 OR 분기 행 추가"):
            rung.rows.append([None] * COLS)
        if ui.button(surf, (bx + 328, by, 110, 30), "병렬 분기 -", enabled=len(rung.rows) > 1, size=14):
            rung.rows.pop()
        fonts.draw(surf, "좌클릭: 배치 · 우클릭: 삭제 · 휠: 스크롤 · 행 안은 직렬(AND), 분기 행끼리는 병렬(OR)",
                   (bx + 450, by + 7), 13, C_DIM)

        # ---- 래더 캔버스 ----
        canvas = pygame.Rect(win.x + 16, win.y + 116, ww - 330, wh - 166)
        pygame.draw.rect(surf, (18, 20, 24), canvas, border_radius=4)
        pygame.draw.rect(surf, C_BORDER, canvas, 1, border_radius=4)
        clip = surf.get_clip()
        surf.set_clip(canvas)
        x0 = canvas.x + 44
        out_x = x0 + COLS * CW + 16
        rail_r = out_x + OUT_W + 12
        y = canvas.y + 10 - self.scroll
        total_h = 0
        for ri, r in enumerate(prog.rungs):
            rh = len(r.rows) * RH + 10
            rect = pygame.Rect(canvas.x + 4, y, canvas.w - 8, rh)
            if ri == self.sel_rung:
                pygame.draw.rect(surf, (40, 50, 70), rect, border_radius=4)
            fonts.draw(surf, f"{ri:02d}", (canvas.x + 10, y + RH // 2 - 8), 14, C_DIM)
            self._draw_rung(surf, r, x0, out_x, rail_r, y + 4, ri)
            if rect.collidepoint(ui.mouse) and canvas.collidepoint(ui.mouse):
                for c in list(ui.clicks):
                    if rect.collidepoint(c[0]):
                        self.sel_rung = ri
            y += rh + 6
            total_h += rh + 6
        # 레일
        top = canvas.y + 10 - self.scroll
        pygame.draw.line(surf, ON, (x0, top), (x0, top + total_h - 6), 3)
        pygame.draw.line(surf, OFF, (rail_r, top), (rail_r, top + total_h - 6), 3)
        surf.set_clip(clip)
        self.scroll = min(self.scroll, max(0, total_h - canvas.h + 20))

        # ---- I/O 표 ----
        io = pygame.Rect(canvas.right + 12, canvas.y, win.right - canvas.right - 28, canvas.h)
        pygame.draw.rect(surf, (24, 26, 32), io, border_radius=4)
        pygame.draw.rect(surf, C_BORDER, io, 1, border_radius=4)
        cy = io.y + 8
        fonts.draw(surf, "입력 X (신호선 연결 순서)", (io.x + 8, cy), 14, bold=True)
        cy += 22
        ins = g.control.inputs_of(self.plc.uid)
        for i in range(8):
            if i < len(ins):
                src = g.buildings.get(ins[i]["src"])
                nm = f"{src.name} ({src.x},{src.y})" if src else "?"
            else:
                nm = "-"
            col = ON if prog.X[i] else OFF
            fonts.draw(surf, f"X{i}", (io.x + 8, cy), 13, col, True)
            fonts.draw(surf, nm, (io.x + 36, cy), 13, col if nm != "-" else (90, 90, 100))
            cy += 18
        cy += 8
        fonts.draw(surf, "출력 Y → 연결된 기계", (io.x + 8, cy), 14, bold=True)
        cy += 22
        outs = {l["port"]: l for l in g.control.outputs_of(self.plc.uid)}
        for i in range(8):
            l = outs.get(i)
            dst = g.buildings.get(l["dst"]) if l else None
            nm = f"{dst.name} ({dst.x},{dst.y})" if dst else "-"
            col = ON if prog.Y[i] else OFF
            fonts.draw(surf, f"Y{i}", (io.x + 8, cy), 13, col, True)
            fonts.draw(surf, nm, (io.x + 36, cy), 13, col if dst else (90, 90, 100))
            cy += 18
        cy += 8
        for ln in fonts.wrap("신호선(L키): 센서→PLC는 X입력, PLC→기계는 Y출력이 됩니다. M=내부 릴레이, T=타이머 완료, C=카운터 완료 비트.", 12, io.w - 16):
            fonts.draw(surf, ln, (io.x + 8, cy), 12, C_DIM)
            cy += 16
        ui.eat_all()

    def _draw_rung(self, surf, r, x0, out_x, rail_r, y, ri):
        ui = self.scene.ui
        prog = self.prog
        flows = r.flow or [[False] * COLS for _ in r.rows]
        join_x = out_x - 8
        for k, row in enumerate(r.rows):
            ry = y + k * RH + RH // 2
            f = flows[k] if k < len(flows) else [False] * COLS
            prev = True
            for c in range(COLS):
                cx = x0 + c * CW
                cell = pygame.Rect(cx, ry - RH // 2 + 2, CW, RH - 4)
                el = row[c]
                cur = f[c] if c < len(f) else False
                if el is None:
                    pygame.draw.line(surf, ON if prev and cur else OFF, (cx, ry), (cx + CW, ry), 2)
                else:
                    on = prog.contact(el)
                    pygame.draw.line(surf, ON if prev else OFF, (cx, ry), (cx + 34, ry), 2)
                    pygame.draw.line(surf, ON if cur else OFF, (cx + CW - 34, ry), (cx + CW, ry), 2)
                    col = ON if on else (200, 205, 215)
                    pygame.draw.line(surf, col, (cx + 38, ry - 12), (cx + 38, ry + 12), 3)
                    pygame.draw.line(surf, col, (cx + CW - 38, ry - 12), (cx + CW - 38, ry + 12), 3)
                    if el["t"] == "NC":
                        pygame.draw.line(surf, col, (cx + 36, ry + 12), (cx + CW - 36, ry - 12), 2)
                    fonts.draw(surf, el["a"], (cx + CW // 2, ry - 16), 13, col, True, "midbottom")
                if cell.collidepoint(ui.mouse):
                    pygame.draw.rect(surf, (255, 255, 160), cell, 1, border_radius=3)
                    self._cell_click(cell, ri, k, c)
                prev = cur
            pygame.draw.line(surf, ON if (f[-1] if f else False) else OFF, (x0 + COLS * CW, ry), (join_x, ry), 2)
            if k > 0:
                y_top = y + RH // 2
                pygame.draw.line(surf, ON, (x0, y_top), (x0, ry), 2)
                pygame.draw.line(surf, ON if r.energized else OFF, (join_x, y_top), (join_x, ry), 2)
        # 출력
        oy = y + RH // 2
        cell = pygame.Rect(out_x, oy - RH // 2 + 2, OUT_W, RH - 4)
        en = r.energized
        col = ON if en else (200, 205, 215)
        pygame.draw.line(surf, ON if en else OFF, (join_x, oy), (out_x + 10, oy), 2)
        pygame.draw.line(surf, OFF, (out_x + OUT_W - 10, oy), (rail_r, oy), 2)
        el = r.out
        if el:
            t = el["t"]
            if t in ("COIL", "RST"):
                pygame.draw.arc(surf, col, (out_x + 30, oy - 14, 24, 28), 1.57, 4.71, 3)
                pygame.draw.arc(surf, col, (out_x + OUT_W - 54, oy - 14, 24, 28), -1.57, 1.57, 3)
                pygame.draw.line(surf, col, (out_x + 10, oy), (out_x + 32, oy), 2)
                pygame.draw.line(surf, col, (out_x + OUT_W - 32, oy), (out_x + OUT_W - 10, oy), 2)
                fonts.draw(surf, el["a"], (out_x + OUT_W // 2, oy - 16), 13, col, True, "midbottom")
                if t == "RST":
                    fonts.draw(surf, "R", (out_x + OUT_W // 2, oy), 14, col, True, "center")
            else:
                box = pygame.Rect(out_x + 10, oy - 18, OUT_W - 20, 36)
                pygame.draw.rect(surf, (30, 40, 30) if en else (30, 32, 38), box, border_radius=3)
                pygame.draw.rect(surf, col, box, 2, border_radius=3)
                from ..plc import parse_addr
                _, i = parse_addr(el["a"])
                if t == "TON":
                    extra = f"{prog.T_acc[i]:.1f}/{el.get('p', 1)}s" if i is not None else ""
                else:
                    extra = f"{prog.C_cnt[i]}/{el.get('p', 1)}" if i is not None else ""
                fonts.draw(surf, f"{t} {el['a']}", (box.centerx, box.y + 2), 12, col, True, "midtop")
                fonts.draw(surf, extra, (box.centerx, box.bottom - 2), 12, col, anchor="midbottom")
        else:
            pygame.draw.line(surf, OFF, (out_x + 10, oy), (out_x + OUT_W - 10, oy), 1)
            fonts.draw(surf, "(출력)", (out_x + OUT_W // 2, oy - 4), 12, (90, 90, 100), anchor="midbottom")
        if cell.collidepoint(ui.mouse):
            pygame.draw.rect(surf, (255, 255, 160), cell, 1, border_radius=3)
            self._cell_click(cell, ri, -1, -1)

    def _cell_click(self, cell, ri, row, col):
        ui = self.scene.ui
        r = self.prog.rungs[ri]
        for c in list(ui.clicks):
            if not cell.collidepoint(c[0]):
                continue
            ui.clicks.remove(c)
            self.sel_rung = ri
            erase = c[1] == 3 or self.tool == "ERASE"
            if row < 0:
                if erase:
                    r.out = None
                elif self.tool in ("COIL", "TON", "CTU", "RST"):
                    r.out = self._element()
                    sound.play("click")
                else:
                    sound.play("error")
            else:
                if erase:
                    r.rows[row][col] = None
                elif self.tool in ("NO", "NC"):
                    r.rows[row][col] = self._element()
                    sound.play("click")
                else:
                    sound.play("error")
