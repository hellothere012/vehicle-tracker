from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from . import models, schemas
from datetime import datetime

async def get_car_listing_by_url(db: AsyncSession, url: str):
    result = await db.execute(
        select(models.ScrapedData).where(models.ScrapedData.url == url)
    )
    return result.scalars().first()

async def create_car_listing(db: AsyncSession, listing: schemas.CarListingCreate):
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
    await db.commit()
    await db.refresh(db_listing)
    return db_listing

async def create_scrape_job(db: AsyncSession) -> models.ScrapeJob:
    db_job = models.ScrapeJob(timestamp=datetime.utcnow(), status="pending")
    db.add(db_job)
    await db.commit()
    await db.refresh(db_job)
    return db_job

async def update_scrape_job_status(db: AsyncSession, job_id: int, status: str, results_count: int = 0, error_message: str = None):
    result = await db.execute(
        select(models.ScrapeJob).where(models.ScrapeJob.id == job_id)
    )
    db_job = result.scalars().first()
    if db_job:
        db_job.status = status
        db_job.results_count = results_count
        db_job.error_message = error_message
        await db.commit()
        await db.refresh(db_job)
    return db_job

async def get_scrape_job(db: AsyncSession, job_id: int):
    result = await db.execute(
        select(models.ScrapeJob).where(models.ScrapeJob.id == job_id)
    )
    return result.scalars().first()

async def get_all_scrape_jobs(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(models.ScrapeJob).order_by(models.ScrapeJob.timestamp.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_listings_for_job(db: AsyncSession, job_id: int, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(models.ScrapedData).where(models.ScrapedData.job_id == job_id).offset(skip).limit(limit)
    )
    return result.scalars().all()
