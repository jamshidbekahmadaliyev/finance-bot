import os
from dotenv import load_dotenv


load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = _optional_env(name, "")
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


TOKEN = _require_env("BOT_TOKEN")

DB_HOST = _require_env("DB_HOST")
DB_PORT = _require_env("DB_PORT")
DB_NAME = _require_env("DB_NAME")
DB_USER = _require_env("DB_USER")
DB_PASSWORD = _require_env("DB_PASSWORD")

USE_WEBHOOK = _bool_env("USE_WEBHOOK", False)
WEBHOOK_URL = _optional_env("WEBHOOK_URL", "")
WEBHOOK_PATH = _optional_env("WEBHOOK_PATH", "/telegram")
WEBHOOK_SECRET = _optional_env("WEBHOOK_SECRET", "")
PORT = int(_optional_env("PORT", "8080"))
