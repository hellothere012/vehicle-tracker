import logging
import os
import asyncio
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from . import crud, models, schemas, scraper
from .database import AsyncSessionLocal, engine, get_db, create_tables

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="AutoTrader Scraper API", version="1.0.0")

@app.on_event("startup")
async def on_startup() -> None:
    await create_tables()

# get_db imported from .database

# Global variable to store scraping status (simple approach)
scrape_status = {
    "job_id": None,
    "status": "idle", # States: idle, pending, running, completed, failed
    "message": "No scraping job initiated yet.",
    "last_run_time": None,
    "duration_seconds": None,
    "results_count": 0,
    "error_message": None
}

async def run_scraping_task(job_id: int, autotrader_url: str, headless: bool, scrape_timeout: int):
    """Run scraping in the background using its own DB session."""
    global scrape_status
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"Background task started for job_id: {job_id}")
            await crud.update_scrape_job_status(db, job_id, status="running")
            scrape_status.update({
                "job_id": job_id,
                "status": "running",
                "message": f"Scraping from {autotrader_url}...",
                "last_run_time": datetime.utcnow().isoformat(),
                "duration_seconds": None,
                "results_count": 0,
                "error_message": None,
            })

            start_time = datetime.utcnow()

            scraped_data_list = await scraper.scrape_autotrader_data(
                autotrader_url=autotrader_url,
                headless=headless,
                timeout=scrape_timeout,
            )

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            scrape_status["duration_seconds"] = round(duration, 2)

            added_count = 0
            updated_count = 0

            if not scraped_data_list:
                logger.info(f"No listings found for job_id: {job_id}")
                await crud.update_scrape_job_status(db, job_id, status="completed", results_count=0)
                scrape_status.update({
                    "status": "completed",
                    "message": "Scraping completed. No new listings found or page was inaccessible.",
                    "results_count": 0,
                })
                return

            for item_data in scraped_data_list:
                listing_create = schemas.CarListingCreate(
                    job_id=job_id,
                    platform=item_data.get("source_name", "autotrader"),
                    url=item_data.get("listing_url"),
                    title=item_data.get("title"),
                    price=item_data.get("price"),
                    mileage=item_data.get("mileage"),
                    vin=item_data.get("vin"),
                    image_urls=item_data.get("image_urls", []),
                    raw_data=item_data.get("data_points", {}),
                )

                existing_listing = await crud.get_car_listing_by_url(db, str(listing_create.url))
                if existing_listing:
                    updated_count += 1
                else:
                    await crud.create_car_listing(db=db, listing=listing_create)
                    added_count += 1

            await crud.update_scrape_job_status(db, job_id, status="completed", results_count=added_count)
            scrape_status.update({
                "status": "completed",
                "message": f"Scraping finished. Added: {added_count}, Updated: {updated_count} (placeholder).",
                "results_count": added_count + updated_count,
            })
            logger.info(
                f"Background task for job_id: {job_id} completed. Added: {added_count}, Updated: {updated_count}"
            )

        except Exception as e:
            logger.error(
                f"Error in background scraper task for job_id {job_id}: {e}",
                exc_info=True,
            )
            await crud.update_scrape_job_status(db, job_id, status="failed", error_message=str(e))
            scrape_status.update({
                "status": "failed",
                "message": f"Error during scraping: {str(e)}",
                "error_message": str(e),
            })
        finally:
            logger.info(f"DB session closed for job_id: {job_id}")


@app.post("/scrape/", response_model=schemas.ScrapeJob, status_code=202)
async def trigger_scrape(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Triggers a new scraping job for Autotrader.
    """
    global scrape_status
    if scrape_status.get("status") == "running":
        raise HTTPException(status_code=409, detail="A scraping job is already in progress.")

    autotrader_url = os.getenv("AUTOTRADER_URL", "https://www.autotrader.com/cars-for-sale/all-cars/cars-under-10000") # Default to a common search if not set
    headless_str = os.getenv("HEADLESS", "True")
    headless = headless_str.lower() == "true"
    scrape_timeout_str = os.getenv("SCRAPE_TIMEOUT", "120000")

    try:
        scrape_timeout = int(scrape_timeout_str)
    except ValueError:
        scrape_timeout = 120000 # Default timeout if parsing fails
        logger.warning(f"Invalid SCRAPE_TIMEOUT value: {scrape_timeout_str}. Using default {scrape_timeout}ms.")

    job = await crud.create_scrape_job(db)
    scrape_status.update({
        "job_id": job.id,
        "status": "pending",
        "message": f"Scraping job {job.id} initiated for URL: {autotrader_url}",
        "last_run_time": job.timestamp.isoformat(),
        "duration_seconds": None,
        "results_count": 0,
        "error_message": None
    })

    # Pass job_id to the background task
    background_tasks.add_task(run_scraping_task, job.id, autotrader_url, headless, scrape_timeout)

    logger.info(f"Scraping job {job.id} queued for URL: {autotrader_url}")
    return job

@app.post("/api/v1/listings/ingest", response_model=schemas.CarListing, status_code=201)
async def ingest_listing(payload: schemas.CarListingCreate, db: AsyncSession = Depends(get_db)):
    """
    Ingests a new car listing into the database.
    This endpoint is useful for manually adding or testing data.
    """
    # Check if listing with this URL already exists to prevent duplicates,
    # though the database constraint should also handle this.
    db_listing = await crud.get_car_listing_by_url(db, url=str(payload.url))
    if db_listing:
        raise HTTPException(status_code=400, detail="Listing with this URL already exists.")

    # The job_id in CarListingCreate might be problematic if this is a direct ingest
    # not tied to a specific scrape job. For now, we'll assume it's provided or
    # we could adjust the schema/logic if direct ingestion shouldn't have a job_id.
    # For testing, we might need to create a dummy job or adjust schema.
    # Let's assume for now a valid job_id is provided or handle it if not.
    if not payload.job_id:
        # Create a dummy job or handle as per requirements for listings not tied to a job
        # For simplicity, let's assume job_id is optional in the schema for this use case
        # or a default/placeholder job_id is used.
        # For this test, the payload includes job_id, so we'll proceed.
        # If CarListingCreate schema requires job_id, this endpoint needs to handle it.
        # For now, let's assume it's provided in the payload.
        pass

    try:
        created_listing = await crud.create_car_listing(db=db, listing=payload)
        return created_listing
    except Exception as e:
        logger.error(f"Error ingesting listing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/scrape/status", response_model=schemas.ScrapeJob) # Using ScrapeJob schema for better structure
async def get_current_scrape_status(db: AsyncSession = Depends(get_db)):
    """
    Returns the status of the current or last scraping job.
    """
    global scrape_status
    if scrape_status.get("job_id"):
        job = await crud.get_scrape_job(db, scrape_status["job_id"])
        if job:
            # Update status from DB if available, otherwise use in-memory for simplicity
            # A more robust system might always fetch from DB or use a proper job queue status
            return job
    return scrape_status # Fallback to in-memory status if job not found or not started

@app.get("/scrape/jobs/", response_model=List[schemas.ScrapeJob])
async def read_jobs(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all scrape jobs.
    """
    jobs = await crud.get_all_scrape_jobs(db, skip=skip, limit=limit)
    return jobs

@app.get("/scrape/jobs/{job_id}/results", response_model=List[schemas.CarListing])
async def read_job_results(job_id: int, skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """
    Retrieve results for a specific scrape job.
    """
    job = await crud.get_scrape_job(db, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    listings = await crud.get_listings_for_job(db, job_id=job_id, skip=skip, limit=limit)
    return listings

@app.get("/")
async def read_root():
    return {"message": "AutoTrader Scraper API is running!"}

# This is for local development if you run `python app/main.py`
# Uvicorn will be started by Procfile in production environments like Heroku
if __name__ == "__main__":
    # Ensure tables are created before starting the app if they don't exist
    # This is useful for local development but might be handled differently in production
    from .database import create_tables
    asyncio.run(create_tables())

    # Get port from environment variable or default to 8000
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

# Remove the old main.py content if it exists in the root directory
# This is now handled by app/main.py
# Ensure Procfile points to app.main:app or similar based on your directory structure
# e.g., web: uvicorn app.main:app --host=0.0.0.0 --port=${PORT:-8000}
# (Assuming app.py is moved to app/main.py)
# If app.py remains in root, then Procfile is fine.

# The `models.Base.metadata.create_all(bind=engine)` should ideally be called once,
# perhaps in main.py or a startup script, not every time database.py is imported.
# For simplicity in this single-file app structure, it's often put there.
# If app.py is the main entry point for uvicorn, it's a good place.
# For Render, buildCommand in render.yaml can also handle migrations/table creation.

# Let's ensure the imports are correct considering the file structure
# If main.py is in root and imports from app/, it should be `from app import crud, models, schemas, scraper`
# If this file is app/main.py, then `from . import crud, models, schemas, scraper` is correct.
# The prompt implies this file is app/main.py.
