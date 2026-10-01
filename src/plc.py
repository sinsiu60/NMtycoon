"""PLC 래더 프로그램.

렁(Rung) = 최대 3개의 행(병렬 분기) x 5칸 접점 + 출력 1칸.
- 한 행 안의 접점은 직렬(AND), 행끼리는 병렬(OR).
- 접점: NO(A접점), NC(B접점)  주소 X/Y/M/T/C
- 출력: COIL(Y/M), TON(T, 프리셋=초), CTU(C, 프리셋=횟수), RST(T/C 리셋)
"""

COLS = 5
MAX_ROWS = 3
CONTACTS = ("NO", "NC")
OUTPUTS = ("COIL", "TON", "CTU", "RST")
ADDR_COUNT = {"X": 8, "Y": 8, "M": 16, "T": 8, "C": 8}


def parse_addr(a):
    try:
        k, i = a[0], int(a[1:])
        if k in ADDR_COUNT and 0 <= i < ADDR_COUNT[k]:
            return k, i
    except (ValueError, IndexError, TypeError):
        pass
    return None, None


class Rung:
    def __init__(self):
        self.rows = [[None] * COLS]
        self.out = None
        # 표시용 통전 상태
        self.flow = []           # 행별 칸별 bool
        self.energized = False

    def to_dict(self):
        return {"rows": self.rows, "out": self.out}

    @classmethod
    def from_dict(cls, d):
        r = cls()
        rows = d.get("rows") or [[None] * COLS]
        r.rows = [(list(row) + [None] * COLS)[:COLS] for row in rows[:MAX_ROWS]]
        r.out = d.get("out")
        return r


class LadderProgram:
    def __init__(self):
        self.rungs = [Rung()]
        self.X = [False] * 8
        self.Y = [False] * 8
        self.M = [False] * 16
        self.T_acc = [0.0] * 8
        self.T_done = [False] * 8
        self.C_cnt = [0] * 8
        self.C_done = [False] * 8
        self.C_prev = [False] * 8

    # ---------- 저장 ----------
    def to_dict(self):
        return {"rungs": [r.to_dict() for r in self.rungs], "M": self.M, "C": self.C_cnt}

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.rungs = [Rung.from_dict(r) for r in d.get("rungs", [])] or [Rung()]
        m = d.get("M")
        if m:
            p.M = (list(m) + [False] * 16)[:16]
        c = d.get("C")
        if c:
            p.C_cnt = (list(c) + [0] * 8)[:8]
        return p

    # ---------- 실행 ----------
    def read(self, addr):
        k, i = parse_addr(addr)
        if k == "X":
            return self.X[i]
        if k == "Y":
            return self.Y[i]
        if k == "M":
            return self.M[i]
        if k == "T":
            return self.T_done[i]
        if k == "C":
            return self.C_done[i]
        return False

    def contact(self, el):
        v = self.read(el.get("a"))
        return (not v) if el.get("t") == "NC" else v

    def scan(self, dt):
        for r in self.rungs:
            flows = []
            any_contact = False
            power = False
            for row in r.rows:
                f = []
                ok = True
                has = False
                for el in row:
                    if el is None:
                        f.append(ok)
                        continue
                    has = True
                    ok = ok and self.contact(el)
                    f.append(ok)
                flows.append(f)
                if has:
                    any_contact = True
                    power = power or ok
            if not any_contact:
                power = r.out is not None
            r.flow = flows
            r.energized = power
            self._output(r.out, power, dt)

    def _output(self, el, power, dt):
        if not el:
            return
        k, i = parse_addr(el.get("a"))
        if k is None:
            return
        t = el.get("t")
        if t == "COIL":
            if k == "Y":
                self.Y[i] = power
            elif k == "M":
                self.M[i] = power
        elif t == "TON" and k == "T":
            pre = float(el.get("p", 1))
            if power:
                self.T_acc[i] = min(pre, self.T_acc[i] + dt)
                self.T_done[i] = self.T_acc[i] >= pre
            else:
                self.T_acc[i] = 0.0
                self.T_done[i] = False
        elif t == "CTU" and k == "C":
            pre = int(el.get("p", 1))
            if power and not self.C_prev[i]:
                self.C_cnt[i] += 1
            self.C_prev[i] = power
            self.C_done[i] = self.C_cnt[i] >= pre
        elif t == "RST" and power:
            if k == "T":
                self.T_acc[i] = 0.0
                self.T_done[i] = False
            elif k == "C":
                self.C_cnt[i] = 0
                self.C_done[i] = False
