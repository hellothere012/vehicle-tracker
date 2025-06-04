import logging
# import os # No longer needed for getenv in background task
import asyncio
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from database import CarListing, get_db, Session, SessionLocal
from scraper import scrape_autotrader_and_update_db
from fastapi.middleware.cors import CORSMiddleware
from config import AUTOTRADER_URL, HEADLESS, SCRAPE_TIMEOUT, LOG_LEVEL # Import from config

# Configure basic logging using LOG_LEVEL from config
# Ensure this is called only once. If FastAPI/Uvicorn also configures logging,
# this might need adjustment or to be handled by the logger instance directly.
# For now, assume this is the primary logging config.
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s', force=True)
# Added force=True to ensure this config takes precedence if uvicorn also tries to set basicConfig.

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CarListingRaw(BaseModel):
    platform: str
    extracted_at: datetime
    source_url: str
    data_points: Dict

@app.post("/api/v1/listings/ingest")
async def ingest_listing(payload: CarListingRaw, db: Session = Depends(get_db)):
    listing = CarListing(
        platform=payload.platform,
        extracted_at=payload.extracted_at,
        source_url=payload.source_url,
        data_points=payload.data_points
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return {"status": "saved", "listing_id": listing.id}

@app.get("/")
def read_root():
    return {"message": "🚗 Car Tracker API is running!"}

# Global variable to store scraping status
scrape_status = {
    "last_run_time": None,
    "status": "idle", # States: idle, running, success, error
    "message": "",
    "added": 0,
    "updated": 0,
    "scraped_count": 0
}

# Background task wrapper
async def _background_scraper_task_wrapper():
    global scrape_status
    db_task_session: Session = SessionLocal()
    logging.info("Background scraper task started.")
    scrape_status["status"] = "running"
    scrape_status["message"] = "Scraping in progress..."
    scrape_status["last_run_time"] = datetime.utcnow().isoformat()
    scrape_status["added"] = 0 # Reset counts for current run
    scrape_status["updated"] = 0
    scrape_status["scraped_count"] = 0

    try:
        # Use imported config values
        # autotrader_url = os.getenv("AUTOTRADER_URL", "https://www.autotrader.com/cars-for-sale/private-seller")
        # headless_str = os.getenv("HEADLESS", "True")
        # headless = headless_str.lower() == "true"
        # scrape_timeout_str = os.getenv("SCRAPE_TIMEOUT", "120000")
        # try:
        #     scrape_timeout = int(scrape_timeout_str)
        # except ValueError:
        #     logging.warning(f"Invalid SCRAPE_TIMEOUT value: {scrape_timeout_str}. Defaulting to 120000ms.")
        #     scrape_timeout = 120000

        logging.info(f"Background task using URL: {AUTOTRADER_URL}, Headless: {HEADLESS}, Timeout: {SCRAPE_TIMEOUT}ms")

        result = await scrape_autotrader_and_update_db(
            db=db_task_session,
            autotrader_url=AUTOTRADER_URL,
            headless=HEADLESS,
            scrape_timeout=SCRAPE_TIMEOUT
        )

        if result.get("status") == "success":
            scrape_status["status"] = "success"
            scrape_status["message"] = "Scraping completed successfully."
            scrape_status["added"] = result.get("added", 0)
            scrape_status["updated"] = result.get("updated", 0)
            scrape_status["scraped_count"] = result.get("scraped_count", 0)
        else:
            scrape_status["status"] = "error"
            scrape_status["message"] = result.get("message", "Scraping failed with an unknown error.")

        logging.info(f"Background scraper task completed: {result}")

    except Exception as e:
        logging.error(f"Error in background scraper task: {e}", exc_info=True)
        scrape_status["status"] = "error"
        scrape_status["message"] = str(e)
    finally:
        db_task_session.close()
        logging.info("Background scraper DB session closed.")

@app.post("/api/v1/scrape/autotrader")
async def trigger_autotrader_scrape(background_tasks: BackgroundTasks):
    if scrape_status["status"] == "running":
        return {"message": "AutoTrader scraping job is already running."}
    background_tasks.add_task(_background_scraper_task_wrapper)
    return {"message": "AutoTrader scraping job started in the background."}

@app.get("/api/v1/scrape/status")
async def get_scrape_status():
    return scrape_status
