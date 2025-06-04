import asyncio
import logging
import os
import datetime # Keep for now, might be used in data processing
from playwright.async_api import async_playwright

# Assuming database.py is in the same directory or accessible in PYTHONPATH
from database import get_db, CarListing, SessionLocal # Added SessionLocal for main example
from sqlalchemy.orm import Session
from datetime import datetime # Ensure datetime is imported directly

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from stealth_utils import apply_stealth_js # Import new stealth utility
# from playwright_stealth import stealth_async # Commenting out old stealth

class AutoTraderScraper:
    """Scraper for AutoTrader private party listings using Playwright."""

    def __init__(self, source_name: str = "autotrader"):
        """
        Initializes the AutoTraderScraper.
        Args:
            source_name (str): Name of the source platform.
        """
        self.source_name = source_name
        # Potentially load other configs from a config file or env vars here
        # For example: self.base_url = "https://www.autotrader.com/cars-for-sale/private-seller"

    async def get_private_listings(self, autotrader_url: str, headless: bool, timeout: int = 120000) -> list[dict]:
        """
        Scrapes private party listings from AutoTrader using Playwright.

        Args:
            autotrader_url (str): The starting URL for scraping AutoTrader private listings.
            headless (bool): Whether to run the browser in headless mode.
            timeout (int): Maximum time in milliseconds for page operations.

        Returns:
            list[dict]: A list of dictionaries, where each dictionary represents a scraped vehicle listing.
        """
        listings_data = []
        browser = None
        
        launch_options = {
            "headless": headless,
            "args": [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-position=0,0',
                '--ignore-certificate-errors',
                '--ignore-certificate-errors-spki-list',
                # '--user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"' # User agent is set in context
                '--disable-gpu' # Already there but keep
            ],
            # "channel": "chrome" # This might require full Chrome install, trying without first to see if args help
        }
        
        # Try with 'msedge' or 'chrome' if default chromium fails and they are available
        # For now, stick to chromium and args. If 'channel' is needed, it's a bigger setup change.

        async with async_playwright() as p:
            try:
                # browser = await p.chromium.launch(**launch_options) # Default chromium
                # Let's try specifying channel, assuming it might use a locally installed Chrome if available, or a Playwright-managed one.
                # This is a common suggestion if the default Playwright Chromium build is too easily detected.
                # If "chrome" channel is not found by Playwright, it will error.
                try:
                    browser = await p.chromium.launch(
                        **launch_options,
                        channel="chrome" # Attempt to use a branded Chrome build
                    )
                    logging.info("Attempting to launch with channel='chrome'")
                except Exception as e_channel:
                    logging.warning(f"Failed to launch with channel='chrome' ({e_channel}). Falling back to default Playwright Chromium.")
                    # Remove channel from launch_options if it failed
                    launch_options_no_channel = launch_options.copy()
                    if "channel" in launch_options_no_channel: # Should not be needed based on above structure but good practice
                        del launch_options_no_channel["channel"]
                    browser = await p.chromium.launch(**launch_options_no_channel)
                    logging.info("Launched with default Playwright Chromium.")


                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36', # A fairly common user agent
                    java_script_enabled=True,
                )
                context.set_default_navigation_timeout(timeout)
                context.set_default_timeout(timeout)
                
                page = await context.new_page()
                await page.set_viewport_size({"width": 1920, "height": 1080})

                # Apply custom JS stealth
                await apply_stealth_js(page)
                
                logging.info(f"Navigating to {autotrader_url}")
                await page.goto(autotrader_url, wait_until="domcontentloaded", timeout=timeout) # Reverted to domcontentloaded
                
                title = await page.title()
                logging.info(f"Page title: {title}")

                if "unavailable" in title.lower() or "block" in title.lower() or "access denied" in title.lower():
                    logging.critical(f"Failed to load AutoTrader listings page. Blocked by website. Title: {title}")
                    await browser.close() # Ensure browser is closed before returning
                    return []

                # Using speculative selectors for AutoTrader
                # Main container for listings: 'div[data-qaid="cntnr-lstng-main"]' (this might be too broad or incorrect)
                # A more specific item selector might be needed, e.g., an article or a div with a specific class.
                # For now, let's assume individual listing cards can be found with a selector like:
                # "div.inventory-listing" or "div[data-cmp='inventoryListing']" - these are common patterns.
                # The provided example 'div[data-qaid="cntnr-lstng-main"]' seems like it might be a single container FOR ALL listings.
                # Let's try a more specific (but still guessed) selector for individual listing items.
                # A common pattern is items within a list or grid. Let's try to find items:
                # This selector is a **GUESS** based on common AutoTrader structures.
                listing_item_selector = "div[data-cmp='inventoryListing']" # GUESS
                
                # Fallback if the primary guess doesn't work, try another common pattern
                # listing_item_selector_fallback = "div.inventory-listing.new-listing.stub" # Another GUESS

                # await page.wait_for_selector(listing_item_selector, timeout=15000) # Wait for items to appear
                
                listing_containers = await page.query_selector_all(listing_item_selector)
                
                # if not listing_containers:
                #     logging.info(f"No listings found with primary selector '{listing_item_selector}'. Trying fallback...")
                #     listing_containers = await page.query_selector_all(listing_item_selector_fallback)

                logging.info(f"Found {len(listing_containers)} potential listing containers using selector '{listing_item_selector}'.")

                processed_count = 0
                # first_container_processed_for_html_dump = False # REMOVE HTML DUMP FLAG
                for i, container in enumerate(listing_containers):
                    url_path = None
                    title_text = "N/A" # Default to N/A
                    price_text = "N/A" # Default to N/A
                    mileage_text = "N/A" # Default to N/A (as it's not reliably on card)
                    listing_url = None

                    try:
                        logging.debug(f"Processing container {i+1}/{len(listing_containers)}")

                        # Attempt to get Title
                        title_el = await container.query_selector("h2[data-cmp='subheading']") # Updated selector from HTML dump
                        if title_el:
                            raw_title_text = await title_el.inner_text()
                            title_text = raw_title_text.strip() if raw_title_text else "N/A"

                            # Attempt to get URL from parent <a> of title_el
                            # Playwright's query_selector does not directly support xpath like "ancestor::a".
                            # A common structure is <a><h3>...</h3></a> or <a><h2>...</h2></a>
                            # We can try to find 'a' that contains this h2, or assume the 'a[data-cmp="link"]' is the one.

                            # Let's use the a[data-cmp="link"] which was identified as containing the title h2
                            parent_link_el = await container.query_selector("a[data-cmp='link']")
                            if parent_link_el:
                                url_path = await parent_link_el.get_attribute("href")
                            else: # Fallback if the above structure isn't found
                                logging.warning(f"Could not find parent a[data-cmp='link'] for title in listing {i+1}")
                        else:
                            logging.warning(f"Title not found with h2[data-cmp='subheading'] for listing {i+1}.")

                        # Fallback or alternative for URL if not found via title's parent link
                        if not url_path:
                            url_el_alt = await container.query_selector("a[data-cmp='relLnk']") # Keep this fallback
                            if url_el_alt:
                                url_path = await url_el_alt.get_attribute("href")

                        if not url_path: # Last resort for URL
                            first_a = await container.query_selector("a[href]") # Broadest fallback
                            if first_a:
                                url_path = await first_a.get_attribute("href")

                        if not url_path:
                            logging.warning(f"Could not extract URL for listing {i+1} (Title: {title_text}). Skipping.")
                            continue

                        if not url_path.startswith(('http://', 'https://')):
                            listing_url = f"https://www.autotrader.com{url_path}"
                        else:
                            listing_url = url_path

                        # Attempt to get Price
                        price_el = await container.query_selector("div[data-cmp='firstPrice']") # Updated selector
                        if price_el:
                            raw_price_text = await price_el.inner_text()
                            price_text = raw_price_text.replace('$', '').replace(',', '').strip() if raw_price_text else "N/A"
                        else:
                            # Fallback for price (e.g. .first-price class directly)
                            price_el_fallback = await container.query_selector(".first-price")
                            if price_el_fallback:
                                raw_price_text = await price_el_fallback.inner_text()
                                price_text = raw_price_text.replace('$', '').replace(',', '').strip() if raw_price_text else "N/A"
                            else:
                                logging.warning(f"Price not found for listing {listing_url}")
                                price_text = "N/A"


                        # Mileage - Set to N/A as it's not reliably on the card from previous findings
                        mileage_text = "N/A"
                        # logging.info(f"Mileage not scraped from listing card for {listing_url} (by design for now).")

                        vin_text = None

                        listing_data = {
                            "listing_url": listing_url,
                            "title": title_text, # Already defaults to N/A or has value
                            "price": price_text, # Already defaults to N/A or has value
                            "mileage": mileage_text, # Is N/A
                            "vin": vin_text,
                            "source_name": self.source_name,
                            "data_points": {
                                "page_title_at_scrape": title # page's title, not listing's
                            }
                        }
                        listings_data.append(listing_data)
                        processed_count += 1
                        logging.info(f"Successfully processed listing: {title_text[:50]}... URL: {listing_url}")

                    except Exception as e:
                        logging.error(f"Error processing listing container {i+1} for URL {listing_url if listing_url else 'Unknown'}: {e}", exc_info=True)
                        continue

                logging.info(f"Successfully processed {processed_count} out of {len(listing_containers)} listing containers.")

            except Exception as e:
                logging.error(f"An error occurred during Playwright scraping phase: {e}", exc_info=True)
            finally:
                if browser:
                    logging.info("Closing browser.")
                    await browser.close()

        return listings_data


async def scrape_autotrader_data(autotrader_url: str, headless: bool = True, timeout: int = 120000) -> list[dict]:
    """
    High-level function to scrape data from AutoTrader.
    Initializes the scraper and calls its scraping method.

    Args:
        autotrader_url (str): The URL to scrape.
        headless (bool): Whether to run the browser in headless mode.
        timeout (int): Timeout for scraping operations in milliseconds.

    Returns:
        list[dict]: A list of scraped listing data.
    """
    scraper = AutoTraderScraper()
    listings = await scraper.get_private_listings(autotrader_url=autotrader_url, headless=headless, timeout=timeout)
    return listings


async def scrape_autotrader_and_update_db(db: Session, autotrader_url: str, headless: bool, scrape_timeout: int):
    """
    Scrapes listings from AutoTrader and updates the database.

    Args:
        db (Session): The SQLAlchemy database session.
        autotrader_url (str): The URL to scrape.
        headless (bool): Whether to run the browser in headless mode.
        scrape_timeout (int): Timeout for scraping operations in milliseconds.

    Returns:
        dict: A status dictionary with counts of added, updated, and scraped listings.
    """
    logging.info(f"Starting scrape and update for URL: {autotrader_url}")
    
    try:
        listings_data = await scrape_autotrader_data(
            autotrader_url=autotrader_url,
            headless=headless,
            timeout=scrape_timeout
        )
    except Exception as e:
        logging.error(f"Failed to scrape data from {autotrader_url}: {e}", exc_info=True)
        return {"status": "error", "message": f"Scraping failed: {e}"}

    added_count = 0
    updated_count = 0
    scraped_count = len(listings_data)

    for listing_data in listings_data:
        source_url = listing_data.get('listing_url') # Renamed from 'url' to 'listing_url' in dummy data
        if not source_url:
            logging.warning(f"Scraped item missing 'listing_url': {listing_data.get('title')}. Skipping.")
            continue

        try:
            existing_listing = db.query(CarListing).filter(CarListing.source_url == source_url).first()

            if existing_listing:
                # Placeholder for update logic
                # existing_listing.extracted_at = datetime.utcnow()
                # existing_listing.data_points = {k: v for k, v in listing_data.items() if k != 'listing_url'}
                # # Update other fields like price if necessary
                # db.add(existing_listing) # Not strictly necessary if only mutable fields changed and session tracks
                updated_count += 1
                logging.info(f"Listing at {source_url} already exists. Marked for update (placeholder).")
            else:
                new_listing = CarListing(
                    platform="autotrader",
                    extracted_at=datetime.utcnow(),
                    source_url=source_url,
                    # Ensure data_points stores everything else from listing_data
                    data_points={k: v for k, v in listing_data.items() if k != 'listing_url'}
                )
                db.add(new_listing)
                added_count += 1
                logging.info(f"New listing added from {source_url}")
        except Exception as e:
            logging.error(f"Error processing listing {source_url} for DB: {e}", exc_info=True)
            # Decide if you want to rollback here or continue with other listings

    try:
        db.commit()
        logging.info("Database changes committed.")
    except Exception as e:
        logging.error(f"Database commit failed: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": f"DB commit failed: {e}", "added": 0, "updated": 0, "scraped_count": scraped_count}

    status_summary = {
        "status": "success",
        "added": added_count,
        "updated": updated_count,
        "scraped_count": scraped_count
    }
    logging.info(f"DB update summary: {status_summary}")
    return status_summary

async def main():
    # Example: Fetch AUTOTRADER_URL from environment or use a default
    url = os.getenv("AUTOTRADER_URL", "https://www.autotrader.com/cars-for-sale/private-seller")
    headless_str = os.getenv("HEADLESS_BROWSER", "True")
    headless = headless_str.lower() == "true"
    scrape_timeout_str = os.getenv("SCRAPE_TIMEOUT", "120000")
    try:
        scrape_timeout = int(scrape_timeout_str)
    except ValueError:
        logging.warning(f"Invalid SCRAPE_TIMEOUT value: {scrape_timeout_str}. Defaulting to 120000ms.")
        scrape_timeout = 120000

    # from database import SessionLocal # Already imported at the top
    db: Session = SessionLocal()
    try:
        logging.info(f"Starting scraper and DB update for URL: {url}, Headless: {headless}, Timeout: {scrape_timeout}ms")
        stats = await scrape_autotrader_and_update_db(
            db=db,
            autotrader_url=url,
            headless=headless,
            scrape_timeout=scrape_timeout # Pass the integer directly
        )
        logging.info(f"Scraping and DB update completed: {stats}")
    except Exception as e:
        logging.error(f"Error during scraping and DB update in main: {e}", exc_info=True)
    finally:
        logging.info("Closing DB session in main.")
        db.close()

if __name__ == "__main__":
    # To run this:
    # 1. Ensure Playwright browsers are installed: `playwright install chromium`
    # 2. Set environment variables if needed (AUTOTRADER_URL, HEADLESS_BROWSER, SCRAPE_TIMEOUT)
    # 3. Uncomment the line below
    asyncio.run(main())
    # pass # Keep it passive for now, to be run manually when needed
