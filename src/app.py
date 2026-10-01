"""메인 루프: 고정 틱 시뮬레이션(20틱/초) + 60fps 렌더링."""
import os

import pygame

from . import save, sound, sprites, fonts
from .config import SCREEN_W, SCREEN_H, FPS, TITLE
from .data import GameData
from .game import Game
from .scenes import MenuScene, GameScene
from .ui.widgets import UI


class App:
    def __init__(self, smoke_frames=0, screenshot=None, autostart=False):
        pygame.init()
        pygame.key.set_repeat(0)
        flags = pygame.RESIZABLE
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
        pygame.display.set_caption(TITLE)
        pygame.display.set_icon(sprites.make_icon(64))
        self.clock = pygame.time.Clock()
        self.data = GameData()
        self.settings = save.load_settings()
        sound.init(self.settings.get("volume", 0.6))
        self.ui = UI()
        self.running = True
        self.smoke_frames = smoke_frames
        self.screenshot = screenshot
        self.scene = MenuScene(self)
        if autostart:
            self.scene = GameScene(self, Game(self.data), new=False)

    # ---------------- 씬 전환 ----------------
    def goto_menu(self):
        self.scene = MenuScene(self)

    def new_game(self, slot):
        g = Game(self.data)
        g.slot = slot
        try:
            save.save_game(g, slot)
        except OSError:
            pass
        self.scene = GameScene(self, g, new=True)

    def load_slot(self, slot):
        try:
            g = save.load_game(self.data, slot)
        except Exception as e:
            if hasattr(self.scene, "note"):
                self.scene.note(f"불러오기 실패: {e}", "bad", 4)
            print("불러오기 실패:", e)
            return
        self.scene = GameScene(self, g)
        self.scene.note(f"슬롯 {slot} 불러옴", "good", 3)

    # ---------------- 루프 ----------------
    def run(self):
        frame = 0
        while self.running:
            dt = min(0.1, self.clock.tick(FPS) / 1000.0)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    if isinstance(self.scene, GameScene):
                        self.scene.autosave(quiet=True)
                    self.running = False
            self.ui.begin(events)
            scene = self.scene
            for e in events:
                scene.handle_event(e)
            scene.update(dt)
            self.scene.draw(self.screen, dt)
            pygame.display.flip()
            frame += 1
            if self.smoke_frames and frame >= self.smoke_frames:
                if self.screenshot:
                    pygame.image.save(self.screen, self.screenshot)
                self.running = False
        pygame.quit()
