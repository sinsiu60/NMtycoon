"""헤드리스 시뮬레이션 테스트 (pygame 불필요). 실행: python -m pytest tests  또는  python tests/test_sim.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FACTORY_SAVE_DIR", tempfile.mkdtemp())

from src.data import GameData
from src.game import Game
from src.config import TICK_DT
from src import save

DATA = GameData()


def run(g, seconds):
    for _ in range(int(seconds / TICK_DT)):
        g.tick(TICK_DT)


def blank_game():
    """광맥을 지운 테스트용 맵에 원하는 광석을 직접 깐다."""
    g = Game(DATA, seed=1)
    for row in g.world.ore:
        for i in range(len(row)):
            row[i] = None
    g.money = 10 ** 7
    return g


def build_line(g, ore, x0, y0, length, end_bid):
    """(x0,y0) 채굴기 → 동쪽 벨트 → 끝 건물."""
    g.world.ore[y0][x0] = ore
    assert g.place("miner_mk1", x0, y0, 0)[0]
    for i in range(1, length + 1):
        assert g.place("belt_mk1", x0 + i, y0, 0)[0]
    b, why = g.place(end_bid, x0 + length + 1, y0, 0)
    assert b, why
    return b


def powered_base(g):
    # 석탄 채굴기 → 벨트 → 발전기(2x2) + 전신주
    g.world.ore[10][10] = "coal"
    g.place("miner_mk1", 10, 10, 0)
    g.place("belt_mk1", 11, 10, 0)
    gen, _ = g.place("coal_gen", 12, 10, 0)
    return gen


def test_basic_smelting_and_selling():
    g = blank_game()
    gen = powered_base(g)
    smelter = build_line(g, "iron_ore", 10, 14, 2, "smelter")
    g.place("belt_mk1", 14, 14, 0)
    g.place("sink", 15, 14, 0)
    for y in (12, 16):
        g.place("pole", 12, y, 0)
    g.place("pole", 10, 12, 0)
    money0 = g.money
    run(g, 60)
    assert g.power.nets, "전력망 없음"
    assert smelter.recipe and smelter.recipe["id"] == "smelt_iron"
    assert g.stats_produced.get("iron_plate", 0) > 15, g.stats_produced
    assert g.stats_sold.get("iron_plate", 0) > 10, g.stats_sold
    assert g.money > money0
    assert gen.fuel_count() > 0 or gen.energy > 0


def test_no_power_stops_machines():
    g = blank_game()
    m = build_line(g, "iron_ore", 30, 30, 2, "sink")
    miner = g.world.at(30, 30)
    run(g, 5)
    assert miner.status == "no_power"
    assert g.stats_produced.get("iron_ore", 0) == 0


def test_breaker_trip_and_reset():
    g = blank_game()
    gen, _ = g.place("coal_gen", 40, 40, 0, free=True)
    gen.fuel["coal"] = 20
    g.place("pole", 42, 40, 0)
    # 400kW 발전기에 채굴기 8대(480kW) → 과부하
    for i in range(8):
        g.world.ore[38][40 + i % 4 + (0 if i < 4 else 0)] = "iron_ore"
    xs = [(40, 38), (41, 38), (42, 38), (43, 38), (43, 39), (43, 40), (43, 41), (41, 42)]
    for x, y in xs:
        g.world.ore[y][x] = "iron_ore"
        assert g.place("miner_mk1", x, y, 3)[0]
    run(g, 3)
    net = g.power.nets[0]
    assert net.tripped, (net.demand_kw, net.capacity_kw)
    assert any(e["sound"] == "alarm" for e in g.events)
    g.remove(g.world.at(43, 40)); g.remove(g.world.at(43, 41)); g.remove(g.world.at(41, 42))
    g.power.reset(g.power.nets[0])
    run(g, 3)
    assert not g.power.nets[0].tripped


def test_assembler_research_and_milestone():
    g = blank_game()
    g.era = 2
    a, _ = g.place("assembler_mk1", 50, 50, 0)
    a.set_recipe("gear")
    lab, _ = g.place("lab", 55, 50, 0)
    g.place("pole", 53, 49, 0)
    gen, _ = g.place("coal_gen", 53, 46, 0)
    gen.fuel["coal"] = 20
    for _ in range(4):
        a.accept("iron_plate", 0)
    g.research.set_current("splitter")
    for _ in range(10):
        lab.accept("red_pack", 0)
    run(g, 6)
    assert a.produced >= 1, a.status
    assert g.research.progress.get("splitter", 0) >= 1, lab.status
    g.research.progress["splitter"] = 19
    for _ in range(5):
        lab.accept("red_pack", 0)
    run(g, 6)
    assert "splitter" in g.research.completed
    assert g.building_unlocked("splitter")
    # 마일스톤
    g.stats_produced.update({"gear": 300, "red_pack": 150})
    run(g, 1)
    assert g.era == 3


def test_splitter_alternates():
    g = blank_game()
    g.research.completed.add("splitter")
    sp, _ = g.place("splitter", 60, 60, 0)
    up, _ = g.place("belt_mk1", 60, 59, 3)
    fw, _ = g.place("belt_mk1", 61, 60, 0)
    dn, _ = g.place("belt_mk1", 60, 61, 1)
    for _ in range(3):
        assert sp.accept("iron_plate", 0)
        run(g, 0.1)
    assert (len(up.items), len(fw.items), len(dn.items)) == (1, 1, 1)


def test_plc_ladder():
    from src.plc import LadderProgram, Rung
    p = LadderProgram()
    r = Rung()
    r.rows = [[{"t": "NO", "a": "X0"}, {"t": "NC", "a": "X1"}, None, None, None],
              [{"t": "NO", "a": "Y0"}, {"t": "NC", "a": "X1"}, None, None, None]]   # 자기유지
    r.out = {"t": "COIL", "a": "Y0"}
    t = Rung(); t.rows = [[{"t": "NO", "a": "Y0"}, None, None, None, None]]; t.out = {"t": "TON", "a": "T0", "p": 1}
    c = Rung(); c.rows = [[{"t": "NO", "a": "T0"}, None, None, None, None]]; c.out = {"t": "COIL", "a": "Y1"}
    p.rungs = [r, t, c]
    p.X[0] = True; p.scan(0.05)
    assert p.Y[0]
    p.X[0] = False; p.scan(0.05)
    assert p.Y[0], "자기유지 실패"
    for _ in range(25):
        p.scan(0.05)
    assert p.Y[1], "TON 실패"
    p.X[1] = True; p.scan(0.05)
    assert not p.Y[0]
    d = LadderProgram.from_dict(p.to_dict())
    assert len(d.rungs) == 3


def test_sensor_controls_machine():
    g = blank_game()
    g.research.completed.update({"sensors"})
    belt, _ = g.place("belt_mk1", 70, 70, 0)
    sensor, _ = g.place("sensor", 70, 71, 3)       # 북쪽(벨트)을 감시
    target, _ = g.place("belt_mk1", 72, 72, 0)
    assert g.control.add_link(sensor, target) is None
    run(g, 0.1)
    assert not target.enabled
    belt.items.append(["iron_ore", 0.0])
    g.place("belt_mk1", 71, 70, 2)   # 벨트 끝을 막아 아이템 유지
    run(g, 0.2)
    assert sensor.signal and target.enabled


def test_save_load_roundtrip():
    g = blank_game()
    powered_base(g)
    build_line(g, "copper_ore", 20, 20, 3, "smelter")
    g.place("pole", 12, 12, 0)
    run(g, 10)
    save.save_game(g, 1)
    g2 = save.load_game(DATA, 1)
    assert len(g2.buildings) == len(g.buildings)
    assert g2.money == g.money
    assert save.slot_info(1)["era"] == 1
    run(g2, 5)


def test_megaproject_completion():
    g = blank_game()
    g.era = 6
    core, why = g.place("core", 80, 80, 0)
    assert core, why
    for st in DATA.progression["megaproject"]["stages"]:
        for item, n in st["items"].items():
            for _ in range(n):
                assert core.accept(item, 0)
    assert g.progress.completed and g.era == 7
    assert g.research.can_research("inf_craft")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
