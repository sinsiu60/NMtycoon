"""건물 동작. buildings.json 의 kind 값마다 클래스 하나.

공통 규칙
- dir: 0=동 1=남 2=서 3=북. 출력은 항상 '앞쪽' 타일(out_tile)로.
- accept(item, d): 다른 건물이 이 건물로 아이템을 넣으려 할 때 호출 (d = 아이템 이동 방향).
- demand: 이번 틱에 일하고 싶어서 요청하는 전력(kW). 전력망은 다음 틱에 power_sat(0~1)으로 응답.
"""
from .config import DX, DY, BELT_SPACING
from .world import SOLID_ORES


def opposite(d):
    return (d + 2) % 4


STATUS_TEXT = {
    "ok": "가동 중",
    "idle": "대기",
    "no_power": "전력 없음",
    "no_input": "재료 없음",
    "blocked": "출력 막힘",
    "disabled": "신호 OFF",
    "no_recipe": "레시피 미설정",
    "no_ore": "광맥 없음",
    "no_fuel": "연료 없음",
    "shed": "부하 차단됨",
    "no_research": "연구 미선택",
    "done": "완료",
}

# 정지 원인 아이콘을 띄울 상태
PROBLEM_STATUS = {"no_power", "no_input", "blocked", "disabled", "no_recipe", "no_fuel", "shed", "no_research"}


class Building:
    kind = "base"
    ticks = True            # update() 호출 여부
    controllable = True     # 신호선으로 ON/OFF 가능 여부

    def __init__(self, game, defn, x, y, d):
        self.game = game
        self.defn = defn
        self.type = defn["id"]
        self.x, self.y = x, y
        self.w = self.h = defn.get("size", 1)
        self.dir = d
        self.uid = 0
        self.power_kw = defn.get("power", 0)
        self.demand = 0.0
        self.power_sat = 0.0
        self.net = None
        self.shed = False
        self.enabled = True
        self.controlled = False
        self.invert = False
        self.priority = 1        # 0=낮음 1=보통 2=높음
        self.status = "idle"
        self.produced = 0

    # ---------- 위치 ----------
    def tiles(self):
        return [(self.x + i, self.y + j) for j in range(self.h) for i in range(self.w)]

    def contains(self, tx, ty):
        return self.x <= tx < self.x + self.w and self.y <= ty < self.y + self.h

    def center(self):
        return self.x + self.w / 2.0, self.y + self.h / 2.0

    def out_tile(self):
        return out_tile_for(self.x, self.y, self.w, self.dir)

    @property
    def name(self):
        return self.defn["name"]

    # ---------- 전력/신호 ----------
    @property
    def needs_power(self):
        return self.power_kw > 0

    def power_factor(self):
        return self.power_sat if self.needs_power else 1.0

    def check_run(self):
        """일할 수 있으면 True, 아니면 status를 원인으로 설정."""
        if not self.enabled:
            self.status = "disabled"
            self.demand = 0.0
            return False
        if self.needs_power:
            self.demand = self.power_kw
            if self.shed:
                self.status = "shed"
                return False
            if self.power_sat <= 0:
                self.status = "no_power"
                return False
        return True

    # ---------- 아이템 ----------
    def accept(self, item, d):
        return False

    def push(self, item):
        tx, ty = self.out_tile()
        t = self.game.world.at(tx, ty)
        if t is None or t is self:
            return False
        return t.accept(item, self.dir)

    def holding_items(self):
        return False

    def update(self, dt):
        pass

    def on_removed(self):
        pass

    # ---------- 저장 ----------
    def save_state(self):
        return {}

    def load_state(self, s):
        pass

    def info_lines(self):
        return []


def out_tile_for(x, y, size, d):
    c = (size - 1) // 2
    if d == 0:
        return x + size, y + c
    if d == 1:
        return x + size - 1 - c, y + size
    if d == 2:
        return x - 1, y + size - 1 - c
    return x + c, y - 1


# ======================================================================
class Belt(Building):
    kind = "belt"

    def __init__(self, *a):
        super().__init__(*a)
        self.speed = self.defn.get("speed", 1.5)
        self.items = []          # [item_id, 위치 0~1], 0번이 가장 앞

    def _has_rear_feeder(self):
        bx, by = self.x - DX[self.dir], self.y - DY[self.dir]
        b = self.game.world.at(bx, by)
        return b is not None and b.kind in ("belt", "underground_out", "splitter", "filter_splitter") and b.dir == self.dir

    def accept(self, item, d):
        if d == opposite(self.dir):
            return False
        if d == self.dir or not self._has_rear_feeder():
            entry = 0.0
        else:
            entry = 0.5          # 옆에서 합류
        items = self.items
        for it in items:
            if abs(it[1] - entry) < BELT_SPACING - 1e-6:
                return False
        if len(items) >= 4:
            return False
        i = 0
        while i < len(items) and items[i][1] > entry:
            i += 1
        items.insert(i, [item, entry])
        return True

    def holding_items(self):
        return bool(self.items)

    def update(self, dt):
        items = self.items
        if not items or not self.enabled:
            return
        move = self.speed * dt
        i = 0
        while i < len(items):
            it = items[i]
            np = it[1] + move
            if i == 0:
                if np >= 1.0:
                    if self.push(it[0]):
                        items.pop(0)
                        continue
                    np = 1.0
            else:
                lim = items[i - 1][1] - BELT_SPACING
                if np > lim:
                    np = max(lim, it[1])
            it[1] = np
            i += 1

    def save_state(self):
        return {"items": self.items}

    def load_state(self, s):
        self.items = [list(x) for x in s.get("items", [])]

    def info_lines(self):
        return [f"속도: 초당 {self.speed:g}칸", f"위의 아이템: {len(self.items)}개"]


class UndergroundIn(Building):
    kind = "underground_in"

    def __init__(self, *a):
        super().__init__(*a)
        self.range = self.defn.get("range", 5)
        self.speed = self.defn.get("speed", 3.0)
        self.queue = []          # [item, 남은 시간]
        self._exit = None
        self._exit_ver = -1

    def find_exit(self):
        w = self.game.world
        if self._exit_ver == w.version:
            return self._exit
        self._exit_ver = w.version
        self._exit = None
        for k in range(1, self.range + 1):
            b = w.at(self.x + DX[self.dir] * k, self.y + DY[self.dir] * k)
            if b is None:
                continue
            if b.kind == "underground_out" and b.dir == self.dir:
                self._exit = (b, k)
                break
            if b.kind == "underground_in" and b.dir == self.dir:
                break
        return self._exit

    def accept(self, item, d):
        if d == opposite(self.dir) or len(self.queue) >= 4 or not self.find_exit():
            return False
        if self.queue and self.queue[-1][1] > (self.find_exit()[1] / self.speed) - BELT_SPACING / self.speed:
            return False
        self.queue.append([item, self.find_exit()[1] / self.speed])
        return True

    def holding_items(self):
        return bool(self.queue)

    def update(self, dt):
        if not self.queue or not self.enabled:
            return
        ex = self.find_exit()
        if not ex:
            return
        for q in self.queue:
            q[1] = max(0.0, q[1] - dt)
        if self.queue[0][1] <= 0 and len(ex[0].buffer) < 2:
            ex[0].buffer.append(self.queue.pop(0)[0])

    def save_state(self):
        return {"queue": self.queue}

    def load_state(self, s):
        self.queue = [list(x) for x in s.get("queue", [])]

    def info_lines(self):
        ex = self.find_exit()
        return [f"연결된 출구: {'있음 (' + str(ex[1]) + '칸 앞)' if ex else '없음 — 앞쪽 5칸 안에 같은 방향 출구 필요'}"]


class UndergroundOut(Building):
    kind = "underground_out"

    def __init__(self, *a):
        super().__init__(*a)
        self.buffer = []

    def holding_items(self):
        return bool(self.buffer)

    def update(self, dt):
        if self.buffer and self.enabled and self.push(self.buffer[0]):
            self.buffer.pop(0)

    def save_state(self):
        return {"buffer": self.buffer}

    def load_state(self, s):
        self.buffer = list(s.get("buffer", []))


class Splitter(Building):
    kind = "splitter"

    def __init__(self, *a):
        super().__init__(*a)
        self.buffer = []
        self.rr = 0

    def accept(self, item, d):
        if d == opposite(self.dir) or len(self.buffer) >= 2:
            return False
        self.buffer.append(item)
        return True

    def holding_items(self):
        return bool(self.buffer)

    def _try_dir(self, item, od):
        t = self.game.world.at(self.x + DX[od], self.y + DY[od])
        return t is not None and t.accept(item, od)

    def outputs_for(self, item):
        return [(self.dir + 3) % 4, self.dir, (self.dir + 1) % 4]

    def update(self, dt):
        if not self.buffer or not self.enabled:
            return
        item = self.buffer[0]
        outs = self.outputs_for(item)
        n = len(outs)
        for k in range(n):
            idx = (self.rr + k) % n
            if self._try_dir(item, outs[idx]):
                self.buffer.pop(0)
                self.rr = (idx + 1) % n
                return

    def save_state(self):
        return {"buffer": self.buffer, "rr": self.rr}

    def load_state(self, s):
        self.buffer = list(s.get("buffer", []))
        self.rr = s.get("rr", 0)

    def info_lines(self):
        return ["뒤에서 받아 좌 → 앞 → 우 순서로 분배"]


class FilterSplitter(Splitter):
    kind = "filter_splitter"

    def __init__(self, *a):
        super().__init__(*a)
        self.filter = None

    def outputs_for(self, item):
        if self.filter is None:
            return super().outputs_for(item)
        if item == self.filter:
            return [self.dir]
        return [(self.dir + 3) % 4, (self.dir + 1) % 4]

    def save_state(self):
        s = super().save_state()
        s["filter"] = self.filter
        return s

    def load_state(self, s):
        super().load_state(s)
        self.filter = s.get("filter")

    def info_lines(self):
        f = self.game.data.item_name(self.filter) if self.filter else "없음 (일반 분배)"
        return [f"필터: {f}", "필터 아이템 → 앞, 나머지 → 좌/우"]


class Sink(Building):
    kind = "sink"
    ticks = False
    controllable = False

    def accept(self, item, d):
        self.game.sell(item)
        self.produced += 1
        return True

    def info_lines(self):
        return [f"판매한 아이템: {self.produced}개", "주문 의뢰 품목은 여기서 납품됩니다"]


class Miner(Building):
    kind = "miner"
    OUT_CAP = 5

    def __init__(self, *a):
        super().__init__(*a)
        self.rate = self.defn.get("rate", 0.5)
        ore = self.game.world.ore_at(self.x, self.y)
        allowed = self.defn.get("ores", SOLID_ORES)
        self.ore = ore if ore in allowed else None
        self.progress = 0.0
        self.out = 0

    def holding_items(self):
        return self.out > 0

    def update(self, dt):
        if self.out > 0 and self.push(self.ore):
            self.out -= 1
        self.demand = 0.0
        if self.ore is None:
            self.status = "no_ore"
            return
        if self.out >= self.OUT_CAP:
            self.status = "blocked"
            return
        if not self.check_run():
            return
        self.status = "ok"
        self.progress += dt * self.rate * (1 + self.game.mining_bonus) * self.power_factor()
        if self.progress >= 1.0:
            self.progress -= 1.0
            self.out += 1
            self.produced += 1
            self.game.on_produced(self.ore, 1)

    def save_state(self):
        return {"progress": self.progress, "out": self.out}

    def load_state(self, s):
        self.progress = s.get("progress", 0.0)
        self.out = s.get("out", 0)

    def info_lines(self):
        rate = self.rate * (1 + self.game.mining_bonus)
        ore = self.game.data.item_name(self.ore) if self.ore else "없음"
        return [f"채굴 자원: {ore}", f"채굴 속도: 초당 {rate:.2f}개", f"진행: {int(self.progress * 100)}%  보관: {self.out}"]


class Crafter(Building):
    kind = "crafter"

    def __init__(self, *a):
        super().__init__(*a)
        self.speed = self.defn.get("speed", 1.0)
        self.crafts = self.defn.get("crafts", "assembler")
        self.recipe = None
        self.inbuf = {}
        self.outbuf = {}
        self.progress = 0.0
        self.crafting = False
        # 제련로는 레시피 자동 선택 (첫 재료로 판단)
        self.auto_recipe = self.crafts == "smelter"

    def set_recipe(self, rid):
        if rid == (self.recipe["id"] if self.recipe else None):
            return
        self.recipe = self.game.data.recipes[rid] if rid else None
        self.inbuf = {}
        self.progress = 0.0
        self.crafting = False

    def cap(self, item):
        need = self.recipe["inputs"][item]
        return max(need * 2, need + 2)

    def accept(self, item, d):
        if self.recipe is None and self.auto_recipe:
            for r in self.game.data.recipes_for(self.crafts):
                if item in r["inputs"] and self.game.is_unlocked(r.get("unlock")):
                    # 단일 재료 레시피 우선 (광석 → 판)
                    if len(r["inputs"]) == 1:
                        self.set_recipe(r["id"])
                        break
        r = self.recipe
        if r is None or item not in r["inputs"]:
            return False
        if self.inbuf.get(item, 0) >= self.cap(item):
            return False
        self.inbuf[item] = self.inbuf.get(item, 0) + 1
        return True

    def holding_items(self):
        return any(v > 0 for v in self.outbuf.values())

    def _out_full(self):
        for it, n in self.recipe["outputs"].items():
            if self.outbuf.get(it, 0) + n > max(n * 3, 6):
                return True
        return False

    def update(self, dt):
        # 출력 버퍼 비우기
        for it, n in self.outbuf.items():
            if n > 0 and self.push(it):
                self.outbuf[it] = n - 1
                break
        self.demand = 0.0
        r = self.recipe
        if r is None:
            self.status = "no_recipe"
            return
        if not self.crafting:
            if self._out_full():
                self.status = "blocked"
                return
            for it, n in r["inputs"].items():
                if self.inbuf.get(it, 0) < n:
                    self.status = "no_input"
                    return
            if not self.check_run():
                return
            for it, n in r["inputs"].items():
                self.inbuf[it] -= n
            self.crafting = True
            self.progress = 0.0
        if not self.check_run():
            return
        self.status = "ok"
        self.progress += dt * self.speed * (1 + self.game.craft_bonus) * self.power_factor() / r["time"]
        if self.progress >= 1.0:
            for it, n in r["outputs"].items():
                self.outbuf[it] = self.outbuf.get(it, 0) + n
                self.game.on_produced(it, n)
                self.produced += n
            self.crafting = False
            self.progress = 0.0

    def save_state(self):
        return {"recipe": self.recipe["id"] if self.recipe else None, "inbuf": self.inbuf,
                "outbuf": self.outbuf, "progress": self.progress, "crafting": self.crafting}

    def load_state(self, s):
        rid = s.get("recipe")
        self.recipe = self.game.data.recipes.get(rid) if rid else None
        self.inbuf = dict(s.get("inbuf", {}))
        self.outbuf = dict(s.get("outbuf", {}))
        self.progress = s.get("progress", 0.0)
        self.crafting = s.get("crafting", False)

    def info_lines(self):
        d = self.game.data
        if not self.recipe:
            return ["레시피: 없음", "(제련로는 광석이 들어오면 자동 선택)" if self.auto_recipe else "[레시피 선택] 버튼을 누르세요"]
        r = self.recipe
        spd = self.speed * (1 + self.game.craft_bonus)
        ins = ", ".join(f"{d.item_name(i)} {self.inbuf.get(i, 0)}/{n}" for i, n in r["inputs"].items())
        outs = ", ".join(f"{d.item_name(i)} x{n}" for i, n in r["outputs"].items())
        return [f"레시피: {r['name']} ({r['time'] / spd:.1f}초)", f"재료: {ins}", f"결과: {outs}",
                f"진행: {int(self.progress * 100)}%", f"누적 생산: {self.produced}개"]


class Lab(Building):
    kind = "lab"

    def __init__(self, *a):
        super().__init__(*a)
        self.speed = self.defn.get("speed", 1.0)
        self.buf = {}
        self.unit_tech = None
        self.progress = 0.0

    def accept(self, item, d):
        if not item.endswith("_pack"):
            return False
        if self.buf.get(item, 0) >= 10:
            return False
        self.buf[item] = self.buf.get(item, 0) + 1
        return True

    def update(self, dt):
        self.demand = 0.0
        res = self.game.research
        if self.unit_tech is None:
            tid = res.current
            if tid is None:
                self.status = "no_research"
                return
            packs = self.game.data.techs[tid]["packs"]
            if any(self.buf.get(p, 0) < 1 for p in packs):
                self.status = "no_input"
                return
            if not self.check_run():
                return
            for p in packs:
                self.buf[p] -= 1
            self.unit_tech = tid
            self.progress = 0.0
        if not self.check_run():
            return
        self.status = "ok"
        t = self.game.data.techs[self.unit_tech]
        self.progress += dt * self.speed * self.power_factor() / t["unit_time"]
        if self.progress >= 1.0:
            res.add_unit(self.unit_tech)
            self.unit_tech = None
            self.progress = 0.0

    def save_state(self):
        return {"buf": self.buf, "unit_tech": self.unit_tech, "progress": self.progress}

    def load_state(self, s):
        self.buf = dict(s.get("buf", {}))
        self.unit_tech = s.get("unit_tech")
        if self.unit_tech not in self.game.data.techs:
            self.unit_tech = None
        self.progress = s.get("progress", 0.0)

    def info_lines(self):
        d = self.game.data
        packs = ", ".join(f"{d.item_name(k)} {v}" for k, v in self.buf.items() if v) or "없음"
        cur = d.techs[self.unit_tech]["name"] if self.unit_tech else "-"
        return [f"보유 연구팩: {packs}", f"연구 중: {cur} ({int(self.progress * 100)}%)"]


class Generator(Building):
    kind = "generator"
    FUEL_CAP = 20

    def __init__(self, *a):
        super().__init__(*a)
        self.output = self.defn.get("output", 0)
        self.fuels = self.defn.get("fuels", {})
        self.fuel = {}
        self.energy = 0.0         # 현재 태우는 연료의 남은 에너지 (kJ)
        self.current_kw = 0.0

    def fuel_count(self):
        return sum(self.fuel.values())

    def accept(self, item, d):
        if item not in self.fuels or self.fuel_count() >= self.FUEL_CAP:
            return False
        self.fuel[item] = self.fuel.get(item, 0) + 1
        return True

    def capacity(self):
        if not self.enabled:
            return 0.0
        if self.energy > 0 or self.fuel_count() > 0:
            return self.output * (1 + self.game.gen_bonus)
        return 0.0

    def produce(self, kw, dt):
        self.current_kw = kw
        need = kw * dt
        while need > 1e-9:
            if self.energy <= 0:
                for f, n in self.fuel.items():
                    if n > 0:
                        self.fuel[f] = n - 1
                        self.energy += self.game.data.fuels.get(f, 1000) * self.fuels[f]
                        break
                else:
                    break
            take = min(need, self.energy)
            self.energy -= take
            need -= take

    def update(self, dt):
        if not self.enabled:
            self.status = "disabled"
        elif self.capacity() <= 0:
            self.status = "no_fuel"
        else:
            self.status = "ok"

    def save_state(self):
        return {"fuel": self.fuel, "energy": self.energy}

    def load_state(self, s):
        self.fuel = dict(s.get("fuel", {}))
        self.energy = s.get("energy", 0.0)

    def info_lines(self):
        d = self.game.data
        fuels = ", ".join(d.item_name(f) for f in self.fuels)
        have = ", ".join(f"{d.item_name(k)} {v}" for k, v in self.fuel.items() if v) or "없음"
        return [f"최대 출력: {self.output * (1 + self.game.gen_bonus):.0f} kW", f"현재 출력: {self.current_kw:.0f} kW",
                f"연료: {fuels}", f"보유 연료: {have}"]


class Solar(Building):
    kind = "solar"
    controllable = False

    def __init__(self, *a):
        super().__init__(*a)
        self.output = self.defn.get("output", 100)
        self.current_kw = 0.0

    def capacity(self):
        return self.output * self.game.daylight() * (1 + self.game.gen_bonus)

    def produce(self, kw, dt):
        self.current_kw = kw

    def update(self, dt):
        self.status = "ok" if self.capacity() > 0 else "idle"

    def info_lines(self):
        return [f"최대 출력: {self.output} kW (낮)", f"현재 가능 출력: {self.capacity():.0f} kW", f"햇빛: {int(self.game.daylight() * 100)}%"]


class Battery(Building):
    kind = "battery"
    ticks = False
    controllable = False

    def __init__(self, *a):
        super().__init__(*a)
        self.capacity_kj = self.defn.get("capacity", 10000)
        self.rate = self.defn.get("rate", 300)
        self.stored = 0.0
        self.flow = 0.0

    def save_state(self):
        return {"stored": self.stored}

    def load_state(self, s):
        self.stored = s.get("stored", 0.0)

    def info_lines(self):
        pct = self.stored / self.capacity_kj * 100
        f = "충전" if self.flow > 0 else ("방전" if self.flow < 0 else "대기")
        return [f"저장량: {self.stored / 1000:.1f} / {self.capacity_kj / 1000:.0f} MJ ({pct:.0f}%)", f"상태: {f} {abs(self.flow):.0f} kW"]


class Pole(Building):
    kind = "pole"
    ticks = False
    controllable = False

    def __init__(self, *a):
        super().__init__(*a)
        self.reach = self.defn.get("reach", 7)
        self.long_reach = self.defn.get("long_reach", 0)
        self.supply = self.defn.get("supply", 2)

    def info_lines(self):
        n = self.net
        if n is None:
            return ["전력망: 없음"]
        lines = [f"전력망 {n.id}: 공급 {n.supply_kw:.0f} / 부하 {n.load_kw:.0f} kW (최대 {n.capacity_kw:.0f})"]
        if n.tripped:
            lines.append("[경고] 차단기 트립됨 — [차단기 복구]를 누르세요")
        return lines


class Sensor(Building):
    kind = "sensor"
    ticks = False
    controllable = False

    def __init__(self, *a):
        super().__init__(*a)
        self.signal = False

    def sense(self):
        tx, ty = self.x + DX[self.dir], self.y + DY[self.dir]
        b = self.game.world.at(tx, ty)
        self.signal = bool(b and b.holding_items())

    def info_lines(self):
        return [f"신호: {'ON' if self.signal else 'OFF'}", "앞 칸에 아이템이 있으면 ON", "L키(신호선)로 기계에 연결"]


class Relay(Building):
    kind = "relay"
    ticks = False
    controllable = False

    def __init__(self, *a):
        super().__init__(*a)
        self.signal = False
        self.input = False
        self.nc = False          # True면 b접점(반전)

    def save_state(self):
        return {"nc": self.nc}

    def load_state(self, s):
        self.nc = s.get("nc", False)

    def info_lines(self):
        return [f"모드: {'b접점 (반전)' if self.nc else 'a접점 (그대로)'}", f"입력: {'ON' if self.input else 'OFF'}  출력: {'ON' if self.signal else 'OFF'}"]


class PLCBuilding(Building):
    kind = "plc"
    ticks = False
    controllable = False

    def __init__(self, *a):
        super().__init__(*a)
        from .plc import LadderProgram
        self.program = LadderProgram()

    def save_state(self):
        return {"program": self.program.to_dict()}

    def load_state(self, s):
        from .plc import LadderProgram
        if "program" in s:
            self.program = LadderProgram.from_dict(s["program"])

    def info_lines(self):
        p = self.program
        xs = "".join("1" if v else "0" for v in p.X)
        ys = "".join("1" if v else "0" for v in p.Y)
        return [f"렁 수: {len(p.rungs)}", f"X0-7: {xs}", f"Y0-7: {ys}", "[래더 편집] 버튼으로 프로그램 편집"]


class Core(Building):
    kind = "core"
    ticks = False
    controllable = False

    def accept(self, item, d):
        return self.game.progress.deliver_to_core(item)

    def info_lines(self):
        return self.game.progress.core_lines()


KINDS = {c.kind: c for c in (Belt, UndergroundIn, UndergroundOut, Splitter, FilterSplitter, Sink, Miner, Crafter,
                             Lab, Generator, Solar, Battery, Pole, Sensor, Relay, PLCBuilding, Core)}


def create(game, defn, x, y, d):
    return KINDS[defn["kind"]](game, defn, x, y, d)
