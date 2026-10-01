"""입력 경로 테스트: 가짜 마우스/키 이벤트로 설치·드래그·철거·신호선·저장을 검증.
실행: python tests/test_ui_input.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["FACTORY_SAVE_DIR"] = tempfile.mkdtemp()

import pygame
from src.app import App
from src.scenes import GameScene, MenuScene


def test_ui_input_flow():
    app = App()
    mouse = {"pos": (0, 0), "pressed": (False, False, False)}
    pygame.mouse.get_pos = lambda: mouse["pos"]
    pygame.mouse.get_pressed = lambda num_buttons=3: mouse["pressed"]


    def step(events=()):
        events = list(events)
        app.ui.begin(events)
        for e in events:
            app.scene.handle_event(e)
        app.scene.update(1 / 60)
        app.scene.draw(app.screen, 1 / 60)


    def click(pos, button=1):
        mouse["pos"] = pos
        mouse["pressed"] = tuple(i == button - 1 for i in range(3))
        step([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)])
        mouse["pressed"] = (False, False, False)
        step([pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button)])


    def key(k, mod=0):
        step([pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")])


    # 메뉴 → 새 게임 → 슬롯 1
    assert isinstance(app.scene, MenuScene)
    step()
    click((640, 323))                     # "새 게임"
    assert app.scene.modal == "new", app.scene.modal
    click((640, 315))                     # 슬롯 1 버튼 (창 y=235 + 56 ~ 112)
    assert isinstance(app.scene, GameScene), type(app.scene)
    sc = app.scene
    g = sc.game
    assert sc.modal == "help"
    key(pygame.K_ESCAPE)
    assert sc.modal is None

    cam = sc.cam


    def tile_pos(tx, ty):
        sx, sy = cam.to_screen(tx + 0.5, ty + 0.5)
        return int(sx), int(sy)


    # 빈 땅 찾기
    cx, cy = g.world.center
    tx, ty = cx, cy
    # 1) 벨트 선택(1키) 후 드래그로 5칸 설치
    key(pygame.K_1)
    assert sc.tool == ("build", "belt_mk1")
    start = tile_pos(tx, ty)
    mouse["pos"] = start
    mouse["pressed"] = (True, False, False)
    step([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=start, button=1)])
    for i in range(1, 5):
        mouse["pos"] = tile_pos(tx + i, ty)
        step()
    mouse["pos"] = tile_pos(tx + 4, ty + 2)   # 아래로 꺾기
    step()
    mouse["pressed"] = (False, False, False)
    step([pygame.event.Event(pygame.MOUSEBUTTONUP, pos=mouse["pos"], button=1)])
    belts = [b for b in g.buildings.values() if b.kind == "belt"]
    assert len(belts) == 7, len(belts)
    assert g.world.at(tx + 4, ty).dir == 1, "꺾이는 지점 벨트가 아래를 향해야 함"
    assert g.world.at(tx + 2, ty).dir == 0

    # 2) 우클릭 철거
    money = g.money
    click(tile_pos(tx + 2, ty), 3)
    assert g.world.at(tx + 2, ty) is None
    assert g.money > money

    # 3) R 회전 후 설치 + 툴바 버튼으로 출하장 선택
    key(pygame.K_ESCAPE)
    assert sc.tool is None
    key(pygame.K_8)
    assert sc.tool == ("build", "sink"), sc.tool
    key(pygame.K_r)
    assert sc.dir == 2
    click(tile_pos(tx, ty + 6))
    assert g.world.at(tx, ty + 6).type == "sink"

    # 4) 선택 → 정보 패널 → 철거 버튼
    key(pygame.K_ESCAPE)
    click(tile_pos(tx, ty + 6))
    assert sc.selected == g.world.at(tx, ty + 6).uid

    # 5) 돈 부족 설치 실패
    g.money = 0
    key(pygame.K_ESCAPE)
    key(pygame.K_8)
    click(tile_pos(tx + 6, ty + 6))
    assert g.world.at(tx + 6, ty + 6) is None
    assert any("돈 부족" in n["text"] for n in sc.notes)
    g.money = 10000

    # 6) 연구 트리 열기/닫기, 일시정지
    key(pygame.K_ESCAPE)
    key(pygame.K_t); assert sc.modal == "tech"
    key(pygame.K_t); assert sc.modal is None
    key(pygame.K_SPACE); assert sc.speed_i == 0
    key(pygame.K_SPACE); assert sc.speed_i == 1

    # 7) 신호선: 연구 강제 완료 후 센서 → 벨트 연결
    g.research.completed.add("sensors"); g.research.recompute_bonuses()
    key(pygame.K_TAB); key(pygame.K_TAB); key(pygame.K_TAB)
    assert sc.category == "control", sc.category
    key(pygame.K_1)
    click(tile_pos(tx + 1, ty + 1))
    sensor = g.world.at(tx + 1, ty + 1)
    assert sensor and sensor.kind == "sensor"
    key(pygame.K_l)
    assert sc.tool == ("link",)
    click(tile_pos(tx + 1, ty + 1))
    click(tile_pos(tx + 3, ty))
    assert len(g.control.links) == 1, g.control.links

    # 7b) 툴바 버튼으로 같은 프레임에 모달 열기 (회귀 테스트)
    key(pygame.K_ESCAPE)
    click((1028, 725))
    assert sc.modal == "tech", sc.modal
    key(pygame.K_ESCAPE)
    click((1220, 725))
    assert sc.modal == "pause", sc.modal
    key(pygame.K_ESCAPE)

    # 8) F5 저장 → 메뉴 → 불러오기
    assert sc.modal is None
    key(pygame.K_F5)
    n_build = len(g.buildings)
    from src import save
    assert save.slot_info(1) is not None
    app.goto_menu()
    step()
    click((640, 379))           # 불러오기
    assert app.scene.modal == "load"
    click((640, 315))
    assert isinstance(app.scene, GameScene)
    assert len(app.scene.game.buildings) == n_build
    assert len(app.scene.game.control.links) == 1
    pygame.quit()


if __name__ == "__main__":
    test_ui_input_flow()
    print("ALL UI INPUT TESTS PASSED")
