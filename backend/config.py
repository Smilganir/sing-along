import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

ENV = os.getenv("ENV", "development").lower()


def _normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_db_url(
    os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'singalong.db'}")
)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-token")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret-change-me")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "dev-password")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", str(7 * 24 * 3600)))
STATIC_DIR = Path(os.getenv("STATIC_DIR", "")).expanduser()

_cross_site_default = "true" if ENV == "prod" else "false"
SESSION_COOKIE_CROSS_SITE = os.getenv("SESSION_COOKIE_CROSS_SITE", _cross_site_default).lower() in {
    "1",
    "true",
    "yes",
}
SESSION_COOKIE_SAMESITE = "none" if SESSION_COOKIE_CROSS_SITE else "lax"
SESSION_COOKIE_SECURE = SESSION_COOKIE_CROSS_SITE or ENV == "prod"

_default_takeout = (
    DATA_DIR
    / "takeout"
    / "Takeout"
    / "YouTube and YouTube Music"
    / "history"
    / "watch-history.json"
)
TAKEOUT_HISTORY_PATH = Path(os.getenv("TAKEOUT_HISTORY_PATH", str(_default_takeout)))

_ytmusic_dir = BASE_DIR / "data" / "ytmusic"
YTMUSIC_AUTH_PATH = Path(os.getenv("YTMUSIC_AUTH_PATH", str(_ytmusic_dir / "browser.json")))
YTMUSIC_SNAPSHOT_PATH = Path(
    os.getenv("YTMUSIC_SNAPSHOT_PATH", str(_ytmusic_dir / "history_snapshot.json"))
)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5175,http://127.0.0.1:5175"
    ).split(",")
    if origin.strip()
]

_INSECURE_ADMIN_TOKENS = frozenset({"dev-token"})
_INSECURE_ADMIN_PASSWORDS = frozenset({"dev-password", "changeme"})
_INSECURE_SESSION_SECRETS = frozenset(
    {"dev-session-secret-change-me", "local-dev-session-secret-replace-in-production"}
)


def sqlite_db_path() -> Path | None:
    if not DATABASE_URL.startswith("sqlite"):
        return None
    raw = DATABASE_URL.removeprefix("sqlite:///")
    return Path(raw)


def validate_config() -> None:
    if ENV != "prod":
        return
    errors: list[str] = []
    if ADMIN_TOKEN in _INSECURE_ADMIN_TOKENS:
        errors.append("Set ADMIN_TOKEN to a strong secret (not dev-token)")
    if ADMIN_PASSWORD in _INSECURE_ADMIN_PASSWORDS:
        errors.append("Set ADMIN_PASSWORD to a strong secret (not dev-password/changeme)")
    if SESSION_SECRET in _INSECURE_SESSION_SECRETS:
        errors.append("Set SESSION_SECRET to a random string")
    if errors:
        print("Production configuration error:", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        raise SystemExit(1)


validate_config()