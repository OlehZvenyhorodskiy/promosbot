import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load local .env file into environment if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key, val = key.strip(), val.strip().strip("\"'")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass

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
    API_SECRET: str = os.getenv("API_SECRET", "")

settings = Settings()
