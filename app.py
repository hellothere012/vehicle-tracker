import os
from fastapi import FastAPI, Depends, HTTPException # Added HTTPException
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from database import CarListing, get_db, Session
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError # Added
import logging # Added for logger

# To run with Uvicorn for production (e.g., in render.yaml):
# uvicorn app:app --host 0.0.0.0 --port $PORT

# Basic logging configuration (similar to scraper.py)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Added logger instance

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
    # Check for existing listing
    existing_listing = db.query(CarListing).filter(CarListing.source_url == payload.source_url).first()
    if existing_listing:
        # Consider returning a 200 or 202 status if this is not considered an error,
        # or 409 Conflict if it is.
        # For now, let's inform it's a duplicate and potentially an update could happen here if desired.
        return {"status": "duplicate", "message": "Listing with this source_url already exists.", "listing_id": existing_listing.id}

    listing = CarListing(
        platform=payload.platform,
        extracted_at=payload.extracted_at,
        source_url=payload.source_url,
        data_points=payload.data_points
    )
    db.add(listing)

    try:
        db.commit()
        db.refresh(listing)
        return {"status": "saved", "listing_id": listing.id}
    except IntegrityError:
        db.rollback()
        # This might happen if the pre-check fails due to a race condition or another unique constraint violation
        # Or if the unique=True on source_url is the primary de-duplication mechanism being hit.
        # Check again to be sure it was a source_url conflict
        conflicting_listing = db.query(CarListing).filter(CarListing.source_url == payload.source_url).first()
        if conflicting_listing:
             # It's good practice to return a specific status code for conflict, e.g., 409
             # However, to match the provided example's structure closely:
             return {"status": "error", "message": "IntegrityError: Listing with this source_url likely already exists (race condition or direct hit on DB constraint).", "listing_id": conflicting_listing.id}
        # If it's another IntegrityError (e.g. other unique constraints if any were added)
        logger.error(f"IntegrityError encountered for source_url: {payload.source_url} that was not a duplicate source_url.") # Requires logger to be defined
        raise HTTPException(status_code=409, detail="IntegrityError: Could not save listing due to a data conflict not related to source_url duplication.")


@app.get("/")
def read_root():
    return {"message": "🚗 Car Tracker API is running!"}

if __name__ == "__main__":
    import uvicorn
    # Default to 8000 if PORT not set, which is common for local development.
    # Render will set the PORT environment variable.
    port = int(os.environ.get("PORT", 8000))
    # Need to ensure logger is available if used in IntegrityError block, or remove that specific log line
    # For now, assuming logger might be set up globally or remove specific line.
    # import logging # Would be needed if logger.error is used and not defined globally
    # logger = logging.getLogger(__name__) # Example setup
    uvicorn.run(app, host="0.0.0.0", port=port)
