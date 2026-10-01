"""게임 전역 상수."""

TITLE = "공장 자동화 타이쿤"
SCREEN_W, SCREEN_H = 1280, 760
FPS = 60
TICK_RATE = 20                 # 시뮬레이션 틱/초
TICK_DT = 1.0 / TICK_RATE
SPEEDS = [0, 1, 2, 4]          # 일시정지 / 1배 / 2배 / 4배

MAP_W, MAP_H = 160, 160
ZOOM_LEVELS = [12, 16, 20, 24, 32, 40, 48, 64]
DEFAULT_ZOOM = 4               # ZOOM_LEVELS 인덱스 (32px)

# 방향: 0=동(→) 1=남(↓) 2=서(←) 3=북(↑)
DX = (1, 0, -1, 0)
DY = (0, 1, 0, -1)

BELT_SPACING = 0.25            # 벨트 위 아이템 최소 간격 (칸) → 칸당 최대 4개
REFUND_RATE = 0.75             # 철거 환불률
TRIP_DELAY = 1.0               # 과부하 지속 시간(초) 이후 차단기 트립
AUTO_RECLOSE_DELAY = 5.0
DAY_LENGTH = 480.0             # 낮밤 한 주기(초)
AUTOSAVE_INTERVAL = 300.0      # 5분

# 색상 팔레트
C_BG = (22, 24, 28)
C_GROUND = (46, 52, 46)
C_GROUND2 = (50, 56, 50)
C_GRID = (58, 64, 58)
C_PANEL = (30, 33, 40)
C_PANEL2 = (40, 44, 54)
C_BORDER = (80, 88, 104)
C_TEXT = (230, 232, 238)
C_DIM = (150, 155, 165)
C_ACCENT = (90, 170, 255)
C_GOOD = (90, 210, 110)
C_WARN = (240, 190, 60)
C_BAD = (235, 75, 70)
C_MONEY = (250, 215, 90)
