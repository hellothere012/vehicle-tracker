import asyncio
import json
import re
import random
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser, PlaywrightException, Locator
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime
import logging
import hashlib

from src.config import settings
from src.models.vehicle import VehicleListingCreate

logger = logging.getLogger(__name__)

class AutoTraderScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright_instance: Optional[async_playwright] = None
        self.base_action_delay = settings.MIN_DELAY_BETWEEN_ACTIONS
        self.page_load_delay = settings.PAGE_DELAY / 1000

    async def __aenter__(self):
        logger.info("Initializing AutoTrader Scraper...")
        self.playwright_instance = await async_playwright().start()
        try:
            proxy_cfg = None
            if settings.PROXY_SERVER:
                proxy_cfg = {"server": settings.PROXY_SERVER}
                if settings.PROXY_USERNAME and settings.PROXY_PASSWORD:
                    proxy_cfg["username"] = settings.PROXY_USERNAME
                    proxy_cfg["password"] = settings.PROXY_PASSWORD

            self.browser = await self.playwright_instance.chromium.launch(
                headless=settings.HEADLESS,
                proxy=proxy_cfg,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certificate-errors',
                    '--ignore-certificate-errors-spki-list',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage'
                ],
                timeout=settings.BROWSER_TIMEOUT
            )
            logger.info(f"Browser launched (Headless: {settings.HEADLESS})")
        except PlaywrightException as e:
            logger.error(f"Failed to launch browser: {e}")
            if self.playwright_instance:
                await self.playwright_instance.stop()
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.info("Closing AutoTrader Scraper resources...")
        if self.browser and self.browser.is_connected():
            try:
                await self.browser.close()
                logger.info("Browser closed.")
            except PlaywrightException as e:
                logger.error(f"Error closing browser: {e}")
        if self.playwright_instance:
            try:
                await self.playwright_instance.stop()
                logger.info("Playwright instance stopped.")
            except Exception as e:
                logger.error(f"Error stopping Playwright: {e}")
        if exc_type:
            logger.error(f"Exception occurred during scraping: {exc_val}", exc_info=(exc_type, exc_val, exc_tb))

    async def _apply_stealth_measures(self, page: Page):
        logger.info("Applying stealth measures to page...")
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ]
        await page.set_extra_http_headers({"User-Agent": random.choice(user_agents)})
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'en-GB'] });
            const pluginCount = Math.floor(Math.random() * 3) + 1;
            Object.defineProperty(navigator, 'plugins', {
                get: () => Array(pluginCount).fill(null).map((_, i) => ({ name: `Plugin ${i}`, filename: `plugin${i}.dll`, description: `Mock plugin ${i}` }))
            });
            const mimeTypeCount = Math.floor(Math.random() * 3) + 1;
             Object.defineProperty(navigator, 'mimeTypes', {
                get: () => Array(mimeTypeCount).fill(null).map((_, i) => ({ type: `application/x-mimetype${i}`, suffixes: `m${i}`, description: `Mock mimetype ${i}` }))
            });
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Open Source Technology Center';
                if (parameter === 37446) return 'Mesa DRI Intel(R) Iris Xe Graphics (TGL GT2)';
                return getParameter.apply(this, arguments);
            };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(parameters)
            );
            try { Date.prototype.getTimezoneOffset = function() { return -Math.floor(Math.random() * 8 + 3) * 60; }; } catch (e) {}
        """)
        viewports = [{"width": 1920, "height": 1080}, {"width": 1366, "height": 768}, {"width": 1440, "height": 900}, {"width": 2560, "height": 1440}]
        await page.set_viewport_size(random.choice(viewports))
        logger.info("Stealth measures applied.")

    async def _human_like_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None):
        min_d = min_delay if min_delay is not None else self.base_action_delay
        max_d = max_delay if max_delay is not None else self.base_action_delay + 2.0
        delay = random.uniform(min_d, max_d)
        logger.debug(f"Waiting {delay:.2f} seconds...")
        await asyncio.sleep(delay)

    async def _human_like_scroll(self, page: Page, scroll_attempts=7):
        logger.info(f"Performing human-like scrolling: {scroll_attempts} attempts...")
        previous_scroll_height = -1.0
        for i in range(scroll_attempts):
            current_scroll_height = float(await page.evaluate("document.body.scrollHeight"))
            if abs(current_scroll_height - previous_scroll_height) < 1.0 and i > 0:
                logger.info(f"Scroll attempt {i+1}: Reached end of scrollable content or no new content loaded.")
                break
            scroll_amount = await page.evaluate(f"Math.random() * window.innerHeight * 0.7 + window.innerHeight * 0.3")
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await self._human_like_delay(min_delay=0.8, max_delay=2.2)
            previous_scroll_height = current_scroll_height
        logger.info("Scrolling to bottom one last time...")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await self._human_like_delay(min_delay=2.0, max_delay=3.5)
        logger.info("Scrolling finished.")

    def _extract_listing_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            if 'listingId' in query_params:
                return query_params['listingId'][0]
            path_parts = [part for part in parsed_url.path.split('/') if part]
            if 'vehicle' in path_parts:
                vehicle_idx = path_parts.index('vehicle')
                if vehicle_idx + 1 < len(path_parts):
                    return path_parts[vehicle_idx+1]
            for part in reversed(path_parts):
                if part.isdigit() and len(part) > 5:
                    return part
        except Exception as e:
            logger.warning(f"Could not parse structured listing ID from URL {url}: {e}")
        logger.debug(f"No structured ID found, hashing URL for ID: {url}")
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def _parse_title_details(self, title_str: str) -> Dict:
        details = {'year': None, 'make': None, 'model': None, 'trim': None}
        if not title_str:
            return details
        original_title = title_str
        year_match = re.search(r'\b(19[89]\d|20[0-2]\d|2030)\b', title_str)
        if year_match:
            details['year'] = int(year_match.group(1))
            title_str = title_str.replace(year_match.group(1), "", 1).strip()
        title_str = re.sub(r'^(Used|New|Certified Pre-Owned|CPO)\s+', '', title_str, flags=re.IGNORECASE).strip()
        parts = title_str.split(maxsplit=3)
        if len(parts) > 0:
            details['make'] = parts[0]
        if len(parts) > 1:
            details['model'] = parts[1]
        if len(parts) > 2:
            details['trim'] = " ".join(parts[2:])
        logger.debug(f"Parsed title details: {details} from original title: '{original_title}'")
        return details

    async def _extract_listing_data(self, listing_element: Locator, page_url: str) -> Optional[VehicleListingCreate]:
        data_dict: Dict[str, any] = {}
        listing_html_for_debug = "N/A (HTML not captured)"
        try:
            link_el_selectors = [
                'a[data-cmp="inventoryListingCardLink"]',
                'a[data-testid="srp-list-item-link"]',
                'a[href*="vehicledetails.xhtml?listingId="]',
                'h2 > a',
                'h3 > a'
            ]
            raw_href = None
            for selector in link_el_selectors:
                link_el = listing_element.locator(selector).first
                if await link_el.count():
                    raw_href = await link_el.get_attribute("href", timeout=1500)
                    if raw_href:
                        break
            if not raw_href:
                logger.warning("No primary link found for a listing card. Skipping.")
                return None
            data_dict['listing_url'] = urljoin(page_url, raw_href)

            title_el_selectors = ["h2[data-cmp*='title']", "h3[data-cmp*='title']", "div[data-cmp='displayName'] h2", "h2", "h3"]
            raw_title = "Title Not Found"
            for selector in title_el_selectors:
                title_el = listing_element.locator(selector).first
                if await title_el.count():
                    try:
                        raw_title = await title_el.text_content(timeout=1500)
                        if raw_title and raw_title.strip():
                            break
                    except PlaywrightException:
                        continue
            data_dict['title'] = raw_title.strip()
            title_details = self._parse_title_details(data_dict['title'])
            data_dict.update(title_details)

            price_selectors = [
                "span[data-cmp='pricingSection'] .text-size-lg-3",
                "span[data-cmp='pricingSection']",
                ".pricing-section .first-price",
                "span[class*='price']", "div[class*='price']"
            ]
            for selector in price_selectors:
                price_el = listing_element.locator(selector).filter(has_text=re.compile(r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?")).first
                if await price_el.count():
                    try:
                        price_text = await price_el.text_content(timeout=1000)
                        cleaned_price = re.sub(r'[^\d.]', '', price_text)
                        if cleaned_price and cleaned_price != '.':
                            data_dict['price'] = float(cleaned_price)
                            break
                    except PlaywrightException:
                        continue

            mileage_selectors = [
                "div[data-cmp='listUnstyled'] li:has-text('miles')",
                "div.item-vehicle-mileage",
                "div[class*='mileage']", "span[class*='mileage']"
            ]
            for selector in mileage_selectors:
                mileage_el = listing_element.locator(selector).filter(has_text=re.compile(r"[\d,]+\s*mi(?:les)?", re.IGNORECASE)).first
                if await mileage_el.count():
                    try:
                        mileage_text = await mileage_el.text_content(timeout=1000)
                        match = re.search(r'([\d,]+)\s*mi', mileage_text, re.IGNORECASE)
                        if match:
                            data_dict['mileage'] = int(re.sub(r',', '', match.group(1)))
                            break
                    except PlaywrightException:
                        continue

            photo_selectors = [
                'img[data-cmp="responsiveImage"]',
                'img[data-testid="srp-list-item-image"]',
                '.srp-img-container img',
                'img[alt*="vehicle image"]'
            ]
            for selector in photo_selectors:
                photo_el = listing_element.locator(selector).first
                if await photo_el.count():
                    try:
                        src = await photo_el.get_attribute("src", timeout=1000)
                        if src and not src.startswith('data:image'):
                            data_dict['photo_url'] = urljoin(page_url, src)
                            break
                    except PlaywrightException:
                        continue

            features_list = []
            feature_selectors = ["ul[class*='features'] li", "div[data-cmp='pill']", ".item-特色 span"]
            for selector in feature_selectors:
                feature_elements = await listing_element.locator(selector).all()
                for fe_el in feature_elements[:5]:
                    try:
                        f_text = await fe_el.text_content(timeout=500)
                        if f_text and len(f_text.strip()) > 2 and len(f_text.strip()) < 50:
                            features_list.append(f_text.strip())
                    except PlaywrightException:
                        continue
                if features_list:
                    break
            data_dict['features'] = list(set(features_list))

            location_selectors = ["div[data-cmp*='location']", "div.text-gray-dark.text-truncate", ".item-location"]
            for selector in location_selectors:
                location_el = listing_element.locator(selector).first
                if await location_el.count():
                    try:
                        loc_text = await location_el.text_content(timeout=1000)
                        data_dict['location'] = loc_text.replace('Located in', '').replace('Dealership Location', '').strip()
                        if data_dict['location']:
                            break
                    except PlaywrightException:
                        continue

            data_dict['listing_id_external'] = self._extract_listing_id_from_url(data_dict['listing_url'])

            return VehicleListingCreate(**data_dict)

        except PlaywrightException as e:
            listing_html_for_debug = await listing_element.evaluate("element => element.outerHTML", timeout=1000)
            logger.error(f"Playwright error extracting data from a listing card: {e}. HTML: {listing_html_for_debug[:500]}...")
        except Exception as e:
            listing_html_for_debug = await listing_element.evaluate("element => element.outerHTML", timeout=1000)
            logger.error(f"General error extracting data from a listing card: {e}. HTML: {listing_html_for_debug[:500]}...")
        return None

    async def scrape_listings(self, search_url: str, max_listings_to_fetch: int) -> List[VehicleListingCreate]:
        if not self.browser or not self.browser.is_connected():
            logger.error("Browser not initialized or not connected. Call within async context manager.")
            return []
        page: Optional[Page] = None
        processed_listings: List[VehicleListingCreate] = []
        try:
            context = await self.browser.new_context(
                java_script_enabled=True,
                accept_downloads=False,
                locale='en-US'
            )
            page = await context.new_page()
            await self._apply_stealth_measures(page)
            logger.info(f"Navigating to search URL: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=settings.BROWSER_TIMEOUT)
            await self._human_like_delay(min_delay=self.page_load_delay, max_delay=self.page_load_delay + 3.0)
            cookie_selectors = ['#onetrust-accept-btn-handler', 'button:has-text("Accept All Cookies")']
            for cs_selector in cookie_selectors:
                try:
                    cookie_button = page.locator(cs_selector).first
                    if await cookie_button.is_visible(timeout=3000):
                        await cookie_button.click(timeout=5000, delay=random.uniform(0.3,0.8)*1000)
                        logger.info(f"Clicked cookie banner: {cs_selector}")
                        await self._human_like_delay(1.5, 2.5)
                        break
                except PlaywrightException:
                    logger.debug(f"Cookie banner not found/visible or clickable with: {cs_selector}")
            await self._human_like_scroll(page, scroll_attempts=settings.MAX_LISTINGS_PER_SESSION // 5 or 5)
            listing_card_selectors = [
                "article[data-cmp='inventoryListing']",
                "div[data-testid='srp-listing-item']",
                "div[data-cmp='inventorySpotlightListingCard']",
                ".inventory-listing",
                "div[class*='srp-results'] div[class*='vehicle-card']"
            ]
            all_card_elements_locators = []
            for selector in listing_card_selectors:
                elements_on_page = await page.locator(selector).count()
                if elements_on_page > 0:
                    logger.info(f"Found {elements_on_page} cards with selector '{selector}'")
                    all_card_elements_locators.append(page.locator(selector))
                    if selector in ["article[data-cmp='inventoryListing']", "div[data-testid='srp-listing-item']"]:
                        break
            final_card_locator = None
            if all_card_elements_locators:
                final_card_locator = all_card_elements_locators[0]
            if not final_card_locator:
                logger.warning(f"No listing cards found on page: {search_url}.")
                try:
                    await page.screenshot(path=f"debug_no_listings_{datetime.now():%Y%m%d%H%M%S}.png")
                except Exception as e:
                    logger.error(f"Failed to save screenshot: {e}")
                return []
            num_cards_on_page = await final_card_locator.count()
            logger.info(f"Total listing cards to process with chosen locator: {num_cards_on_page}")
            for i in range(num_cards_on_page):
                if len(processed_listings) >= max_listings_to_fetch:
                    logger.info(f"Reached max listings to fetch: {max_listings_to_fetch}")
                    break
                card_element = final_card_locator.nth(i)
                logger.info(f"Processing card {i+1}/{num_cards_on_page}...")
                try:
                    if not await card_element.is_visible(timeout=3000):
                        await card_element.scroll_into_view_if_needed(timeout=5000)
                        await self._human_like_delay(0.5, 1.0)
                except PlaywrightException as e:
                    logger.warning(f"Card {i+1} not visible or could not scroll into view, skipping: {e}")
                    continue
                listing_data = await self._extract_listing_data(card_element, page.url)
                if listing_data:
                    processed_listings.append(listing_data)
                    logger.info(f"Successfully extracted: {listing_data.title[:60]}... ({listing_data.listing_id_external})")
                else:
                    logger.warning(f"Failed to extract complete data from card {i+1}.")
                await self._human_like_delay()
        except PlaywrightException as e:
            logger.error(f"A Playwright error occurred during scraping session for {search_url}: {e}", exc_info=True)
            if page:
                try:
                    await page.screenshot(path=f"error_pw_session_{datetime.now():%Y%m%d%H%M%S}.png")
                except Exception as se:
                    logger.error(f"Failed to save error screenshot: {se}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during scraping session for {search_url}: {e}", exc_info=True)
            if page:
                try:
                    await page.screenshot(path=f"error_unexpected_session_{datetime.now():%Y%m%d%H%M%S}.png")
                except Exception as se:
                    logger.error(f"Failed to save error screenshot: {se}")
        finally:
            if page:
                try:
                    await page.close()
                except PlaywrightException as e:
                    logger.error(f"Error closing page: {e}")
            if 'context' in locals() and context:
                try:
                    await context.close()
                except PlaywrightException as e:
                    logger.error(f"Error closing context: {e}")
        logger.info(f"Scraping session for {search_url} finished. Extracted {len(processed_listings)} listings.")
        return processed_listings[:max_listings_to_fetch]

async def run_autotrader_scraper_example_standalone():
    example_search_url = "https://www.autotrader.com/cars-for-sale/by-owner/all-states?searchRadius=0&sortBy=datelistedDESC&numRecords=25"
    max_to_get = settings.MAX_LISTINGS_PER_SESSION
    async with AutoTraderScraper() as scraper:
        results = await scraper.scrape_listings(example_search_url, max_listings_to_fetch=max_to_get)
        if results:
            logger.info(f"\n--- Scraped {len(results)} AutoTrader Listings (Standalone Example Run) ---")
            for i, listing in enumerate(results):
                logger.info(f"{i+1}. ID_Ext: {listing.listing_id_external} - {listing.title} ({listing.year} {listing.make} {listing.model}) - Price: ${listing.price if listing.price else 'N/A'}")
        else:
            logger.info("No listings were extracted in the standalone example run.")
    return results
