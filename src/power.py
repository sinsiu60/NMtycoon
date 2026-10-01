"""전력 시스템: 전신주/변압기/철탑으로 전력망을 구성하고 매 틱 공급·부하를 계산한다.

연결 규칙
- 단거리 선(reach): 전신주·변압기끼리, 거리 <= 두 reach 중 작은 값
- 장거리 선(long_reach): 철탑·변압기끼리, 거리 <= 두 long_reach 중 작은 값
- 전신주의 supply 반경 안 타일에 걸친 건물은 그 전력망에 연결
"""
import math
from collections import deque

from .config import TRIP_DELAY, AUTO_RECLOSE_DELAY


class PowerNet:
    def __init__(self, nid):
        self.id = nid
        self.poles = []
        self.consumers = []
        self.producers = []      # 발전기, 태양광 (capacity/produce 보유)
        self.batteries = []
        self.tripped = False
        self.overload_timer = 0.0
        self.reclose_timer = 0.0
        self.supply_kw = 0.0
        self.load_kw = 0.0
        self.demand_kw = 0.0
        self.capacity_kw = 0.0
        self.history = deque(maxlen=60)   # (공급, 부하, 최대) 초당 1개
        self._hist_acc = 0.0

    @property
    def overloaded(self):
        return self.overload_timer > 0


class PowerSystem:
    def __init__(self, game):
        self.game = game
        self.nets = []
        self.edges = []          # (pole_a, pole_b, long?) 그리기용
        self.dirty = True

    def mark_dirty(self):
        self.dirty = True

    # ------------------------------------------------------------------
    def rebuild(self):
        g = self.game
        old_tripped = {}
        for n in self.nets:
            for p in n.poles:
                old_tripped[p.uid] = n
        poles = [b for b in g.buildings.values() if b.kind == "pole"]
        parent = {p.uid: p.uid for p in poles}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        self.edges = []
        for i, a in enumerate(poles):
            ax, ay = a.center()
            for b in poles[i + 1:]:
                bx, by = b.center()
                d = math.hypot(ax - bx, ay - by)
                short = min(a.reach, b.reach)
                long_ = min(a.long_reach, b.long_reach)
                link = None
                if short > 0 and d <= short:
                    link = False
                elif long_ > 0 and d <= long_:
                    link = True
                if link is not None:
                    self.edges.append((a, b, link))
                    ra, rb = find(a.uid), find(b.uid)
                    if ra != rb:
                        parent[ra] = rb

        groups = {}
        for p in poles:
            groups.setdefault(find(p.uid), []).append(p)
        nets = []
        for i, (_, ps) in enumerate(sorted(groups.items(), key=lambda kv: min(p.uid for p in kv[1]))):
            n = PowerNet(i + 1)
            n.poles = ps
            prev = [old_tripped[p.uid] for p in ps if p.uid in old_tripped]
            if prev:
                n.tripped = any(o.tripped for o in prev)
                n.history = deque(prev[0].history, maxlen=60)
            nets.append(n)
            for p in ps:
                p.net = n

        for b in g.buildings.values():
            if b.kind != "pole":
                b.net = None
        w = g.world
        for n in nets:
            seen = set()
            for p in n.poles:
                r = p.supply
                if r <= 0:
                    continue
                for ty in range(p.y - r, p.y + r + 1):
                    for tx in range(p.x - r, p.x + r + 1):
                        b = w.at(tx, ty)
                        if b is None or b.uid in seen or b.kind == "pole" or b.net is not None:
                            continue
                        seen.add(b.uid)
                        if b.kind in ("generator", "solar"):
                            b.net = n
                            n.producers.append(b)
                        elif b.kind == "battery":
                            b.net = n
                            n.batteries.append(b)
                        elif b.needs_power:
                            b.net = n
                            n.consumers.append(b)
        self.nets = nets
        self.dirty = False

    # ------------------------------------------------------------------
    def tick(self, dt):
        if self.dirty:
            self.rebuild()
        g = self.game
        for b in g.ticking:
            if b.needs_power and b.net is None:
                b.power_sat = 0.0
                b.shed = False
        smart = "smart_grid" in g.flags
        shed_low = "priority_shed" in g.flags
        auto = "auto_reclose" in g.flags
        for n in self.nets:
            self._solve(n, dt, smart, shed_low, auto)

    def _solve(self, n, dt, smart, shed_low, auto):
        g = self.game
        cons = n.consumers
        demand = 0.0
        for c in cons:
            c.shed = False
            demand += c.demand
        n.demand_kw = demand
        cap_gen = 0.0
        caps = []
        for p in n.producers:
            c = p.capacity()
            caps.append(c)
            cap_gen += c
        bat_out = sum(min(b.rate, b.stored / dt) for b in n.batteries)
        bat_in = sum(min(b.rate, (b.capacity_kj - b.stored) / dt) for b in n.batteries)
        n.capacity_kw = cap_gen + bat_out

        if n.tripped:
            for c in cons:
                c.power_sat = 0.0
            for p in n.producers:
                p.produce(0.0, dt)
            n.supply_kw = 0.0
            n.load_kw = 0.0
            if auto:
                n.reclose_timer += dt
                if n.reclose_timer >= AUTO_RECLOSE_DELAY:
                    n.tripped = False
                    n.reclose_timer = 0.0
                    n.overload_timer = 0.0
                    g.notify(f"전력망 {n.id}: 차단기 자동 재투입", "warn", "click")
            self._history(n, dt)
            return

        total_cap = cap_gen + bat_out
        if demand > total_cap and total_cap > 0 and (smart or shed_low):
            # 우선순위 낮은 기계부터 차단
            order = sorted((c for c in cons if c.demand > 0), key=lambda c: c.priority)
            for c in order:
                if demand <= total_cap:
                    break
                if not smart and c.priority > 0:
                    break
                c.shed = True
                demand -= c.demand
        served = min(demand, total_cap)
        sat = served / demand if demand > 0 else 1.0
        if total_cap <= 0:
            sat = 0.0
        for c in cons:
            c.power_sat = 0.0 if c.shed else sat

        charge = 0.0
        if cap_gen > served:
            charge = min(bat_in, cap_gen - served)
        discharge = max(0.0, served - cap_gen)
        gen_out = min(cap_gen, served + charge)
        for p, c in zip(n.producers, caps):
            p.produce(gen_out * c / cap_gen if cap_gen > 0 else 0.0, dt)
        if n.batteries:
            if charge > 0 and bat_in > 0:
                for b in n.batteries:
                    room = min(b.rate, (b.capacity_kj - b.stored) / dt)
                    kw = charge * room / bat_in
                    b.stored = min(b.capacity_kj, b.stored + kw * dt)
                    b.flow = kw
            elif discharge > 0 and bat_out > 0:
                for b in n.batteries:
                    avail = min(b.rate, b.stored / dt)
                    kw = discharge * avail / bat_out
                    b.stored = max(0.0, b.stored - kw * dt)
                    b.flow = -kw
            else:
                for b in n.batteries:
                    b.flow = 0.0
        n.supply_kw = gen_out + discharge
        n.load_kw = served

        if demand > total_cap + 1e-6 and total_cap > 0 and not smart:
            n.overload_timer += dt
            if n.overload_timer >= TRIP_DELAY:
                n.tripped = True
                n.overload_timer = 0.0
                n.reclose_timer = 0.0
                g.notify(f"[경고] 전력망 {n.id} 과부하! 차단기 트립 (부하 {demand:.0f} > 공급 {total_cap:.0f} kW)", "bad", "alarm")
        else:
            n.overload_timer = 0.0
        self._history(n, dt)

    def _history(self, n, dt):
        n._hist_acc += dt
        if n._hist_acc >= 1.0:
            n._hist_acc -= 1.0
            n.history.append((n.supply_kw, n.demand_kw, n.capacity_kw))

    def reset(self, net):
        if net and net.tripped:
            net.tripped = False
            net.overload_timer = 0.0
            self.game.notify(f"전력망 {net.id}: 차단기 수동 복구", "good", "click")
