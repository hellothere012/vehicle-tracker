import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# This is useful for local development.
load_dotenv()

# Database Configuration
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/vehicle_tracker.db")

# Scraper Configuration
AUTOTRADER_URL: str = os.getenv("AUTOTRADER_URL", "https://www.autotrader.com/cars-for-sale/private-seller")
SCRAPE_TIMEOUT: int = int(os.getenv("SCRAPE_TIMEOUT", "120000"))  # Milliseconds
HEADLESS_BROWSER: bool = os.getenv("HEADLESS_BROWSER", "True").lower() == "true"

# API Configuration (if any specific ones are needed later)
# Example: API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
# Example: API_PORT: int = int(os.getenv("API_PORT", "8000"))

# Logging Configuration (can also be added here if more complex)
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Ensure critical URLs have a scheme for robustness
if not AUTOTRADER_URL.startswith(("http://", "https://")):
    # This print statement is for immediate feedback during startup/import.
    # In a pure library, side effects on import are sometimes discouraged,
    # but for an application's main config, it's often acceptable.
    print(f"Warning: AUTOTRADER_URL ('{AUTOTRADER_URL}') did not have a scheme, prepended https://.")
    AUTOTRADER_URL = "https://" + AUTOTRADER_URL
    print(f"Corrected AUTOTRADER_URL: {AUTOTRADER_URL}")


# Example of how to handle SQLite connect_args based on config
DB_CONNECT_ARGS: dict = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
