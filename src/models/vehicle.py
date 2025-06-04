from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

Base = declarative_base()

class VehicleListing(Base):
    __tablename__ = "vehicle_listings"

    id = Column(Integer, primary_key=True, index=True)
    listing_id_external = Column(String, index=True, unique=False, nullable=True)
    title = Column(String, nullable=False)
    year = Column(Integer, index=True, nullable=True)
    make = Column(String, index=True, nullable=True)
    model = Column(String, index=True, nullable=True)
    trim = Column(String, nullable=True)
    price = Column(Float, index=True, nullable=True)
    mileage = Column(Integer, index=True, nullable=True)
    listing_url = Column(Text, unique=True, nullable=False, index=True)
    photo_url = Column(Text, nullable=True)
    features = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    seller_type = Column(String, default="private", nullable=True)
    source_site = Column(String, default="autotrader", nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_scraped_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, index=True)

class VehicleListingCreate(BaseModel):
    listing_id_external: Optional[str] = None
    title: str
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    price: Optional[float] = None
    mileage: Optional[int] = None
    listing_url: str
    photo_url: Optional[str] = None
    features: Optional[List[str]] = Field(default_factory=list)
    location: Optional[str] = None
    seller_type: Optional[str] = "private"
    source_site: Optional[str] = "autotrader"

class VehicleListingResponse(BaseModel):
    id: int
    listing_id_external: Optional[str] = None
    title: str
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    price: Optional[float] = None
    mileage: Optional[int] = None
    listing_url: str
    photo_url: Optional[str] = None
    features: Optional[List[str]] = Field(default_factory=list)
    location: Optional[str] = None
    seller_type: Optional[str] = None
    source_site: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_scraped_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

class SearchFilters(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    max_mileage: Optional[int] = None
    location: Optional[str] = None
    seller_type: Optional[str] = None
    source_site: Optional[str] = None
    is_active: Optional[bool] = True
