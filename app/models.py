from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class ScrapeResult(Base):
    __tablename__ = "scrape_results"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    title = Column(String)
    price = Column(String, nullable=True) # Store as string to handle variations like 'Contact Seller'
    mileage = Column(String, nullable=True) # Store as string to handle non-numeric values
    vin = Column(String, nullable=True, unique=True)
    images = Column(JSON, nullable=True) # Store list of image URLs
    scraped_at = Column(DateTime)
    details = Column(JSON, nullable=True) # Store other details as JSON

class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending") # e.g., pending, running, completed, failed
    results_count = Column(Integer, default=0)
    error_message = Column(String, nullable=True)

class ScrapedData(Base):
    __tablename__ = "scraped_data"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("scrape_jobs.id"))
    platform = Column(String) # e.g., 'autotrader', 'cars.com'
    url = Column(String, unique=True, index=True)
    title = Column(String, nullable=True)
    price = Column(String, nullable=True)
    mileage = Column(String, nullable=True)
    vin = Column(String, nullable=True, index=True)
    image_urls = Column(JSON, nullable=True) # List of image URLs
    raw_data = Column(JSON, nullable=True) # Full raw data if needed
    scraped_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("ScrapeJob")
