"""화면(씬): 시작 메뉴 / 게임 / 엔딩."""
import math

import pygame

from . import save, sound, sprites, fonts
from .config import TICK_DT, SPEEDS, AUTOSAVE_INTERVAL, C_DIM, C_MONEY, C_TEXT, C_BG
from .renderer import Camera, WorldRenderer
from .ui import hud, dialogs
from .ui.info_panel import draw_info_panel
from .ui.ladder import LadderEditor
from .ui.tech_tree import TechTree
from .ui.widgets import dim_screen

HELP_LINES = [
    "[기본 흐름] 광석 채굴 → 제련 → 출하장 판매로 돈을 벌고, 마일스톤을 달성해 다음 시대를 해금",
    "1. 석탄 광맥(검은 점)에 채굴기 → 벨트 → 석탄 발전기를 놓고, 발전기 근처에 전신주를 세우세요",
    "2. 전신주는 주변 5x5 범위 기계에 전력을 공급하고, 7칸 안의 다른 전신주와 자동 연결됩니다",
    "3. 철광석 채굴기 → 벨트 → 제련로 → 벨트 → 출하장(2x2) 으로 철판을 팔아보세요",
    "4. 기계는 앞쪽(흰 화살표)으로 출력하고, 나머지 면으로 재료를 받습니다",
    "5. 부하가 공급보다 크면 차단기가 트립됩니다. 상단 전력 게이지를 눌러 복구하세요",
    "",
    "[조작] 좌클릭: 설치/선택 · 우클릭(드래그): 철거 · R: 회전 · Q: 스포이드 · Esc: 취소/메뉴",
    "WASD/방향키 또는 휠클릭 드래그: 이동 · 휠: 줌 · 1~0: 건물 선택 · Tab: 카테고리",
    "T: 연구 트리 · P: 전력망 · X: 철거 도구 · L: 신호선 · 스페이스: 일시정지 · F5: 빠른 저장 · F1: 도움말",
    "벨트는 드래그하면 이어서 깔리고, 끌고 가는 방향으로 자동 회전합니다",
]


class GameScene:
    def __init__(self, app, game, new=False):
        self.app, self.game = app, game
        self.ui = app.ui
        self.settings = app.settings
        self.cam = Camera(*game.world.center, app.screen.get_size())
        self.renderer = WorldRenderer(game)
        self.tool = None
        self.dir = 0
        self.category = "logistics"
        self.selected = None
        self.speed_i = 1
        self.prev_speed = 1
        self.acc = 0.0
        self.notes = []
        self.popups = []
        self.modal = None
        self.tech = None
        self.ladder = None
        self.link_src = None
        self.show_goals = True
        self.autosave_t = 0.0
        self.drag_tile = None
        self.drag_placed = None
        self.rdrag = False
        self.pan_drag = False
        if new:
            self.open_modal("help")

    # ---------------- 상태 ----------------
    def selected_building(self):
        if self.selected is None:
            return None
        b = self.game.buildings.get(self.selected)
        if b is None:
            self.selected = None
        return b

    def category_buildings(self):
        return [bid for bid, b in self.game.data.buildings.items() if b["category"] == self.category]

    def set_speed(self, i):
        if i == 0 and self.speed_i != 0:
            self.prev_speed = self.speed_i
        self.speed_i = i

    def set_tool(self, tool):
        self.tool = tool
        self.link_src = None
        if tool and tool[0] == "build":
            self.selected = None

    def open_modal(self, name):
        if name == "tech":
            if self.game.era < 2 and not self.game.research.completed:
                self.note("연구는 T2 시대(마일스톤 달성)부터 가능합니다. 그래도 미리 볼 수 있어요", "warn")
            self.tech = TechTree(self)
        elif name == "ladder":
            b = self.selected_building()
            if b is None or b.kind != "plc":
                return
            self.ladder = LadderEditor(self, b)
        self.modal = name

    def close_modal(self):
        if self.modal == "settings":
            save.save_settings(self.settings)
        self.modal = None
        self.ui.eat_all()
        if self.popups:
            self.modal = "popup"

    def note(self, text, color="text", t=5.0):
        self.notes.append({"text": text, "color": color, "t": t})

    def anchor(self, bid, tx, ty):
        s = self.game.data.buildings[bid].get("size", 1)
        return tx - (s - 1) // 2, ty - (s - 1) // 2

    # ---------------- 동작 ----------------
    def try_place(self, tx, ty, quiet=False, d=None):
        bid = self.tool[1]
        x, y = self.anchor(bid, tx, ty)
        b, why = self.game.place(bid, x, y, self.dir if d is None else d)
        if b:
            sound.play("place")
        elif not quiet:
            sound.play("error")
            self.note(why, "bad", 2.5)
        return b

    def remove_building(self, b):
        if b is None:
            return
        if b.kind == "core":
            self.note("메가 프로젝트 코어는 철거할 수 없습니다", "bad", 2.5)
            return
        amt = self.game.remove(b)
        sound.play("remove")
        if self.selected == b.uid:
            self.selected = None
        if amt:
            self.note(f"철거 +${amt:,}", "dim", 1.5)

    def rotate_building(self, b, step=1):
        b.dir = (b.dir + step) % 4
        self.game.world.version += 1
        sound.play("click")

    def link_click(self, b):
        c = self.game.control
        if b is None:
            self.link_src = None
            return
        if self.link_src is None:
            if b.kind in ("sensor", "relay", "plc"):
                self.link_src = b.uid
                self.note("신호를 받을 기계를 클릭하세요 (같은 쌍을 다시 클릭하면 해제)", "accent", 3)
            else:
                sound.play("error")
                self.note("신호선은 센서/릴레이/PLC에서 시작합니다", "bad", 2.5)
            return
        src = self.game.buildings.get(self.link_src)
        if b.uid == self.link_src:
            self.link_src = None
            return
        if any({l["src"], l["dst"]} == {src.uid, b.uid} for l in c.links):
            c.remove_links_between(src.uid, b.uid)
            sound.play("remove")
            self.note("신호선 해제", "dim", 2)
            return
        err = c.add_link(src, b)
        if err:
            sound.play("error")
            self.note(err, "bad", 2.5)
        else:
            sound.play("place")
            port = c.links[-1]["port"]
            self.note(f"연결: {src.name}{f' Y{port}' if src.kind == 'plc' else ''} → {b.name}", "good", 2.5)

    def autosave(self, quiet=False):
        if self.game.slot is None:
            return
        try:
            save.save_game(self.game, self.game.slot)
            if not quiet:
                self.note(f"저장 완료 (슬롯 {self.game.slot})", "good", 2)
        except OSError as e:
            self.note(f"저장 실패: {e}", "bad", 4)

    # ---------------- 입력 ----------------
    def handle_event(self, e):
        if self.modal == "tech" and self.tech and e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
            self.tech.handle_event(e)
            return
        if self.modal == "ladder" and self.ladder and e.type == pygame.MOUSEWHEEL:
            self.ladder.handle_event(e)
            return
        if e.type == pygame.KEYDOWN:
            self.on_key(e)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 2 and not self.modal:
                self.pan_drag = True
        elif e.type == pygame.MOUSEBUTTONUP:
            if e.button == 2:
                self.pan_drag = False
            elif e.button == 1:
                self.drag_tile = None
                self.drag_placed = None
            elif e.button == 3:
                self.rdrag = False
        elif e.type == pygame.MOUSEMOTION and self.pan_drag:
            self.cam.pan_pixels(*e.rel)
        elif e.type == pygame.MOUSEWHEEL and not self.modal and not self.ui.over_ui():
            self.cam.zoom(1 if e.y > 0 else -1, pygame.mouse.get_pos())
        elif e.type == pygame.VIDEORESIZE:
            self.cam.resize(self.app.screen.get_size())

    def on_key(self, e):
        k = e.key
        if k == pygame.K_ESCAPE:
            if self.modal:
                if self.modal == "popup":
                    self.popups.pop(0)
                self.close_modal()
            elif self.tool:
                self.set_tool(None)
            elif self.selected is not None:
                self.selected = None
            else:
                self.open_modal("pause")
            return
        if self.modal:
            if k == pygame.K_t and self.modal == "tech":
                self.close_modal()
            return
        g = self.game
        mods = pygame.key.get_mods()
        if k == pygame.K_r:
            step = -1 if mods & pygame.KMOD_SHIFT else 1
            if self.tool and self.tool[0] == "build":
                self.dir = (self.dir + step) % 4
            else:
                tx, ty = self.cam.tile_at(*self.ui.mouse)
                b = g.world.at(tx, ty) or self.selected_building()
                if b is not None and b.kind != "core":
                    self.rotate_building(b, step)
        elif k == pygame.K_q:
            tx, ty = self.cam.tile_at(*self.ui.mouse)
            b = g.world.at(tx, ty)
            if b is not None and g.building_unlocked(b.type):
                self.set_tool(("build", b.type))
                self.dir = b.dir
                self.category = b.defn["category"]
            else:
                self.set_tool(None)
        elif k == pygame.K_x:
            self.set_tool(None if self.tool == ("remove",) else ("remove",))
        elif k == pygame.K_l:
            if g.building_unlocked("sensor"):
                self.set_tool(None if self.tool == ("link",) else ("link",))
            else:
                self.note("신호선은 '센서·릴레이' 연구 후 사용 가능", "warn", 2.5)
        elif k == pygame.K_t:
            self.open_modal("tech")
        elif k == pygame.K_p:
            self.open_modal("power")
        elif k == pygame.K_F1:
            self.open_modal("help")
        elif k == pygame.K_F5:
            if self.game.slot is None:
                self.open_modal("save")
            else:
                self.autosave()
        elif k == pygame.K_SPACE:
            self.set_speed(self.prev_speed if self.speed_i == 0 else 0)
        elif k == pygame.K_TAB:
            cats = [c["id"] for c in g.data.categories if c["id"] != "special" or g.era >= 6]
            i = cats.index(self.category) if self.category in cats else 0
            self.category = cats[(i + (-1 if mods & pygame.KMOD_SHIFT else 1)) % len(cats)]
        elif pygame.K_1 <= k <= pygame.K_9 or k == pygame.K_0:
            idx = 9 if k == pygame.K_0 else k - pygame.K_1
            bl = self.category_buildings()
            if idx < len(bl):
                if g.building_unlocked(bl[idx]):
                    self.set_tool(("build", bl[idx]))
                else:
                    sound.play("error")
                    self.note(hud.unlock_text(g, g.data.buildings[bl[idx]].get("unlock")), "warn", 2.5)

    # ---------------- 업데이트 ----------------
    def update(self, dt):
        g = self.game
        if not self.modal:
            keys = pygame.key.get_pressed()
            sp = 900 * dt
            dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
            if dx or dy:
                self.cam.pan_pixels(-dx * sp, -dy * sp)
        self.cam.resize(self.app.screen.get_size())
        self.cam.clamp(g.world.w, g.world.h)

        speed = SPEEDS[self.speed_i]
        if self.modal in ("pause", "save", "load", "settings", "help"):
            speed = 0
        if speed:
            self.acc += dt * speed
            g.play_time += dt
            n = 0
            while self.acc >= TICK_DT and n < 4 * 8:
                g.tick(TICK_DT)
                self.acc -= TICK_DT
                n += 1
            if n >= 32:
                self.acc = 0.0

        for ev in g.events:
            if ev["sound"]:
                sound.play(ev["sound"])
            self.note(ev["text"], ev["color"], 7.0 if ev["popup"] else 5.0)
            if ev["popup"]:
                self.popups.append(ev["text"])
                if self.modal is None:
                    self.modal = "popup"
        g.events.clear()

        if self.settings.get("autosave", True) and g.slot is not None:
            self.autosave_t += dt
            if self.autosave_t >= AUTOSAVE_INTERVAL:
                self.autosave_t = 0.0
                self.autosave(quiet=True)
                self.note("자동 저장됨", "dim", 2)

        if g.progress.ending_pending:
            g.progress.ending_pending = False
            self.autosave(quiet=True)
            self.app.scene = EndingScene(self.app, self)

    # ---------------- 그리기 ----------------
    def draw(self, surf, dt):
        ui = self.ui
        ui.modal = False
        self.renderer.draw(surf, self.cam, self)
        held = []
        if self.modal:
            held, ui.clicks = ui.clicks, []
        hud.draw_topbar(self, surf)
        hud.draw_toolbar(self, surf)
        hud.draw_left_panel(self, surf)
        draw_info_panel(self, surf)
        if self.tool and self.tool[0] == "link":
            src = self.game.buildings.get(self.link_src) if self.link_src else None
            msg = f"신호선: {src.name} → 대상 기계 클릭" if src else "신호선: 센서/릴레이/PLC를 클릭"
            fonts.draw(surf, msg + "  (Esc 취소)", (surf.get_width() // 2, surf.get_height() - hud.TOOLBAR_H - 28), 15, (255, 255, 140), True, "center")
        if self.speed_i == 0 and not self.modal:
            fonts.draw(surf, "일시정지", (surf.get_width() // 2, hud.TOP_H + 14), 22, (255, 220, 120), True, "midtop")
        hud.draw_notifications(self, surf, dt)
        if self.modal:
            ui.clicks = held
            ui.modal = True
            self.draw_modal(surf)
            ui.eat_all()
        else:
            self.world_input()
        ui.draw_tooltip(surf)

    def draw_modal(self, surf):
        m = self.modal
        if m == "tech":
            self.tech.draw(surf)
        elif m == "ladder":
            self.ladder.draw(surf)
        elif m == "recipe":
            dialogs.recipe_picker(self, surf)
        elif m == "filter":
            dialogs.filter_picker(self, surf)
        elif m == "pause":
            dialogs.pause_menu(self, surf)
        elif m == "save":
            def do_save(s):
                save.save_game(self.game, s)
                self.note(f"슬롯 {s}에 저장했습니다", "good", 3)
                self.close_modal()
            dialogs.slot_dialog(self, surf, "save", do_save)
        elif m == "load":
            dialogs.slot_dialog(self, surf, "load", self.app.load_slot)
        elif m == "settings":
            dialogs.settings_dialog(self, surf)
        elif m == "power":
            dialogs.power_dialog(self, surf)
        elif m == "popup":
            if self.popups:
                dialogs.popup(self, surf, self.popups[0])
            else:
                self.close_modal()
        elif m == "help":
            rect, closed = dialogs._window(self, surf, 860, 80 + len(HELP_LINES) * 26, "도움말 (F1)")
            y = rect.y + 52
            for ln in HELP_LINES:
                fonts.draw(surf, ln, (rect.x + 20, y), 15, C_TEXT if not ln.startswith("[") else C_MONEY)
                y += 26
            if closed:
                self.close_modal()

    def world_input(self):
        ui, g = self.ui, self.game
        over = ui.over_ui()
        mx, my = ui.mouse
        tx, ty = self.cam.tile_at(mx, my)
        for pos, button in list(ui.clicks):
            if any(r.collidepoint(pos) for r in ui.blockers):
                continue
            ctx, cty = self.cam.tile_at(*pos)
            b = g.world.at(ctx, cty)
            if button == 1:
                if self.tool and self.tool[0] == "build":
                    self.try_place(ctx, cty)
                    self.drag_tile = (ctx, cty)
                    self.drag_placed = g.world.at(ctx, cty)
                elif self.tool == ("remove",):
                    self.remove_building(b)
                    self.rdrag = True
                elif self.tool == ("link",):
                    self.link_click(b)
                else:
                    self.selected = b.uid if b else None
                    if b:
                        sound.play("click")
            elif button == 3:
                if self.tool == ("link",):
                    self.link_src = None
                else:
                    self.remove_building(b)
                    self.rdrag = True
        ui.clicks = []
        pressed = pygame.mouse.get_pressed()
        if over:
            return
        # 벨트 드래그 설치
        if pressed[0] and self.drag_tile and self.tool and self.tool[0] == "build" and (tx, ty) != self.drag_tile:
            defn = g.data.buildings[self.tool[1]]
            if defn["kind"] == "belt":
                cx, cy = self.drag_tile
                while (cx, cy) != (tx, ty):
                    ddx, ddy = tx - cx, ty - cy
                    if abs(ddx) >= abs(ddy):
                        d = 0 if ddx > 0 else 2
                    else:
                        d = 1 if ddy > 0 else 3
                    nx, ny = cx + (1, 0, -1, 0)[d], cy + (0, 1, 0, -1)[d]
                    prev = g.world.at(cx, cy)
                    if prev is not None and prev is self.drag_placed and prev.kind == "belt" and prev.dir != d:
                        prev.dir = d
                        g.world.version += 1
                    self.dir = d
                    self.try_place(nx, ny, quiet=True, d=d)
                    self.drag_placed = g.world.at(nx, ny)
                    cx, cy = nx, ny
                self.drag_tile = (tx, ty)
        if (pressed[2] or (pressed[0] and self.tool == ("remove",))) and self.rdrag:
            b = g.world.at(tx, ty)
            if b is not None and b.kind != "core":
                self.remove_building(b)


# ======================================================================
class MenuScene:
    def __init__(self, app):
        self.app = app
        self.ui = app.ui
        self.modal = None
        self.t = 0.0

    def open_modal(self, m):
        self.modal = m

    def close_modal(self):
        if self.modal == "settings":
            save.save_settings(self.app.settings)
        self.modal = None
        self.ui.eat_all()

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.modal:
                self.close_modal()

    def update(self, dt):
        self.t += dt

    def draw(self, surf, dt):
        ui = self.ui
        W, H = surf.get_size()
        surf.fill(C_BG)
        # 배경: 천천히 도는 톱니들과 흐르는 벨트
        for i in range(7):
            cx = (i * 211 + 80) % W
            cy = (i * 137 + 120) % H
            r = 40 + (i * 23) % 60
            ang = self.t * (0.3 + 0.1 * i) * (1 if i % 2 else -1)
            pts = []
            for k in range(20):
                a = ang + k * math.tau / 20
                rr = r if k % 2 == 0 else r * 0.8
                pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            pygame.draw.polygon(surf, (34, 38, 46), pts)
        by = H - 120
        pygame.draw.rect(surf, (45, 45, 50), (0, by, W, 30))
        items = list(self.app.data.items.values())
        for k in range(W // 60 + 2):
            x = (k * 60 + self.t * 60) % (W + 60) - 30
            idef = items[k % len(items)]
            surf.blit(sprites.item(idef, 22), (x, by + 4))
        icon = sprites.make_icon(96)
        surf.blit(icon, (W // 2 - 48, 70))
        fonts.draw(surf, "공장 자동화 타이쿤", (W // 2, 180), 46, (240, 240, 245), True, "midtop")
        fonts.draw(surf, "원자재 → 부품 → 연구 → 다음 시대", (W // 2, 252), 18, C_DIM, anchor="midtop")
        held = []
        if self.modal:
            held, ui.clicks = ui.clicks, []
        bw = 260
        y = 300
        for label, act in (("새 게임", "new"), ("불러오기", "load"), ("설정", "settings"), ("종료", "quit")):
            if ui.button(surf, (W // 2 - bw // 2, y, bw, 46), label, size=18):
                if act == "quit":
                    self.app.running = False
                else:
                    self.open_modal(act)
            y += 56
        fonts.draw(surf, "F1: 게임 중 도움말", (W // 2, y + 10), 14, C_DIM, anchor="midtop")
        if self.modal:
            ui.clicks = held
            if self.modal == "new":
                dialogs.slot_dialog(self, surf, "new", self.app.new_game)
            elif self.modal == "load":
                dialogs.slot_dialog(self, surf, "load", self.app.load_slot)
            elif self.modal == "settings":
                dialogs.settings_dialog(self, surf)
            ui.eat_all()
        ui.draw_tooltip(surf)


# ======================================================================
class EndingScene:
    def __init__(self, app, game_scene):
        self.app = app
        self.ui = app.ui
        self.gs = game_scene
        self.t = 0.0
        sound.play("fanfare")

    def handle_event(self, e):
        pass

    def update(self, dt):
        self.t += dt

    def draw(self, surf, dt):
        g = self.gs.game
        ui = self.ui
        W, H = surf.get_size()
        self.gs.renderer.draw(surf, self.gs.cam, self.gs)
        dim_screen(surf, 200)
        for i in range(40):
            a = self.t * 0.8 + i * 0.7
            x = W / 2 + math.cos(a * 1.3 + i) * (200 + i * 9)
            y = H / 2 + math.sin(a + i * 2) * (120 + i * 5)
            pygame.draw.circle(surf, [(250, 215, 90), (90, 170, 255), (90, 210, 110)][i % 3], (x, y), 3)
        fonts.draw(surf, "무인 스마트 팩토리 코어 완성!", (W // 2, 90), 40, C_MONEY, True, "midtop")
        fonts.draw(surf, "당신의 공장은 이제 스스로 돌아갑니다.", (W // 2, 150), 18, C_TEXT, anchor="midtop")
        total = sum(g.stats_produced.values())
        lines = [
            f"플레이 시간: {hud.fmt_time(g.play_time)}",
            f"총 수입: ${int(g.total_earned):,}",
            f"총 생산량: {total:,}개",
            f"건물 수: {len(g.buildings):,}",
            f"완료한 연구: {len(g.research.completed)}개",
        ]
        y = 200
        for ln in lines:
            fonts.draw(surf, ln, (W // 2, y), 20, C_TEXT, anchor="midtop")
            y += 32
        top = sorted(g.stats_produced.items(), key=lambda kv: -kv[1])[:8]
        y += 10
        fonts.draw(surf, "생산 TOP 8", (W // 2, y), 16, C_DIM, anchor="midtop")
        y += 26
        for i, (it, n) in enumerate(top):
            x = W // 2 - 300 + (i % 4) * 150
            yy = y + (i // 4) * 34
            surf.blit(sprites.item(g.data.items[it], 24), (x, yy))
            fonts.draw(surf, f"{g.data.item_name(it)} {n:,}", (x + 28, yy + 3), 14)
        y += 80
        if ui.button(surf, (W // 2 - 270, y, 260, 44), "계속 플레이 (무한 연구)", size=16):
            self.app.scene = self.gs
        if ui.button(surf, (W // 2 + 10, y, 260, 44), "메인 메뉴", size=16):
            self.app.goto_menu()
