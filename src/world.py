"""그리드 맵과 광맥 생성."""
import math
import random

SOLID_ORES = ("iron_ore", "copper_ore", "coal", "sand", "uranium_ore")


class World:
    def __init__(self, w, h, seed):
        self.w, self.h = w, h
        self.seed = seed
        self.ore = [[None] * w for _ in range(h)]
        self.grid = [[None] * w for _ in range(h)]
        self.version = 0          # 건물 배치가 바뀔 때마다 증가 (캐시 무효화용)
        self._generate()

    @property
    def center(self):
        return self.w // 2, self.h // 2

    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def at(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.grid[y][x]
        return None

    def ore_at(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.ore[y][x]
        return None

    # ------------------------------------------------------------------
    def _blob(self, rng, cx, cy, radius, ore, density=1.0):
        r = int(radius) + 2
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if not self.in_bounds(x, y):
                    continue
                d = math.hypot(x - cx, y - cy)
                ang = math.atan2(y - cy, x - cx)
                wobble = 1.0 + 0.25 * math.sin(ang * 3 + cx) + 0.15 * math.cos(ang * 5 + cy)
                if d <= radius * wobble and rng.random() < density:
                    self.ore[y][x] = ore

    def _generate(self):
        rng = random.Random(self.seed)
        cx, cy = self.center
        start_angle = rng.random() * math.tau

        def place(ore, dist, radius, angle=None, density=1.0):
            a = angle if angle is not None else rng.random() * math.tau
            x = int(cx + math.cos(a) * dist)
            y = int(cy + math.sin(a) * dist)
            self._blob(rng, x, y, radius, ore, density)

        # 시작 지점 근처에 반드시 철/구리/석탄
        place("iron_ore", 9, 4.5, start_angle)
        place("copper_ore", 10, 4.0, start_angle + 2.1)
        place("coal", 9, 3.5, start_angle + 4.2)
        place("sand", 22, 4.0, start_angle + 1.0)
        # 추가 광맥
        for _ in range(9):
            place("iron_ore", rng.uniform(25, 70), rng.uniform(4, 7))
        for _ in range(8):
            place("copper_ore", rng.uniform(25, 70), rng.uniform(4, 6.5))
        for _ in range(7):
            place("coal", rng.uniform(25, 70), rng.uniform(3.5, 6))
        for _ in range(4):
            place("sand", rng.uniform(30, 70), rng.uniform(4, 6))
        # 원유: 띄엄띄엄 있는 웅덩이
        for _ in range(6):
            place("crude_oil", rng.uniform(30, 65), rng.uniform(3, 4.5), density=0.35)
        for _ in range(3):
            place("uranium_ore", rng.uniform(45, 72), rng.uniform(3, 4.5))
        # 시작 지점 정중앙 3칸은 비워둔다
        for y in range(cy - 2, cy + 3):
            for x in range(cx - 2, cx + 3):
                self.ore[y][x] = None
