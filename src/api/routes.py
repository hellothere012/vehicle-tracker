from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, exists, update
from datetime import datetime
import json
from typing import List
import logging

from src.database import get_db, AsyncSessionLocal
from src.models.vehicle import (
    VehicleListing,
    VehicleListingCreate,
    VehicleListingResponse,
    SearchFilters
)
from src.automation.browser_sim import AutoTraderScraper
from src.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

async def scrape_and_store_task(search_url: str, max_listings: int, source_site_name: str = "autotrader"):
    logger.info(f"Background task started: Scraping {source_site_name} URL: {search_url} for max {max_listings} listings.")
    created_count = 0
    updated_count = 0
    failed_count = 0
    processed_urls = set()
    if source_site_name.lower() == "autotrader":
        ScraperClass = AutoTraderScraper
    else:
        logger.error(f"Unsupported source site: {source_site_name}")
        return
    async with ScraperClass() as scraper:
        scraped_listings_pydantic = await scraper.scrape_listings(
            search_url=search_url,
            max_listings_to_fetch=max_listings
        )
    if not scraped_listings_pydantic:
        logger.info(f"No listings returned from {source_site_name} scraper for URL: {search_url}")
        return
    logger.info(f"{source_site_name} scraper returned {len(scraped_listings_pydantic)} listings. Processing for DB storage...")
    async with AsyncSessionLocal() as db_session:
        for listing_data in scraped_listings_pydantic:
            if not listing_data.listing_url:
                logger.warning("Scraped data missing listing_url, skipping.")
                failed_count += 1
                continue
            if listing_data.listing_url in processed_urls:
                logger.debug(f"URL {listing_data.listing_url} already processed in this run, skipping duplicate.")
                continue
            processed_urls.add(listing_data.listing_url)
            try:
                stmt = select(VehicleListing).where(VehicleListing.listing_url == listing_data.listing_url)
                result = await db_session.execute(stmt)
                existing_vehicle = result.scalar_one_or_none()
                features_json = json.dumps(listing_data.features) if listing_data.features else None
                if existing_vehicle:
                    logger.debug(f"Updating existing listing: {listing_data.listing_url} (ID: {existing_vehicle.id})")
                    update_values = {}
                    if listing_data.title and existing_vehicle.title != listing_data.title:
                        update_values['title'] = listing_data.title
                    if listing_data.price is not None and existing_vehicle.price != listing_data.price:
                        update_values['price'] = listing_data.price
                    if listing_data.mileage is not None and existing_vehicle.mileage != listing_data.mileage:
                        update_values['mileage'] = listing_data.mileage
                    if features_json and existing_vehicle.features != features_json:
                        update_values['features'] = features_json
                    if listing_data.photo_url and existing_vehicle.photo_url != listing_data.photo_url:
                        update_values['photo_url'] = listing_data.photo_url
                    if listing_data.location and existing_vehicle.location != listing_data.location:
                        update_values['location'] = listing_data.location
                    if listing_data.year and existing_vehicle.year != listing_data.year:
                        update_values['year'] = listing_data.year
                    if listing_data.make and existing_vehicle.make != listing_data.make:
                        update_values['make'] = listing_data.make
                    if listing_data.model and existing_vehicle.model != listing_data.model:
                        update_values['model'] = listing_data.model
                    if listing_data.trim and existing_vehicle.trim != listing_data.trim:
                        update_values['trim'] = listing_data.trim
                    update_values['is_active'] = True
                    update_values['last_scraped_at'] = datetime.utcnow()
                    if update_values:
                        stmt_update = update(VehicleListing).where(VehicleListing.id == existing_vehicle.id).values(**update_values)
                        await db_session.execute(stmt_update)
                        updated_count += 1
                else:
                    logger.debug(f"Adding new listing: {listing_data.listing_url}")
                    db_vehicle = VehicleListing(
                        listing_id_external=listing_data.listing_id_external,
                        title=listing_data.title,
                        year=listing_data.year,
                        make=listing_data.make,
                        model=listing_data.model,
                        trim=listing_data.trim,
                        price=listing_data.price,
                        mileage=listing_data.mileage,
                        listing_url=listing_data.listing_url,
                        photo_url=listing_data.photo_url,
                        features=features_json,
                        location=listing_data.location,
                        seller_type=listing_data.seller_type,
                        source_site=listing_data.source_site,
                        is_active=True,
                        last_scraped_at=datetime.utcnow()
                    )
                    db_session.add(db_vehicle)
                    created_count += 1
                await db_session.commit()
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to process/store listing {listing_data.listing_url}: {e}", exc_info=True)
                await db_session.rollback()
        logger.info(f"Background task for {source_site_name} finished. Created={created_count}, Updated={updated_count}, Failed={failed_count}")

@router.get("/", response_model=dict, include_in_schema=False)
async def api_v1_root_info():
    return {
        "message": "Vehicle Tracking API - V1",
        "active_endpoints": ["/vehicles", "/vehicles/search", "/vehicles/scrape", "/vehicles/{id}", "/vehicles/stats/summary"]
    }

@router.get("/vehicles/", response_model=List[VehicleListingResponse])
async def get_all_vehicles(
    skip: int = Query(0, ge=0),
    limit: int = Query(settings.MAX_LISTINGS_PER_SESSION, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    filters: SearchFilters = Depends(),
):
    query = select(VehicleListing)
    conditions = []
    if filters.is_active is not None:
        conditions.append(VehicleListing.is_active == filters.is_active)
    if filters.make:
        conditions.append(VehicleListing.make.ilike(f"%{filters.make}%"))
    if filters.model:
        conditions.append(VehicleListing.model.ilike(f"%{filters.model}%"))
    if filters.min_year:
        conditions.append(VehicleListing.year >= filters.min_year)
    if filters.max_year:
        conditions.append(VehicleListing.year <= filters.max_year)
    if filters.min_price:
        conditions.append(VehicleListing.price >= filters.min_price)
    if filters.max_price:
        conditions.append(VehicleListing.price <= filters.max_price)
    if filters.max_mileage:
        conditions.append(VehicleListing.mileage <= filters.max_mileage)
    if filters.location:
        conditions.append(VehicleListing.location.ilike(f"%{filters.location}%"))
    if filters.seller_type:
        conditions.append(VehicleListing.seller_type.ilike(f"%{filters.seller_type}%"))
    if filters.source_site:
        conditions.append(VehicleListing.source_site.ilike(f"%{filters.source_site}%"))
    if conditions:
        query = query.where(and_(*conditions))
    query = query.order_by(VehicleListing.last_scraped_at.desc(), VehicleListing.created_at.desc())
    result = await db.execute(query.offset(skip).limit(limit))
    vehicles = result.scalars().all()
    response_vehicles = []
    for vehicle_db_item in vehicles:
        response_vehicles.append(VehicleListingResponse.model_validate(vehicle_db_item))
    return response_vehicles

@router.get("/vehicles/{vehicle_id}", response_model=VehicleListingResponse)
async def get_vehicle_by_id_route(vehicle_id: int, db: AsyncSession = Depends(get_db)):
    query = select(VehicleListing).where(VehicleListing.id == vehicle_id)
    result = await db.execute(query)
    vehicle_db_item = result.scalar_one_or_none()
    if not vehicle_db_item:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return VehicleListingResponse.model_validate(vehicle_db_item)

@router.post("/vehicles/", response_model=VehicleListingResponse, status_code=201)
async def create_vehicle_listing_manual(
    vehicle_create_data: VehicleListingCreate,
    db: AsyncSession = Depends(get_db)
):
    stmt_exists = select(exists().where(VehicleListing.listing_url == vehicle_create_data.listing_url))
    url_exists = await db.scalar(stmt_exists)
    if url_exists:
        raise HTTPException(status_code=409, detail=f"Vehicle with URL {vehicle_create_data.listing_url} already exists.")
    features_json_str = json.dumps(vehicle_create_data.features) if vehicle_create_data.features else None
    db_vehicle_item = VehicleListing(
        **vehicle_create_data.model_dump(exclude={'features'}),
        features=features_json_str,
        is_active=True,
        last_scraped_at=datetime.utcnow()
    )
    db.add(db_vehicle_item)
    await db.commit()
    await db.refresh(db_vehicle_item)
    return VehicleListingResponse.model_validate(db_vehicle_item)

@router.post("/vehicles/scrape", status_code=202)
async def trigger_site_scrape(
    background_tasks: BackgroundTasks,
    site_name: str = Query("autotrader", description="Name of the site to scrape (e.g., 'autotrader')."),
    search_url: str = Query(..., description="Full search URL for the specified site."),
    max_listings: int = Query(settings.MAX_LISTINGS_PER_SESSION, description="Maximum listings to fetch from this scrape.", ge=1, le=100)
):
    logger.info(f"Received request to scrape {site_name} URL: {search_url} for max {max_listings} listings.")
    if site_name.lower() not in ["autotrader"]:
        raise HTTPException(status_code=400, detail=f"Scraping for site '{site_name}' is not supported.")
    background_tasks.add_task(scrape_and_store_task, search_url, max_listings, site_name)
    return {"message": f"{site_name.capitalize()} scraping task accepted and started in the background for URL: {search_url}"}

@router.delete("/vehicles/{vehicle_id}", status_code=200)
async def delete_vehicle_listing(vehicle_id: int, db: AsyncSession = Depends(get_db)):
    query = select(VehicleListing).where(VehicleListing.id == vehicle_id)
    result = await db.execute(query)
    vehicle_db_item = result.scalar_one_or_none()
    if not vehicle_db_item:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    await db.delete(vehicle_db_item)
    await db.commit()
    return {"message": "Vehicle deleted successfully"}

@router.get("/vehicles/stats/summary", response_model=dict)
async def get_vehicle_listing_stats(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func as sql_func
    make_query = select(VehicleListing.make, sql_func.count(VehicleListing.id).label('count'))\
                 .where(VehicleListing.make.isnot(None)).group_by(VehicleListing.make).order_by(sql_func.count(VehicleListing.id).desc())
    make_result = await db.execute(make_query)
    make_stats = [{"make": row[0], "count": row[1]} for row in make_result.all()]
    year_query = select(VehicleListing.year, sql_func.avg(VehicleListing.price).label('avg_price'), sql_func.count(VehicleListing.id).label('count'))\
                 .where(VehicleListing.year.isnot(None)).group_by(VehicleListing.year).order_by(VehicleListing.year.desc())
    year_result = await db.execute(year_query)
    year_stats = [{"year": row[0], "avg_price": round(row[1], 2) if row[1] else 0.0, "count": row[2]} for row in year_result.all()]
    total_query = select(sql_func.count(VehicleListing.id))
    total_count = await db.scalar(total_query) or 0
    active_query = select(sql_func.count(VehicleListing.id)).where(VehicleListing.is_active == True)
    active_count = await db.scalar(active_query) or 0
    return {
        "total_listings_in_db": total_count,
        "active_listings": active_count,
        "by_make": make_stats,
        "by_year_with_avg_price": year_stats
    }
