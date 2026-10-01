"""신호선 시스템: 센서/릴레이/PLC → 기계 ON/OFF.

link = {"src": uid, "dst": uid, "port": n}
- src 가 PLC 이면 port = 출력 Y 번호
- dst 가 PLC 이면 연결된 순서대로 X0, X1, ...
- 일반 기계는 들어오는 신호 중 하나라도 ON이면 가동 (invert면 반대)
"""

SOURCE_KINDS = ("sensor", "relay", "plc")


class ControlSystem:
    def __init__(self, game):
        self.game = game
        self.links = []
        self._index = None

    def _rebuild(self):
        idx = {}
        for l in self.links:
            idx.setdefault(l["dst"], []).append(l)
        self._index = idx

    def can_link(self, src, dst):
        if src is None or dst is None or src is dst:
            return "같은 건물에는 연결할 수 없습니다"
        if src.kind not in SOURCE_KINDS:
            return "신호 출발점은 센서/릴레이/PLC여야 합니다"
        if dst.kind == "sensor" or not (dst.controllable or dst.kind in ("relay", "plc")):
            return f"{dst.name}은(는) 신호를 받을 수 없습니다"
        for l in self.links:
            if l["src"] == src.uid and l["dst"] == dst.uid:
                return "이미 연결되어 있습니다"
        if dst.kind == "plc" and sum(1 for l in self.links if l["dst"] == dst.uid) >= 8:
            return "PLC 입력(X0~X7)이 가득 찼습니다"
        if src.kind == "plc" and self._next_port(src) is None:
            return "PLC 출력(Y0~Y7)이 가득 찼습니다"
        return None

    def _next_port(self, src):
        used = {l["port"] for l in self.links if l["src"] == src.uid}
        for i in range(8):
            if i not in used:
                return i
        return None

    def add_link(self, src, dst):
        err = self.can_link(src, dst)
        if err:
            return err
        port = self._next_port(src) if src.kind == "plc" else 0
        self.links.append({"src": src.uid, "dst": dst.uid, "port": port})
        self._index = None
        return None

    def remove_links_of(self, uid):
        n = len(self.links)
        self.links = [l for l in self.links if l["src"] != uid and l["dst"] != uid]
        if len(self.links) != n:
            self._index = None

    def remove_links_between(self, a, b):
        self.links = [l for l in self.links if {l["src"], l["dst"]} != {a, b}]
        self._index = None

    def inputs_of(self, uid):
        if self._index is None:
            self._rebuild()
        return self._index.get(uid, [])

    def outputs_of(self, uid):
        return [l for l in self.links if l["src"] == uid]

    def source_value(self, b, port):
        if b is None:
            return False
        if b.kind == "plc":
            return b.program.Y[port] if 0 <= port < 8 else False
        return getattr(b, "signal", False)

    def tick(self, dt):
        g = self.game
        bs = g.buildings
        if self._index is None:
            self._rebuild()
        for b in g.signal_nodes:
            if b.kind == "sensor":
                b.sense()
        for b in g.signal_nodes:
            ins = self._index.get(b.uid, [])
            if b.kind == "relay":
                b.input = any(self.source_value(bs.get(l["src"]), l["port"]) for l in ins)
                b.signal = b.input != b.nc
            elif b.kind == "plc":
                p = b.program
                for i in range(8):
                    p.X[i] = False
                for i, l in enumerate(ins[:8]):
                    p.X[i] = self.source_value(bs.get(l["src"]), l["port"])
                p.scan(dt)
        for b in g.ticking:
            ins = self._index.get(b.uid)
            if ins:
                b.controlled = True
                on = any(self.source_value(bs.get(l["src"]), l["port"]) for l in ins)
                b.enabled = on != b.invert
            elif b.controlled:
                b.controlled = False
                b.enabled = True
