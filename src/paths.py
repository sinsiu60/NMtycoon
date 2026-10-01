"""경로 처리. 개발 실행과 PyInstaller exe 실행 모두에서 동작하도록 한 곳에 모아둔다."""
import os
import sys

APP_DIR_NAME = "FactoryTycoon"


def base_dir():
    """data/, assets/ 가 들어있는 폴더."""
    if getattr(sys, "frozen", False):
        # PyInstaller: onedir 빌드는 _internal 폴더가 _MEIPASS
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts):
    return os.path.join(base_dir(), *parts)


def documents_dir():
    """사용자 '문서' 폴더. Windows는 OneDrive 리디렉션까지 고려해 셸 API로 조회."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5 (내 문서)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return buf.value
        except Exception:
            pass
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    return docs if os.path.isdir(docs) else os.path.expanduser("~")


def save_dir():
    """세이브 폴더 (환경변수 FACTORY_SAVE_DIR 로 덮어쓰기 가능 - 테스트용)."""
    d = os.environ.get("FACTORY_SAVE_DIR") or os.path.join(documents_dir(), APP_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d
