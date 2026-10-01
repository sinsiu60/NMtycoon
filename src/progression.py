"""시대 마일스톤, 주문 의뢰, 메가 프로젝트."""
import random


class Progression:
    def __init__(self, game):
        self.game = game
        self.orders = []          # {"item","qty","done","time_left","reward"}
        self.order_timer = 30.0   # 첫 주문은 30초 뒤
        self.core_stage = 0
        self.core_delivered = {}
        self.completed = False    # 메가 프로젝트 완료(엔딩 봤음)
        self.ending_pending = False
        self.rng = random.Random()
        self._check_acc = 0.0

    @property
    def cfg(self):
        return self.game.data.progression

    # ---------------- 마일스톤 ----------------
    def milestone(self):
        e = self.game.data.eras.get(self.game.era)
        return e.get("milestone") if e else None

    def milestone_progress(self):
        m = self.milestone()
        if not m:
            return []
        prod = self.game.stats_produced
        return [(i, min(prod.get(i, 0), n), n) for i, n in m["produce"].items()]

    def tick(self, dt):
        self._check_acc += dt
        if self._check_acc >= 0.5:
            self._check_acc = 0.0
            m = self.milestone()
            if m and all(have >= need for _, have, need in self.milestone_progress()):
                self.advance_era()
        self._tick_orders(dt)

    def advance_era(self):
        g = self.game
        g.era += 1
        e = g.data.eras.get(g.era, {})
        g.notify(f"[마일스톤] 마일스톤 달성! {e.get('name', '')} 시대 해금 — {e.get('desc', '')}", "gold", "fanfare", popup=True)

    # ---------------- 주문 의뢰 ----------------
    def _orderable_items(self):
        g = self.game
        items = set()
        for r in g.data.recipes.values():
            if g.is_unlocked(r.get("unlock")):
                items.update(r["outputs"])
        items -= {"petroleum", "nuclear_fuel"}
        return sorted(items, key=lambda i: g.data.item_order.index(i))

    def _tick_orders(self, dt):
        c = self.cfg["orders"]
        for o in self.orders:
            o["time_left"] -= dt
        expired = [o for o in self.orders if o["time_left"] <= 0]
        for o in expired:
            self.game.notify(f"[주문] 주문 실패: {self.game.data.item_name(o['item'])} {o['qty']}개", "warn", "fail")
            self.orders.remove(o)
        self.order_timer -= dt
        if self.order_timer <= 0:
            self.order_timer = c["interval"]
            if len(self.orders) < c["max_active"]:
                self.new_order()

    def new_order(self):
        g = self.game
        c = self.cfg["orders"]
        items = [i for i in self._orderable_items() if i not in {o["item"] for o in self.orders}]
        if not items:
            return
        # 최신 시대 아이템이 나올 확률을 높게
        weights = [1 + g.data.items[i]["tier"] ** 2 for i in items]
        item = self.rng.choices(items, weights)[0]
        value = g.data.items[item]["value"]
        target = c["base_value_target"] * (1.6 ** (g.era - 1))
        qty = max(5, int(round(target / value / 5)) * 5)
        reward = int(value * qty * c["reward_mult"] + c["reward_bonus_per_era"] * g.era)
        t = self.rng.uniform(c["time_min"], c["time_max"])
        self.orders.append({"item": item, "qty": qty, "done": 0, "time_left": t, "time_total": t, "reward": reward})
        g.notify(f"[주문] 새 주문: {g.data.item_name(item)} {qty}개 ({int(t // 60)}분 안에) 보상 ${reward:,}", "accent", "click")

    def on_sold(self, item):
        for o in self.orders:
            if o["item"] == item:
                o["done"] += 1
                if o["done"] >= o["qty"]:
                    self.orders.remove(o)
                    self.game.add_money(o["reward"])
                    self.game.notify(f"[주문 완료] {self.game.data.item_name(item)} {o['qty']}개 → 보너스 ${o['reward']:,}", "gold", "coin")
                return

    # ---------------- 메가 프로젝트 ----------------
    def stages(self):
        return self.cfg["megaproject"]["stages"]

    def deliver_to_core(self, item):
        st = self.stages()
        if self.core_stage >= len(st):
            return False
        need = st[self.core_stage]["items"]
        if item not in need or self.core_delivered.get(item, 0) >= need[item]:
            return False
        self.core_delivered[item] = self.core_delivered.get(item, 0) + 1
        if all(self.core_delivered.get(i, 0) >= n for i, n in need.items()):
            self.core_stage += 1
            self.core_delivered = {}
            if self.core_stage >= len(st):
                self.completed = True
                self.ending_pending = True
                self.game.era = max(self.game.era, 7)
                self.game.notify("[축하] 무인 스마트 팩토리 코어 완성!", "gold", "fanfare")
            else:
                self.game.notify(f"[메가 프로젝트] 메가 프로젝트 {st[self.core_stage - 1]['name']} 완료!", "gold", "fanfare", popup=True)
        return True

    def core_lines(self):
        st = self.stages()
        if self.core_stage >= len(st):
            return ["완성! 무한 연구가 해금되었습니다"]
        s = st[self.core_stage]
        d = self.game.data
        lines = [f"{s['name']} ({self.core_stage + 1}/{len(st)})"]
        for i, n in s["items"].items():
            lines.append(f"  {d.item_name(i)}: {self.core_delivered.get(i, 0)}/{n}")
        return lines

    # ---------------- 저장 ----------------
    def to_dict(self):
        return {"orders": self.orders, "order_timer": self.order_timer, "core_stage": self.core_stage,
                "core_delivered": self.core_delivered, "completed": self.completed}

    def load(self, d):
        items = self.game.data.items
        self.orders = [o for o in d.get("orders", []) if o.get("item") in items]
        self.order_timer = d.get("order_timer", 60.0)
        self.core_stage = d.get("core_stage", 0)
        self.core_delivered = dict(d.get("core_delivered", {}))
        self.completed = d.get("completed", False)
