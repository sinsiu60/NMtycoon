"""UI 스모크 테스트: 공장을 자동으로 짓고 각 화면을 스크린샷으로 저장.
실행: SDL_VIDEODRIVER=dummy python tests/ui_smoke.py <출력폴더>
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FACTORY_SAVE_DIR", tempfile.mkdtemp())

import pygame
from src.app import App
from src.game import Game
from src.scenes import GameScene
from src.plc import Rung

out = sys.argv[1] if len(sys.argv) > 1 else "screens"
os.makedirs(out, exist_ok=True)

app = App()
g = Game(app.data, seed=7)
for row in g.world.ore:
    for i in range(len(row)):
        if row[i] in ("iron_ore", "copper_ore", "coal"):
            row[i] = None
cx, cy = g.world.center
W = g.world.ore
for dx in range(3):
    W[cy - 6][cx - 10 + dx] = "coal"
    W[cy][cx - 10 + dx] = "iron_ore"
    W[cy + 5][cx - 10 + dx] = "copper_ore"
g.money = 10 ** 6
g.era = 5
g.research.completed.update(t for t, d in app.data.techs.items() if d["era"] <= 4)
g.research.recompute_bonuses()
g.research.set_current("refining")
P = g.place
# 석탄 → 발전기
P("miner_mk1", cx - 10, cy - 6, 0); P("belt_mk1", cx - 9, cy - 6, 0); P("belt_mk1", cx - 8, cy - 6, 0)
P("coal_gen", cx - 7, cy - 7, 0)
P("pole", cx - 5, cy - 5, 0); P("pole", cx - 5, cy + 1, 0); P("pole", cx - 9, cy + 2, 0); P("pole", cx + 1, cy + 1, 0)
# 철광석 → 제련로 → 조립기(톱니) → 출하장
P("miner_mk2", cx - 10, cy, 0)
for i in range(3):
    P("belt_mk2", cx - 9 + i, cy, 0)
P("smelter", cx - 6, cy, 0)
P("belt_mk1", cx - 5, cy, 0); P("belt_mk1", cx - 4, cy, 0)
a, _ = P("assembler_mk1", cx - 3, cy, 0)
a.set_recipe("gear")
P("belt_mk1", cx - 1, cy, 0); P("splitter", cx, cy, 0)
P("belt_mk1", cx + 1, cy, 0); P("belt_mk1", cx, cy - 1, 3); P("belt_mk1", cx, cy + 1, 1)
P("sink", cx + 2, cy, 0)
# 구리
P("miner_mk1", cx - 10, cy + 5, 0)
for i in range(3):
    P("belt_mk1", cx - 9 + i, cy + 5, 0)
P("smelter", cx - 6, cy + 5, 0); P("belt_mk1", cx - 5, cy + 5, 3); P("belt_mk1", cx - 5, cy + 4, 3)
lab, _ = P("lab", cx + 4, cy + 3, 0)
for p in ("red_pack", "green_pack", "blue_pack"):
    for _ in range(5):
        lab.accept(p, 0)
P("pole", cx + 3, cy + 5, 0)
# 제어
sen, _ = P("sensor", cx - 4, cy + 1, 3)
plc, _ = P("plc", cx - 2, cy + 3, 0)
g.control.add_link(sen, plc)
g.control.add_link(plc, a)
r = Rung(); r.rows = [[{"t": "NO", "a": "X0"}, {"t": "NC", "a": "M0"}, None, None, None],
                      [{"t": "NO", "a": "Y0"}, None, None, None, None]]
r.out = {"t": "COIL", "a": "Y0"}
t = Rung(); t.rows = [[{"t": "NO", "a": "Y0"}, None, None, None, None]]; t.out = {"t": "TON", "a": "T0", "p": 5}
plc.program.rungs = [r, t]
P("solar", cx + 6, cy - 6, 0); P("battery", cx + 4, cy - 4, 0); P("pole", cx + 5, cy - 4, 0)
P("miner_mk1", cx + 10, cy + 10, 0)  # 전력 없는 채굴기 (광맥 없음 → 실패)
for _ in range(400):
    g.tick(0.05)

scene = GameScene(app, g)
app.scene = scene
scene.cam.x, scene.cam.y = cx - 20, cy - 11
scene.cam.zoom_i = 5


def frame(name, n=3):
    for _ in range(n):
        app.ui.begin([])
        app.scene.update(1 / 60)
        app.scene.draw(app.screen, 1 / 60)
    pygame.image.save(app.screen, os.path.join(out, name + ".png"))
    print("saved", name)


scene.selected = a.uid
frame("01_factory")
scene.selected = None
scene.tool = ("build", "assembler_mk1")
frame("02_tool")
scene.tool = None
for m in ("tech", "power", "pause", "help"):
    scene.open_modal(m)
    frame("m_" + m)
    scene.close_modal()
scene.selected = a.uid
scene.open_modal("recipe"); frame("m_recipe"); scene.close_modal()
scene.selected = plc.uid
scene.open_modal("ladder"); frame("m_ladder"); scene.close_modal()
g.notify("[마일스톤] 테스트 팝업", "gold", None, popup=True)
frame("m_popup")
print("events ok")
