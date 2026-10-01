"""가벼운 즉시모드(immediate-mode) UI.

매 프레임 UI를 그리면서 동시에 클릭을 처리한다. UI가 소비하지 않은 클릭만 월드(맵)로 넘어간다.
"""
import pygame

from .. import fonts, sound
from ..config import C_PANEL, C_PANEL2, C_BORDER, C_TEXT, C_DIM, C_ACCENT

COLORS = {
    "text": C_TEXT, "dim": C_DIM, "accent": C_ACCENT, "good": (90, 210, 110), "warn": (240, 190, 60),
    "bad": (235, 75, 70), "gold": (250, 215, 90),
}


class UI:
    def __init__(self):
        self.mouse = (0, 0)
        self.clicks = []          # [(pos, button)] 이번 프레임 미처리 클릭
        self.blockers = []        # 이번 프레임 UI 영역 (월드 클릭 차단)
        self.prev_blockers = []
        self.tooltip = None
        self.wheel = 0
        self.modal = False        # 모달 창이 떠 있으면 월드 입력 차단

    def begin(self, events):
        self.prev_blockers = self.blockers
        self.blockers = []
        self.clicks = []
        self.wheel = 0
        self.tooltip = None
        self.mouse = pygame.mouse.get_pos()
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
                self.clicks.append((e.pos, e.button))
            elif e.type == pygame.MOUSEWHEEL:
                self.wheel += e.y

    def over_ui(self, pos=None):
        p = pos or self.mouse
        return self.modal or any(r.collidepoint(p) for r in self.prev_blockers + self.blockers)

    def block(self, rect):
        self.blockers.append(pygame.Rect(rect))

    def click_in(self, rect, button=1):
        rect = pygame.Rect(rect)
        for c in self.clicks:
            if c[1] == button and rect.collidepoint(c[0]):
                self.clicks.remove(c)
                return True
        return False

    def eat_clicks_in(self, rect):
        rect = pygame.Rect(rect)
        self.clicks = [c for c in self.clicks if not rect.collidepoint(c[0])]

    def eat_all(self):
        self.clicks = []

    def hover(self, rect):
        return pygame.Rect(rect).collidepoint(self.mouse)

    # ---------------- 위젯 ----------------
    def panel(self, surf, rect, color=C_PANEL, border=C_BORDER, alpha=235, radius=6):
        rect = pygame.Rect(rect)
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
        pygame.draw.rect(s, (*border, 255), s.get_rect(), 1, border_radius=radius)
        surf.blit(s, rect)
        self.block(rect)
        return rect

    def button(self, surf, rect, text, enabled=True, selected=False, tooltip=None, size=15, color=None, sound_name="click"):
        rect = pygame.Rect(rect)
        hov = self.hover(rect)
        if not enabled:
            bg = (38, 40, 46)
        elif selected:
            bg = (50, 95, 150)
        elif hov:
            bg = (62, 68, 84)
        else:
            bg = color or C_PANEL2
        pygame.draw.rect(surf, bg, rect, border_radius=5)
        pygame.draw.rect(surf, C_ACCENT if selected else C_BORDER, rect, 1, border_radius=5)
        if text:
            fonts.draw(surf, text, rect.center, size, C_TEXT if enabled else (110, 112, 120), anchor="center")
        self.block(rect)
        if hov and tooltip:
            self.tooltip = tooltip
        if self.click_in(rect):
            if enabled:
                if sound_name:
                    sound.play(sound_name)
                return True
            sound.play("error")
        return False

    def text(self, surf, text, pos, size=15, color="text", bold=False, anchor="topleft"):
        c = COLORS.get(color, color) if isinstance(color, str) else color
        return fonts.draw(surf, text, pos, size, c, bold, anchor)

    def bar(self, surf, rect, frac, color=(90, 210, 110), bg=(25, 27, 32)):
        rect = pygame.Rect(rect)
        pygame.draw.rect(surf, bg, rect, border_radius=3)
        f = max(0.0, min(1.0, frac))
        if f > 0:
            pygame.draw.rect(surf, color, (rect.x, rect.y, max(2, int(rect.w * f)), rect.h), border_radius=3)
        pygame.draw.rect(surf, C_BORDER, rect, 1, border_radius=3)

    def draw_tooltip(self, surf):
        if not self.tooltip:
            return
        lines = []
        for ln in str(self.tooltip).split("\n"):
            lines += fonts.wrap(ln, 14, 320)
        w = max(fonts.width(l, 14) for l in lines) + 16
        h = len(lines) * 18 + 10
        x, y = self.mouse[0] + 16, self.mouse[1] + 16
        sw, sh = surf.get_size()
        x = min(x, sw - w - 4)
        y = min(y, sh - h - 4)
        pygame.draw.rect(surf, (18, 20, 26), (x, y, w, h), border_radius=5)
        pygame.draw.rect(surf, C_BORDER, (x, y, w, h), 1, border_radius=5)
        for i, l in enumerate(lines):
            fonts.draw(surf, l, (x + 8, y + 5 + i * 18), 14, C_TEXT)


def dim_screen(surf, alpha=150):
    s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    s.fill((0, 0, 0, alpha))
    surf.blit(s, (0, 0))
