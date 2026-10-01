"""효과음: 외부 파일 없이 numpy로 파형을 직접 만든다."""
import numpy as np
import pygame

RATE = 22050
_sounds = {}
_ok = False
_volume = 0.6


def _env(n, attack=0.01, release=0.08):
    e = np.ones(n)
    a = max(1, min(n // 2, int(RATE * attack)))
    r = max(1, min(n // 2, int(RATE * release)))
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return e


def _tone(freq, dur, wave="sine", vol=0.5, slide=0.0):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    f = freq + slide * t / max(dur, 1e-6)
    ph = 2 * np.pi * np.cumsum(f) / RATE
    if wave == "square":
        w = np.sign(np.sin(ph)) * 0.6
    elif wave == "saw":
        w = 2 * ((ph / (2 * np.pi)) % 1.0) - 1
    elif wave == "noise":
        w = np.random.uniform(-1, 1, n)
    else:
        w = np.sin(ph)
    return w * _env(n) * vol


def _seq(*parts):
    return np.concatenate(parts)


def _make(arr):
    arr = np.clip(arr, -1, 1)
    pcm = (arr * 32767).astype(np.int16)
    ch = pygame.mixer.get_init()[2]
    if ch == 2:
        pcm = np.column_stack([pcm, pcm])
    return pygame.sndarray.make_sound(np.ascontiguousarray(pcm))


def init(volume=0.6):
    global _ok
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(RATE, -16, 2, 512)
        defs = {
            "place": _tone(520, 0.07, "square", 0.25, slide=-200),
            "remove": _tone(300, 0.12, "saw", 0.25, slide=-180),
            "click": _tone(880, 0.04, "sine", 0.3),
            "error": _seq(_tone(200, 0.08, "square", 0.3), _tone(150, 0.12, "square", 0.3)),
            "coin": _seq(_tone(988, 0.06, "square", 0.25), _tone(1319, 0.18, "square", 0.25)),
            "research": _seq(_tone(660, 0.1), _tone(880, 0.1), _tone(1100, 0.25)),
            "fanfare": _seq(_tone(523, 0.12, "square", 0.3), _tone(659, 0.12, "square", 0.3),
                            _tone(784, 0.12, "square", 0.3), _tone(1047, 0.4, "square", 0.3)),
            "alarm": _seq(*[_tone(f, 0.16, "square", 0.35) for f in (950, 700, 950, 700)]),
            "fail": _tone(400, 0.35, "saw", 0.25, slide=-250),
        }
        for k, v in defs.items():
            _sounds[k] = _make(v)
        _ok = True
        set_volume(volume)
    except Exception as e:   # 사운드 장치가 없어도 게임은 돌아가야 함
        print("사운드 비활성화:", e)
        _ok = False


def set_volume(v):
    global _volume
    _volume = v
    for s in _sounds.values():
        s.set_volume(v)


def play(name):
    if _ok and name in _sounds and _volume > 0:
        _sounds[name].play()
