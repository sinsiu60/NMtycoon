"""게임 화면의 상단 바 / 하단 건설 툴바 / 좌측 목표 패널 / 알림."""
import pygame

from .. import sprites, fonts
from ..config import C_PANEL, C_MONEY, C_DIM, C_GOOD, C_BAD, C_WARN, DAY_LENGTH

TOP_H = 40
TOOLBAR_H = 92
LEFT_W = 270
HOTKEYS = "1234567890"


def fmt_time(sec):
    sec = int(max(0, sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def unlock_text(game, unlock):
    if not unlock:
        return ""
    kind, _, val = unlock.partition(":")
    if kind == "era":
        return f"해금: {game.data.eras[int(val)]['name']} 시대"
    return f"해금: 연구 '{game.data.techs[val]['name']}'"


# ----------------------------------------------------------------------
def draw_topbar(scene, surf):
    g, ui = scene.game, scene.ui
    W = surf.get_width()
    ui.panel(surf, (0, 0, W, TOP_H), C_PANEL, alpha=245, radius=0)
    x = 12
    r = ui.text(surf, f"${int(g.money):,}", (x, 9), 20, C_MONEY, bold=True)
    x = r.right + 10
    inc = g.income_rate
    r = ui.text(surf, f"+${inc:,.1f}/초", (x, 13), 14, C_GOOD if inc > 0 else C_DIM)
    x = r.right + 18
    era = g.data.eras[g.era]["name"]
    r = ui.text(surf, era, (x, 12), 15, "accent", bold=True)
    x = r.right + 18
    # 속도
    labels = ["||", "1x", "2x", "4x"]
    for i, lb in enumerate(labels):
        if ui.button(surf, (x, 7, 34, 26), lb, selected=scene.speed_i == i, tooltip="게임 속도 (스페이스: 일시정지)", size=14):
            scene.set_speed(i)
        x += 37
    x += 10
    # 연구
    res = g.research
    rw = 230
    rect = pygame.Rect(x, 6, rw, 28)
    if res.current:
        t = g.data.techs[res.current]
        name = t["name"] + (f" Lv.{res.levels.get(res.current, 0) + 1}" if t.get("repeatable") else "")
        ui.bar(surf, (x, 26, rw, 6), res.fraction(res.current), (90, 170, 255))
        ui.text(surf, f"연구: {name}", (x + 4, 6), 14)
    elif g.era >= 2:
        ui.text(surf, "연구 미선택 (T키)", (x + 4, 11), 14, C_WARN)
    else:
        ui.text(surf, "연구: T2 시대에 해금", (x + 4, 11), 14, C_DIM)
    ui.block(rect)
    if ui.click_in(rect):
        scene.open_modal("tech")
    if ui.hover(rect):
        ui.tooltip = "클릭 또는 T키: 연구 트리 열기"
    x += rw + 14
    # 시계
    phase = (g.time % DAY_LENGTH) / DAY_LENGTH
    hh = int(phase * 24 + 6) % 24
    mm = int((phase * 24 * 60) % 60)
    day = g.daylight() > 0.3
    pygame.draw.circle(surf, (255, 210, 60) if day else (200, 210, 255), (x + 8, 20), 7)
    if not day:
        pygame.draw.circle(surf, C_PANEL, (x + 12, 17), 6)
    r = ui.text(surf, f"{hh:02d}:{mm:02d}", (x + 20, 12), 14)
    x = r.right + 16
    # 전력망
    nets = g.power.nets
    shown = sorted(nets, key=lambda n: -len(n.poles))[:3]
    for n in shown:
        bw = 150
        rect = pygame.Rect(x, 6, bw, 28)
        if x + bw > W - 4:
            break
        if n.tripped:
            if ui.button(surf, rect, f"망{n.id} 트립! 복구", color=(150, 40, 40), size=14,
                         tooltip="차단기가 트립되었습니다. 클릭해서 수동 복구\n(부하를 줄이지 않으면 다시 트립됩니다)"):
                g.power.reset(n)
        else:
            cap = n.capacity_kw
            frac = n.demand_kw / cap if cap > 0 else (1 if n.demand_kw > 0 else 0)
            col = C_BAD if frac > 1 else (C_WARN if frac > 0.85 else C_GOOD)
            ui.bar(surf, (x, 26, bw, 6), min(1, frac), col)
            ui.text(surf, f"망{n.id} {n.demand_kw:.0f}/{cap:.0f}kW", (x + 2, 6), 13, col if frac > 1 else "text")
            ui.block(rect)
            if ui.hover(rect):
                ui.tooltip = f"전력망 {n.id}: 부하 {n.demand_kw:.0f} kW / 최대 공급 {cap:.0f} kW\n발전기 {len(n.producers)}, 소비 기계 {len(n.consumers)}, 배터리 {len(n.batteries)}"
            if ui.click_in(rect):
                scene.open_modal("power")
        x += bw + 6
    if len(nets) > len(shown) and x < W - 60:
        ui.text(surf, f"+{len(nets) - len(shown)}망", (x, 12), 13, C_DIM)


# ----------------------------------------------------------------------
def draw_toolbar(scene, surf):
    g, ui = scene.game, scene.ui
    W, H = surf.get_size()
    y0 = H - TOOLBAR_H
    ui.panel(surf, (0, y0, W, TOOLBAR_H), C_PANEL, alpha=245, radius=0)
    # 카테고리 탭
    x = 10
    for c in g.data.categories:
        if c["id"] == "special" and g.era < 6:
            continue
        if ui.button(surf, (x, y0 + 5, 78, 22), c["name"], selected=scene.category == c["id"], size=13,
                     tooltip="Tab: 다음 카테고리"):
            scene.category = c["id"]
        x += 82
    # 건물 버튼
    x = 10
    by = y0 + 31
    i = 0
    for bid in scene.category_buildings():
        defn = g.data.buildings[bid]
        unlocked = g.building_unlocked(bid)
        rect = pygame.Rect(x, by, 56, 56)
        sel = scene.tool == ("build", bid)
        tip = f"{defn['name']}  ${defn['cost']:,}\n{defn.get('desc', '')}"
        if defn.get("power"):
            tip += f"\n소비전력 {defn['power']} kW"
        tip += f"\n크기 {defn.get('size', 1)}x{defn.get('size', 1)}"
        if not unlocked:
            tip += "\n" + unlock_text(g, defn.get("unlock"))
        if ui.button(surf, rect, "", enabled=unlocked, selected=sel, tooltip=tip):
            scene.set_tool(("build", bid))
        size = defn.get("size", 1)
        icon = sprites.building(defn, 40 // size, 0)
        if not unlocked:
            icon = icon.copy()
            icon.fill((90, 90, 90, 140), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(icon, icon.get_rect(center=rect.center))
        if i < len(HOTKEYS):
            fonts.draw(surf, HOTKEYS[i], (rect.x + 3, rect.y + 1), 12, (200, 200, 200))
        if not unlocked:
            pygame.draw.rect(surf, (200, 200, 200), (rect.centerx - 5, rect.centery - 1, 10, 8))
            pygame.draw.arc(surf, (200, 200, 200), (rect.centerx - 4, rect.centery - 8, 8, 10), 0, 3.14, 2)
        x += 60
        i += 1
    # 우측 도구
    tools = [("철거 (X)", "remove", "remove", True, "건물 철거 도구. 우클릭으로도 철거 가능 (75% 환불)"),
             ("신호선 (L)", "link", "link", g.building_unlocked("sensor"), "센서/릴레이/PLC → 기계로 신호선 연결\n같은 쌍을 다시 연결하면 해제"),
             ("연구 (T)", "tech", None, True, "연구 트리"),
             ("전력 (P)", "power", None, True, "전력망 그래프"),
             ("메뉴 (Esc)", "pause", None, True, "저장 / 불러오기 / 설정")]
    x = W - 10 - len(tools) * 96
    for label, key, tool, en, tip in tools:
        rect = (x, y0 + 31, 92, 56)
        if tool:
            if ui.button(surf, rect, label, enabled=en, selected=scene.tool and scene.tool[0] == tool, tooltip=tip, size=14):
                scene.set_tool((tool,) if scene.tool != (tool,) else None)
        elif ui.button(surf, rect, label, tooltip=tip, size=14):
            scene.open_modal(key)
        x += 96
    ui.text(surf, "R 회전  Q 스포이드  우클릭 철거  WASD/휠클릭 이동  휠 줌", (W - 10 - len(tools) * 96, y0 + 8), 12, C_DIM)


# ----------------------------------------------------------------------
def draw_left_panel(scene, surf):
    g, ui = scene.game, scene.ui
    x, y = 8, TOP_H + 8
    if not scene.show_goals:
        if ui.button(surf, (x, y, 90, 24), "목표 >", size=13):
            scene.show_goals = True
        return
    rows = []
    prog = g.progress
    era = g.data.eras[g.era]
    lines_h = 30
    ms = prog.milestone_progress()
    lines_h += 22 * len(ms) + (22 if ms else 0)
    if g.era == 6:
        lines_h += 22 * (len(prog.core_lines()) + 1)
    lines_h += 26 + max(1, len(prog.orders)) * 40
    rect = ui.panel(surf, (x, y, LEFT_W, lines_h))
    if ui.button(surf, (x + LEFT_W - 26, y + 4, 22, 20), "-", size=13, tooltip="패널 접기"):
        scene.show_goals = False
    cy = y + 6
    ui.text(surf, f"목표 · {era['name']}", (x + 10, cy), 15, "gold", bold=True)
    cy += 24
    if ms:
        ui.text(surf, "마일스톤 (누적 생산)", (x + 10, cy), 13, C_DIM)
        cy += 20
        for item, have, need in ms:
            idef = g.data.items[item]
            surf.blit(sprites.item(idef, 16), (x + 10, cy + 1))
            ui.text(surf, idef["name"], (x + 30, cy), 13)
            ui.bar(surf, (x + 120, cy + 4, 90, 10), have / need, C_GOOD if have >= need else (90, 170, 255))
            ui.text(surf, f"{have}/{need}", (x + 216, cy), 12, C_DIM)
            cy += 22
    if g.era == 6:
        ui.text(surf, "메가 프로젝트" + ("" if g.core_uid else " (코어 미건설: 특수 탭)"), (x + 10, cy), 13, C_WARN)
        cy += 22
        for ln in prog.core_lines():
            ui.text(surf, ln, (x + 10, cy), 13)
            cy += 22
    ui.text(surf, "주문 의뢰 (출하장에 납품)", (x + 10, cy), 13, C_DIM)
    cy += 22
    if not prog.orders:
        ui.text(surf, f"새 주문 대기 중... {int(prog.order_timer)}초", (x + 10, cy), 13, C_DIM)
    for o in prog.orders:
        idef = g.data.items[o["item"]]
        surf.blit(sprites.item(idef, 18), (x + 10, cy + 2))
        ui.text(surf, f"{idef['name']} {o['done']}/{o['qty']}", (x + 32, cy), 13)
        ui.text(surf, f"${o['reward']:,}", (x + LEFT_W - 10, cy), 13, C_MONEY, anchor="topright")
        frac_t = o["time_left"] / o.get("time_total", 600)
        ui.bar(surf, (x + 32, cy + 20, LEFT_W - 100, 8), o["done"] / o["qty"], (90, 170, 255))
        ui.text(surf, fmt_time(o["time_left"]), (x + LEFT_W - 10, cy + 16), 12, C_BAD if frac_t < 0.2 else C_DIM, anchor="topright")
        cy += 40


# ----------------------------------------------------------------------
def draw_notifications(scene, surf, dt):
    W = surf.get_width()
    y = TOP_H + 8
    keep = []
    for n in scene.notes:
        n["t"] -= dt
        if n["t"] <= 0:
            continue
        keep.append(n)
    scene.notes = keep[-6:]
    from .widgets import COLORS
    for n in scene.notes:
        col = COLORS.get(n["color"], (230, 230, 230))
        alpha = int(255 * min(1.0, n["t"]))
        s = fonts.render(n["text"], 15, col)
        bg = pygame.Surface((s.get_width() + 20, 26), pygame.SRCALPHA)
        bg.fill((15, 17, 22, min(220, alpha)))
        bg.blit(s, (10, 4))
        bg.set_alpha(alpha)
        surf.blit(bg, (W // 2 - bg.get_width() // 2 + 60, y))
        y += 30
