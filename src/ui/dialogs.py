"""모달 창들: 레시피 선택, 필터 선택, 일시정지 메뉴, 세이브 슬롯, 설정, 전력 그래프, 알림 팝업."""
import time

import pygame

from .. import sprites, fonts, sound, save
from ..config import C_PANEL, C_DIM, C_GOOD, C_BAD, C_WARN, C_MONEY
from .hud import unlock_text, fmt_time
from .widgets import dim_screen


def _window(scene, surf, w, h, title):
    W, H = surf.get_size()
    dim_screen(surf, 160)
    rect = pygame.Rect((W - w) // 2, (H - h) // 2, w, h)
    scene.ui.panel(surf, rect, C_PANEL, alpha=250)
    scene.ui.block((0, 0, W, H))
    fonts.draw(surf, title, (rect.x + 16, rect.y + 12), 19, bold=True)
    closed = scene.ui.button(surf, (rect.right - 86, rect.y + 10, 76, 28), "닫기", size=14)
    return rect, closed


# ----------------------------------------------------------------------
def recipe_picker(scene, surf):
    g, ui = scene.game, scene.ui
    b = scene.selected_building()
    if b is None or b.kind != "crafter":
        scene.close_modal()
        return
    recipes = g.data.recipes_for(b.crafts)
    rect, closed = _window(scene, surf, 640, 90 + len(recipes) * 46, f"레시피 선택 — {b.name}")
    if closed:
        scene.close_modal()
        return
    y = rect.y + 52
    spd = b.speed * (1 + g.craft_bonus)
    for r in recipes:
        unlocked = g.is_unlocked(r.get("unlock"))
        row = pygame.Rect(rect.x + 14, y, rect.w - 28, 42)
        cur = b.recipe is not None and b.recipe["id"] == r["id"]
        if ui.button(surf, row, "", enabled=unlocked, selected=cur,
                     tooltip=None if unlocked else unlock_text(g, r.get("unlock"))):
            b.set_recipe(r["id"])
            scene.close_modal()
            return
        x = row.x + 8
        out_id = next(iter(r["outputs"]))
        surf.blit(sprites.item(g.data.items[out_id], 30), (x, row.y + 6))
        fonts.draw(surf, r["name"], (x + 38, row.y + 4), 15, (240, 240, 245) if unlocked else (120, 120, 130), True)
        fonts.draw(surf, f"{r['time'] / spd:.1f}초", (x + 38, row.y + 23), 12, C_DIM)
        x += 170
        for i, n in r["inputs"].items():
            surf.blit(sprites.item(g.data.items[i], 22), (x, row.y + 10))
            fonts.draw(surf, f"{n}", (x + 24, row.y + 13), 13)
            x += 46
        fonts.draw(surf, "→", (x + 2, row.y + 11), 16, C_DIM)
        x += 26
        for i, n in r["outputs"].items():
            surf.blit(sprites.item(g.data.items[i], 22), (x, row.y + 10))
            fonts.draw(surf, f"{n}", (x + 24, row.y + 13), 13)
            x += 46
        if not unlocked:
            fonts.draw(surf, unlock_text(g, r.get("unlock")), (row.right - 8, row.y + 13), 12, C_WARN, anchor="topright")
        y += 46
    ui.eat_all()


def filter_picker(scene, surf):
    g, ui = scene.game, scene.ui
    b = scene.selected_building()
    if b is None or b.kind != "filter_splitter":
        scene.close_modal()
        return
    items = g.data.item_order
    cols = 9
    rows = (len(items) + cols - 1) // cols + 1
    rect, closed = _window(scene, surf, cols * 62 + 30, 70 + rows * 62, "필터 아이템 선택")
    if closed:
        scene.close_modal()
        return
    x0, y0 = rect.x + 15, rect.y + 52
    for i, iid in enumerate([None] + items):
        r = pygame.Rect(x0 + (i % cols) * 62, y0 + (i // cols) * 62, 56, 56)
        name = g.data.item_name(iid) if iid else "필터 없음"
        if ui.button(surf, r, "" if iid else "없음", selected=b.filter == iid, tooltip=name, size=13):
            b.filter = iid
            scene.close_modal()
            return
        if iid:
            ic = sprites.item(g.data.items[iid], 36)
            surf.blit(ic, ic.get_rect(center=r.center))
    ui.eat_all()


# ----------------------------------------------------------------------
def pause_menu(scene, surf):
    rect, closed = _window(scene, surf, 320, 340, "메뉴")
    if closed:
        scene.close_modal()
        return
    ui = scene.ui
    y = rect.y + 56
    for label, action in (("계속하기", "close"), ("저장하기", "save"), ("불러오기", "load"), ("설정", "settings"),
                          ("메인 메뉴로", "menu"), ("게임 종료", "quit")):
        if ui.button(surf, (rect.x + 30, y, rect.w - 60, 38), label, size=16):
            if action == "close":
                scene.close_modal()
            elif action in ("save", "load", "settings"):
                scene.open_modal(action)
            elif action == "menu":
                scene.autosave(quiet=True)
                scene.app.goto_menu()
            elif action == "quit":
                scene.autosave(quiet=True)
                scene.app.running = False
            return
        y += 44
    ui.eat_all()


def slot_dialog(scene, surf, mode, on_pick, title=None):
    """mode: 'save' | 'load' | 'new'. on_pick(slot)"""
    ui = scene.ui
    rect, closed = _window(scene, surf, 480, 290, title or {"save": "저장할 슬롯", "load": "불러올 슬롯", "new": "새 게임 슬롯 선택"}[mode])
    if closed:
        scene.close_modal()
        return
    y = rect.y + 56
    for s in save.SLOTS:
        info = save.slot_info(s)
        if info is None:
            desc = "비어 있음"
        elif info.get("broken"):
            desc = "손상된 파일"
        else:
            era = scene.app.data.eras.get(info["era"], {}).get("name", "")
            when = time.strftime("%m/%d %H:%M", time.localtime(info["saved_at"]))
            desc = f"{era} · ${int(info['money']):,} · {fmt_time(info['play_time'])} · {when}"
        enabled = mode != "load" or (info is not None and not info.get("broken"))
        label = f"슬롯 {s}: {desc}"
        if mode == "new" and info is not None:
            label += "  (덮어씀)"
        if ui.button(surf, (rect.x + 20, y, rect.w - 40, 56), label, enabled=enabled, size=14):
            on_pick(s)
            return
        y += 64
    fonts.draw(surf, f"저장 위치: {save.save_dir()}", (rect.x + 20, rect.bottom - 26), 11, C_DIM)
    ui.eat_all()


def settings_dialog(scene, surf):
    ui = scene.ui
    st = scene.app.settings
    rect, closed = _window(scene, surf, 420, 250, "설정")
    if closed:
        save.save_settings(st)
        scene.close_modal()
        return
    y = rect.y + 60
    fonts.draw(surf, f"효과음 볼륨: {int(st['volume'] * 100)}%", (rect.x + 24, y + 6), 15)
    if ui.button(surf, (rect.right - 120, y, 40, 30), "-", size=16):
        st["volume"] = max(0.0, round(st["volume"] - 0.1, 1))
        sound.set_volume(st["volume"])
    if ui.button(surf, (rect.right - 70, y, 40, 30), "+", size=16):
        st["volume"] = min(1.0, round(st["volume"] + 0.1, 1))
        sound.set_volume(st["volume"])
    y += 46
    if ui.button(surf, (rect.x + 24, y, rect.w - 48, 34), f"자동 저장 (5분마다): {'켬' if st['autosave'] else '끔'}", size=15):
        st["autosave"] = not st["autosave"]
    y += 44
    if ui.button(surf, (rect.x + 24, y, rect.w - 48, 34), f"격자 표시: {'켬' if st['show_grid'] else '끔'}", size=15):
        st["show_grid"] = not st["show_grid"]
    ui.eat_all()


# ----------------------------------------------------------------------
def power_dialog(scene, surf):
    g, ui = scene.game, scene.ui
    nets = g.power.nets
    rect, closed = _window(scene, surf, 760, min(surf.get_height() - 40, 110 + max(1, len(nets)) * 150), "전력망")
    if closed:
        scene.close_modal()
        return
    meter = "power_meter" in g.flags
    y = rect.y + 50
    if not nets:
        fonts.draw(surf, "전력망이 없습니다. 발전기 옆에 전신주를 세우세요.", (rect.x + 20, y), 15, C_DIM)
    for n in nets:
        if y + 140 > rect.bottom:
            break
        col = C_BAD if n.tripped else (C_WARN if n.demand_kw > n.capacity_kw else C_GOOD)
        state = "트립됨" if n.tripped else ("과부하" if n.demand_kw > n.capacity_kw else "정상")
        fonts.draw(surf, f"망 {n.id}  [{state}]  부하 {n.demand_kw:.0f} kW / 최대 {n.capacity_kw:.0f} kW", (rect.x + 20, y), 15, col, True)
        bat = sum(b.stored for b in n.batteries)
        batcap = sum(b.capacity_kj for b in n.batteries)
        fonts.draw(surf, f"전신주 {len(n.poles)} · 발전 {len(n.producers)} · 기계 {len(n.consumers)}"
                   + (f" · 배터리 {bat / 1000:.1f}/{batcap / 1000:.0f} MJ" if n.batteries else ""), (rect.x + 20, y + 22), 13, C_DIM)
        if n.tripped and ui.button(surf, (rect.right - 130, y, 110, 28), "차단기 복구", size=14):
            g.power.reset(n)
        gr = pygame.Rect(rect.x + 20, y + 44, rect.w - 40, 90)
        pygame.draw.rect(surf, (18, 20, 24), gr)
        if meter and len(n.history) >= 2:
            peak = max(max(h[0], h[1], h[2]) for h in n.history) or 1
            for idx, color in ((2, (110, 110, 130)), (1, (240, 160, 60)), (0, (90, 210, 110))):
                pts = [(gr.x + i * gr.w / 59, gr.bottom - 4 - h[idx] / peak * (gr.h - 10)) for i, h in enumerate(n.history)]
                pygame.draw.lines(surf, color, False, pts, 2)
            fonts.draw(surf, f"{peak:.0f} kW", (gr.x + 4, gr.y + 2), 11, C_DIM)
            fonts.draw(surf, "초록=공급  주황=부하  회색=최대공급 (최근 60초)", (gr.right - 4, gr.y + 2), 11, C_DIM, anchor="topright")
        elif not meter:
            fonts.draw(surf, "그래프는 '전력 계측기' 연구 후 표시됩니다", gr.center, 14, C_DIM, anchor="center")
        y += 150
    ui.eat_all()


def popup(scene, surf, text):
    rect, closed = _window(scene, surf, 560, 200, "알림")
    lines = fonts.wrap(text, 17, rect.w - 40)
    y = rect.y + 56
    for ln in lines:
        fonts.draw(surf, ln, (rect.centerx, y), 17, C_MONEY, True, "midtop")
        y += 26
    if closed or scene.ui.button(surf, (rect.centerx - 60, rect.bottom - 48, 120, 34), "확인", size=15):
        scene.popups.pop(0)
        if not scene.popups:
            scene.close_modal()
    scene.ui.eat_all()
