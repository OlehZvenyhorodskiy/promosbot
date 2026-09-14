import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseModel):
    # Secrets must be injected through the environment or a managed secret.
    # Keep local tests importable without requiring a real Telegram token.
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    PORT: int = int(os.getenv("PORT", "8080"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "promos.db"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))
    DIGEST_CHECK_INTERVAL_MINUTES: int = int(os.getenv("DIGEST_CHECK_INTERVAL_MINUTES", "15"))
    ALERT_BATCH_INTERVAL_MINUTES: int = int(os.getenv("ALERT_BATCH_INTERVAL_MINUTES", "10"))
    KEEP_ALIVE_URL: str = os.getenv("KEEP_ALIVE_URL", "")

settings = Settings()
