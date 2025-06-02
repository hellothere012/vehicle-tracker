from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from database import CarListing, get_db, Session
from fastapi.middleware.cors import CORSMiddleware

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
