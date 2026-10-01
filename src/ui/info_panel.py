"""건물 클릭 시 오른쪽 정보 패널."""
from .. import sprites, fonts
from ..buildings import STATUS_TEXT, PROBLEM_STATUS
from ..config import C_GOOD, C_BAD, C_WARN, C_DIM
from .hud import TOP_H

PANEL_W = 310


def draw_info_panel(scene, surf):
    b = scene.selected_building()
    if b is None:
        return
    g, ui = scene.game, scene.ui
    W = surf.get_width()
    x, y = W - PANEL_W - 8, TOP_H + 8
    lines = []
    for ln in b.info_lines():
        lines += fonts.wrap(ln, 14, PANEL_W - 24)
    buttons = _buttons(scene, b)
    h = 66 + 20 * 3 + len(lines) * 19 + 12 + ((len(buttons) + 1) // 2) * 32
    rect = ui.panel(surf, (x, y, PANEL_W, h))
    surf.blit(sprites.building(b.defn, 36 // b.w, b.dir), (x + 10, y + 10))
    ui.text(surf, b.name, (x + 54, y + 10), 17, bold=True)
    ui.text(surf, f"({b.x}, {b.y})", (x + 54, y + 32), 12, C_DIM)
    if ui.button(surf, (x + PANEL_W - 30, y + 8, 22, 22), "x", size=14):
        scene.selected = None
        return
    cy = y + 54
    if b.ticks and b.kind not in ("belt", "underground_in", "underground_out", "splitter", "filter_splitter"):
        st = b.status
        col = C_BAD if st in PROBLEM_STATUS else C_GOOD
        ui.text(surf, f"상태: {STATUS_TEXT.get(st, st)}", (x + 12, cy), 14, col)
        cy += 20
    if b.needs_power:
        if b.net is None:
            ui.text(surf, f"소비전력 {b.power_kw} kW · 전력망 연결 안 됨", (x + 12, cy), 14, C_BAD)
        else:
            ui.text(surf, f"소비전력 {b.power_kw} kW · 망{b.net.id} 공급률 {int(b.power_sat * 100)}%", (x + 12, cy), 14)
        cy += 20
    elif b.kind in ("generator", "solar", "battery"):
        ui.text(surf, f"전력망: {'망' + str(b.net.id) if b.net else '연결 안 됨 (전신주 범위 밖)'}", (x + 12, cy), 14,
                "text" if b.net else C_BAD)
        cy += 20
    if b.controlled:
        ui.text(surf, f"신호 제어 중: {'ON (가동)' if b.enabled else 'OFF (정지)'}" + (" · 반전" if b.invert else ""), (x + 12, cy), 14, C_WARN)
        cy += 20
    cy += 4
    for ln in lines:
        ui.text(surf, ln, (x + 12, cy), 14)
        cy += 19
    cy += 8
    bw = (PANEL_W - 30) // 2
    for i, (label, tip, action) in enumerate(buttons):
        bx = x + 10 + (i % 2) * (bw + 10)
        by = cy + (i // 2) * 32
        if ui.button(surf, (bx, by, bw, 28), label, tooltip=tip, size=13):
            action()
            break


def _buttons(scene, b):
    g = scene.game
    out = []

    def add(label, action, tip=None):
        out.append((label, tip, action))

    if b.kind == "crafter":
        add("레시피 선택", lambda: scene.open_modal("recipe"), "이 기계가 만들 레시피 선택 (버퍼의 재료는 사라짐)")
    if b.kind == "pole" and b.net is not None and b.net.tripped:
        add("차단기 복구", lambda: g.power.reset(b.net), "트립된 차단기를 수동으로 재투입")
    if b.kind == "plc":
        add("래더 편집", lambda: scene.open_modal("ladder"), "래더 다이어그램 편집기 열기")
    if b.kind == "relay":
        add("a/b접점 전환", lambda: setattr(b, "nc", not b.nc))
    if b.kind == "filter_splitter":
        add("필터 설정", lambda: scene.open_modal("filter"))
    if b.controlled or b.invert:
        add("신호 반전: " + ("켬" if b.invert else "끔"), lambda: setattr(b, "invert", not b.invert), "켜면 신호 OFF일 때 가동")
    if b.needs_power and ({"priority_shed", "smart_grid"} & g.flags):
        names = ["낮음", "보통", "높음"]
        add(f"우선순위: {names[b.priority]}", lambda: setattr(b, "priority", (b.priority + 1) % 3),
            "과부하 시 '낮음'부터 차단 (스마트 그리드는 보통/높음도 순서대로)")
    n = len(g.control.inputs_of(b.uid)) + len(g.control.outputs_of(b.uid))
    if n:
        add(f"신호선 제거 ({n})", lambda: g.control.remove_links_of(b.uid))
    if b.kind in ("sensor", "relay", "plc"):
        def start_link():
            scene.set_tool(("link",))
            scene.link_src = b.uid
        add("신호선 연결", start_link, "이 건물에서 다른 기계로 신호선 연결 (L키)")
    if b.kind != "core":
        add("회전 (R)", lambda: scene.rotate_building(b))
        add(f"철거 (+${int(b.defn['cost'] * 0.75):,})", lambda: scene.remove_building(b))
    return out
