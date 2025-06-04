from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime

class CarListingBase(BaseModel):
    url: HttpUrl
    title: Optional[str] = None
    price: Optional[str] = None # Keep as string to handle variations
    mileage: Optional[str] = None # Keep as string
    vin: Optional[str] = None
    image_urls: Optional[List[HttpUrl]] = []
    raw_data: Optional[Dict[str, Any]] = {} # For any other unstructured data

class CarListingCreate(CarListingBase):
    platform: str
    job_id: int

class CarListing(CarListingBase):
    id: int
    platform: str
    job_id: int
    scraped_at: datetime

    class Config:
        orm_mode = True

class ScrapeJobBase(BaseModel):
    pass

class ScrapeJobCreate(ScrapeJobBase):
    pass

class ScrapeJob(ScrapeJobBase):
    id: int
    timestamp: datetime
    status: str
    results_count: int = 0
    error_message: Optional[str] = None

    class Config:
        orm_mode = True
