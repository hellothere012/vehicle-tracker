from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime

def get_car_listing_by_url(db: Session, url: str):
    return db.query(models.ScrapedData).filter(models.ScrapedData.url == url).first()

def create_car_listing(db: Session, listing: schemas.CarListingCreate):
    db_listing = models.ScrapedData(
        job_id=listing.job_id,
        platform=listing.platform,
        url=str(listing.url), # Ensure HttpUrl is converted to string
        title=listing.title,
        price=listing.price,
        mileage=listing.mileage,
        vin=listing.vin,
        image_urls=listing.image_urls, # Assuming image_urls is already a list of strings or compatible JSON
        raw_data=listing.raw_data,
        scraped_at=datetime.utcnow()
    )
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)
    return db_listing

def create_scrape_job(db: Session) -> models.ScrapeJob:
    db_job = models.ScrapeJob(timestamp=datetime.utcnow(), status="pending")
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def update_scrape_job_status(db: Session, job_id: int, status: str, results_count: int = 0, error_message: str = None):
    db_job = db.query(models.ScrapeJob).filter(models.ScrapeJob.id == job_id).first()
    if db_job:
        db_job.status = status
        db_job.results_count = results_count
        db_job.error_message = error_message
        db.commit()
        db.refresh(db_job)
    return db_job

def get_scrape_job(db: Session, job_id: int):
    return db.query(models.ScrapeJob).filter(models.ScrapeJob.id == job_id).first()

def get_all_scrape_jobs(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.ScrapeJob).order_by(models.ScrapeJob.timestamp.desc()).offset(skip).limit(limit).all()

def get_listings_for_job(db: Session, job_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.ScrapedData).filter(models.ScrapedData.job_id == job_id).offset(skip).limit(limit).all()
