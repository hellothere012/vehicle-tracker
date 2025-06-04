import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./default_vehicle_data.db")
    HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"
    BROWSER_TIMEOUT: int = int(os.getenv("BROWSER_TIMEOUT", "60000"))
    PAGE_DELAY: int = int(os.getenv("PAGE_DELAY", "5000"))
    MIN_DELAY_BETWEEN_ACTIONS: float = float(os.getenv("MIN_DELAY_BETWEEN_ACTIONS", "2.5"))
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    MAX_LISTINGS_PER_SESSION: int = int(os.getenv("MAX_LISTINGS_PER_SESSION", "25"))

    # Proxy configuration
    PROXY_SERVER: str | None = os.getenv("PROXY_SERVER")
    PROXY_USERNAME: str | None = os.getenv("PROXY_USERNAME")
    PROXY_PASSWORD: str | None = os.getenv("PROXY_PASSWORD")

settings = Settings()
