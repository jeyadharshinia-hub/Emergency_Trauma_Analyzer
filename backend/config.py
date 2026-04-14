import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "eta-dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:root@127.0.0.1:3306/eta_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    USE_MOCK_AI = _to_bool(os.getenv("USE_MOCK_AI"), default=False)
    AI_FAILOVER_TO_SAFE_MOCK = _to_bool(os.getenv("AI_FAILOVER_TO_SAFE_MOCK"), default=False)

    SESSION_COOKIE_NAME = "eta_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    UPLOAD_DIR = BASE_DIR / "static" / "uploads"
    REPORT_DIR = BASE_DIR / "static" / "reports"
    FONT_PATH = BASE_DIR / "assets" / "NotoSansTamil-Regular.ttf"
