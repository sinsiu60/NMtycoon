"""연구 트리 관리."""


class Research:
    def __init__(self, game):
        self.game = game
        self.completed = set()
        self.levels = {}         # 반복 연구 단계
        self.progress = {}       # tech -> 완료 단위 수
        self.current = None

    def tech(self, tid):
        return self.game.data.techs[tid]

    def units_needed(self, tid):
        t = self.tech(tid)
        if t.get("repeatable"):
            return int(t["units"] * (1 + 0.5 * self.levels.get(tid, 0)))
        return t["units"]

    def is_done(self, tid):
        return tid in self.completed and not self.tech(tid).get("repeatable")

    def can_research(self, tid):
        t = self.tech(tid)
        if self.is_done(tid):
            return False
        if self.game.era < t["era"]:
            return False
        return all(p in self.completed for p in t["prereqs"])

    def state(self, tid):
        if self.is_done(tid):
            return "done"
        if self.current == tid:
            return "researching"
        if self.can_research(tid):
            return "available"
        return "locked"

    def set_current(self, tid):
        if tid is None or self.can_research(tid):
            self.current = tid
            return True
        return False

    def add_unit(self, tid):
        if self.is_done(tid):
            return
        self.progress[tid] = self.progress.get(tid, 0) + 1
        if self.progress[tid] >= self.units_needed(tid):
            self.complete(tid)

    def complete(self, tid):
        t = self.tech(tid)
        self.progress[tid] = 0
        self.completed.add(tid)
        if t.get("repeatable"):
            self.levels[tid] = self.levels.get(tid, 0) + 1
            name = f"{t['name']} Lv.{self.levels[tid]}"
        else:
            name = t["name"]
            if self.current == tid:
                self.current = None
        self.recompute_bonuses()
        self.game.notify(f"[연구] 연구 완료: {name} — {t.get('desc', '')}", "good", "research")

    def recompute_bonuses(self):
        g = self.game
        g.craft_bonus = g.mining_bonus = g.gen_bonus = 0.0
        g.flags = set()
        for tid in self.completed:
            t = self.tech(tid)
            mult = self.levels.get(tid, 1) if t.get("repeatable") else 1
            e = t.get("effects", {})
            g.craft_bonus += e.get("craft_speed", 0) * mult
            g.mining_bonus += e.get("mining_speed", 0) * mult
            g.gen_bonus += e.get("gen_output", 0) * mult
            if "flag" in e:
                g.flags.add(e["flag"])

    def fraction(self, tid):
        return self.progress.get(tid, 0) / max(1, self.units_needed(tid))

    def to_dict(self):
        return {"completed": sorted(self.completed), "levels": self.levels, "progress": self.progress, "current": self.current}

    def load(self, d):
        techs = self.game.data.techs
        self.completed = {t for t in d.get("completed", []) if t in techs}
        self.levels = {k: v for k, v in d.get("levels", {}).items() if k in techs}
        self.progress = {k: v for k, v in d.get("progress", {}).items() if k in techs}
        cur = d.get("current")
        self.current = cur if cur in techs else None
        self.recompute_bonuses()
