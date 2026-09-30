"""PagePilot configuration: paths, ports, app constants."""
import os

APP_NAME = "PagePilot"
APP_VERSION = "0.1.0"


def _data_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, APP_NAME)
    else:
        d = os.path.join(os.path.expanduser("~"), ".pagepilot")
    os.makedirs(d, exist_ok=True)
    return d


DATA_DIR = _data_dir()
DB_PATH = os.path.join(DATA_DIR, "pagepilot.db")
KEY_PATH = os.path.join(DATA_DIR, ".key")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
PROFILES_DIR = os.path.join(DATA_DIR, "profiles")  # per-account browser profiles
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(PROFILES_DIR, exist_ok=True)

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5057

# Posting safety defaults (human-like pacing)
DEFAULT_MIN_SPACING = 3
DEFAULT_MAX_SPACING = 10
DEFAULT_SWITCH_ON_ERRORS = 10
