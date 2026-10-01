"""공장 자동화 타이쿤 — 실행 진입점.

python main.py                 일반 실행
python main.py --smoke 120     120프레임 실행 후 자동 종료 (실행 테스트용)
"""
import os
import sys
import traceback


def _show_error(msg):
    """콘솔 없는 exe에서도 오류를 볼 수 있도록 메시지 박스 + 로그 파일."""
    try:
        from src.paths import save_dir
        path = os.path.join(save_dir(), "crash.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(msg)
        msg += f"\n\n로그: {path}"
    except Exception:
        pass
    try:
        print(msg, file=sys.stderr)
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, msg[-1500:], "공장 자동화 타이쿤 - 오류", 0x10)
        except Exception:
            pass


def _safe_stdio():
    """한글 출력이 cp1252 같은 콘솔에서 UnicodeEncodeError를 내지 않도록."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def main():
    _safe_stdio()
    args = sys.argv[1:]
    smoke = 0
    shot = None
    if "--smoke" in args:
        i = args.index("--smoke")
        smoke = int(args[i + 1]) if i + 1 < len(args) else 120
    if "--screenshot" in args:
        shot = args[args.index("--screenshot") + 1]
    try:
        from src.app import App
        App(smoke_frames=smoke, screenshot=shot, autostart="--autostart" in args).run()
    except SystemExit:
        raise
    except Exception:
        _show_error("게임 실행 중 오류가 발생했습니다.\n\n" + traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
