"""게임 상태와 고정 틱 시뮬레이션. 렌더링과 완전히 분리되어 있어 헤드리스 테스트가 가능하다."""
import math
import random
from collections import deque

from . import buildings as B
from .config import MAP_W, MAP_H, REFUND_RATE, DAY_LENGTH
from .control import ControlSystem
from .power import PowerSystem
from .progression import Progression
from .research import Research
from .world import World


class Game:
    def __init__(self, data, seed=None):
        self.data = data
        self.seed = seed if seed is not None else random.randrange(1, 10 ** 9)
        self.world = World(MAP_W, MAP_H, self.seed)
        self.buildings = {}
        self.next_uid = 1
        self.money = data.progression["start_money"]
        self.era = 1
        self.time = DAY_LENGTH * 0.3     # 아침에서 시작
        self.play_time = 0.0
        self.stats_produced = {}
        self.stats_sold = {}
        self.total_earned = 0
        self.income_hist = deque([0] * 10, maxlen=10)
        self._income_cur = 0
        self._income_acc = 0.0
        self.craft_bonus = self.mining_bonus = self.gen_bonus = 0.0
        self.flags = set()
        self.events = []
        self.ticking = []
        self.signal_nodes = []
        self.research = Research(self)
        self.power = PowerSystem(self)
        self.control = ControlSystem(self)
        self.progress = Progression(self)
        self.core_uid = None
        self.slot = None

    # ================= 해금 =================
    def is_unlocked(self, unlock):
        if not unlock:
            return True
        kind, _, val = unlock.partition(":")
        if kind == "era":
            return self.era >= int(val)
        if kind == "tech":
            return val in self.research.completed
        return False

    def building_unlocked(self, bid):
        return self.is_unlocked(self.data.buildings[bid].get("unlock"))

    # ================= 알림 =================
    def notify(self, text, color="text", sound=None, popup=False):
        self.events.append({"text": text, "color": color, "sound": sound, "popup": popup})

    # ================= 돈/통계 =================
    def add_money(self, amount):
        self.money += amount
        if amount > 0:
            self.total_earned += amount
            self._income_cur += amount

    def sell(self, item):
        v = self.data.items[item]["value"]
        self.add_money(v)
        self.stats_sold[item] = self.stats_sold.get(item, 0) + 1
        self.progress.on_sold(item)

    def on_produced(self, item, n):
        self.stats_produced[item] = self.stats_produced.get(item, 0) + n

    @property
    def income_rate(self):
        return sum(self.income_hist) / len(self.income_hist)

    def daylight(self):
        phase = (self.time % DAY_LENGTH) / DAY_LENGTH
        sun = math.sin(phase * math.tau)
        return max(0.0, min(1.0, sun * 1.6 + 0.35))

    # ================= 건설 =================
    def check_place(self, bid, x, y, d, ignore_money=False):
        """(가능 여부, 사유, 교체 대상 건물)"""
        defn = self.data.buildings[bid]
        s = defn.get("size", 1)
        if not self.building_unlocked(bid):
            return False, "아직 해금되지 않음", None
        replace = None
        for ty in range(y, y + s):
            for tx in range(x, x + s):
                if not self.world.in_bounds(tx, ty):
                    return False, "맵 밖", None
                b = self.world.at(tx, ty)
                if b is not None:
                    fam = defn.get("family")
                    if (fam and b.defn.get("family") == fam and b.w == s and b.x == x and b.y == y
                            and (b.type != bid or b.dir != d)):
                        replace = b
                    else:
                        return False, "다른 건물이 있음", None
        if defn["kind"] == "miner":
            ore = self.world.ore_at(x, y)
            allowed = defn.get("ores", B.SOLID_ORES)
            if ore not in allowed:
                return False, ("원유 지대 위에만 설치 가능" if "crude_oil" in allowed else "광맥 위에만 설치 가능"), None
        if defn["kind"] == "core" and self.core_uid is not None:
            return False, "코어는 하나만 지을 수 있음", None
        cost = defn["cost"]
        if replace is not None:
            cost = 0 if replace.type == bid else max(0, cost - int(replace.defn["cost"] * REFUND_RATE))
        if not ignore_money and self.money < cost:
            return False, f"돈 부족 (${cost:,})", None
        return True, "", replace

    def place(self, bid, x, y, d, free=False):
        ok, reason, replace = self.check_place(bid, x, y, d, ignore_money=free)
        if not ok:
            return None, reason
        defn = self.data.buildings[bid]
        state = None
        if replace is not None:
            if replace.type == bid:          # 같은 건물: 회전만
                replace.dir = d
                self.world.version += 1
                return replace, ""
            state = replace.save_state()
            keep = {"controlled": replace.controlled, "invert": replace.invert, "priority": replace.priority}
            old_uid = replace.uid
            if not free:
                self.money -= max(0, defn["cost"] - int(replace.defn["cost"] * REFUND_RATE))
            self._remove(replace, keep_links=True)
        elif not free:
            self.money -= defn["cost"]
        b = B.create(self, defn, x, y, d)
        if replace is not None:
            b.uid = old_uid
            if state:
                try:
                    b.load_state(state)
                except Exception:
                    pass
            b.invert, b.priority = keep["invert"], keep["priority"]
        else:
            b.uid = self.next_uid
            self.next_uid += 1
        if defn["kind"] == "generator" and replace is None and not free:
            sf = defn.get("starter_fuel", 0)
            if sf:
                f = next(iter(defn["fuels"]))
                b.fuel[f] = sf
        self._add(b)
        return b, ""

    def _add(self, b):
        self.buildings[b.uid] = b
        for tx, ty in b.tiles():
            self.world.grid[ty][tx] = b
        if b.kind == "core":
            self.core_uid = b.uid
        self.world.version += 1
        self.power.mark_dirty()
        self._refresh_lists()

    def _remove(self, b, keep_links=False):
        for tx, ty in b.tiles():
            if self.world.grid[ty][tx] is b:
                self.world.grid[ty][tx] = None
        self.buildings.pop(b.uid, None)
        if not keep_links:
            self.control.remove_links_of(b.uid)
        if b.kind == "core":
            self.core_uid = None
        b.on_removed()
        self.world.version += 1
        self.power.mark_dirty()
        self._refresh_lists()

    def remove(self, b, refund=True):
        if b is None or b.uid not in self.buildings:
            return 0
        amount = int(b.defn["cost"] * REFUND_RATE) if refund else 0
        if b.kind == "core":
            amount = 0          # 메가 프로젝트는 환불 없음 (진행도는 유지)
        self.money += amount
        self._remove(b)
        return amount

    def _refresh_lists(self):
        self.ticking = [b for b in self.buildings.values() if b.ticks]
        self.signal_nodes = [b for b in self.buildings.values() if b.kind in ("sensor", "relay", "plc")]

    # ================= 틱 =================
    def tick(self, dt):
        self.time += dt
        self.power.tick(dt)
        self.control.tick(dt)
        for b in self.ticking:
            b.update(dt)
        self.progress.tick(dt)
        self._income_acc += dt
        if self._income_acc >= 1.0:
            self._income_acc -= 1.0
            self.income_hist.append(self._income_cur)
            self._income_cur = 0
