import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

from src.database import create_db_tables
from src.api.routes import router as api_v1_router
from src.config import settings
from src.automation.browser_sim import run_autotrader_scraper_example_standalone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("\ud83d\ude80 Starting Educational Vehicle Tracker API...")
    await create_db_tables()
    logger.info("\ud83d\udcca Database tables checked/created.")
    yield
    logger.info("\ud83d\udd1b Shutting down Educational Vehicle Tracker API.")

app = FastAPI(
    title="Educational Vehicle Tracker",
    description="An educational system for learning web automation and data pipeline architecture, now with real scraping.",
    version="1.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")

@app.get("/", include_in_schema=False)
async def root_redirect_to_docs():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

@app.get("/health", summary="Health Check")
async def health_check():
    return {"status": "healthy", "service": "vehicle-tracker-api", "timestamp": datetime.utcnow()}

async def run_standalone_scrape_cli():
    logger.info("\ud83c\udf3d Running Standalone AutoTrader Scraper Example from CLI")
    print("=" * 40)
    try:
        await run_autotrader_scraper_example_standalone()
        logger.info("\u2705 Standalone scraper example completed successfully!")
    except Exception as e:
        logger.error(f"\u274c Standalone scraper example failed: {e}", exc_info=True)

if __name__ == "__main__":
    import sys
    print_startup_message = True
    if len(sys.argv) > 1:
        if sys.argv[1] == "scrape_test":
            print_startup_message = False
            asyncio.run(run_standalone_scrape_cli())
        elif sys.argv[1] == "create_tables":
            print_startup_message = False
            asyncio.run(create_db_tables())
            logger.info("Database tables creation process finished.")
        else:
            logger.warning(f"Unknown command: {sys.argv[1]}")
            print("\ud83d\udd0d Usage: python main.py [scrape_test | create_tables]")
    if print_startup_message:
        logger.info("\ud83c\udf93 Educational Vehicle Tracking System - API Server Mode")
        print("=" * 50)
        logger.info(f"API Host: {settings.API_HOST}")
        logger.info(f"API Port: {settings.API_PORT}")
        logger.info(f"Database: {settings.DATABASE_URL}")
        logger.info(f"Max Listings per Session (Scrape): {settings.MAX_LISTINGS_PER_SESSION}")
        logger.info(f"Playwright Headless: {settings.HEADLESS}")
        print("=" * 50)
        uvicorn.run(
            "main:app",
            host=settings.API_HOST,
            port=settings.API_PORT,
            reload=True,
            log_level="info"
        )
