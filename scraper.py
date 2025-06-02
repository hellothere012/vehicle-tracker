import requests
import json
import time
import random
import logging
from playwright.sync_api import sync_playwright
import datetime
from urllib.parse import urljoin # Added
import re # Added

# Basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutoTraderScraper:
    """Scraper for AutoTrader private party listings, now with detailed Playwright logic."""
    
    def __init__(self, api_url, delay_range=(2, 5)): # delay_range is for scrolling/explicit waits
        self.api_url = api_url
        self.delay_range = delay_range
        self.base_url = "https://www.autotrader.com/cars-for-sale/private-seller"
        self.source = "autotrader.com" # Updated for more specificity
        self.headers = { # Kept for potential direct requests, Playwright uses its own context
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

    def send_to_api(self, vehicle_data):
        payload = {
            "platform": self.source, # Use self.source
            "extracted_at": datetime.datetime.now().isoformat(), # Correct usage
            "source_url": vehicle_data.get("listing_url", ""),
            "data_points": vehicle_data
        }
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully sent listing {vehicle_data.get('listing_id', 'N/A')} to API. Status: {response.status_code}")
            return True
        except requests.RequestException as e:
            logger.error(f"Error sending listing {vehicle_data.get('listing_id', 'N/A')} to API: {e}")
            return False

    def _handle_consent(self, page):
        """Attempts to click cookie consent buttons."""
        consent_selectors = [
            "button:has-text('Accept')",
            "button:has-text('Agree')",
            "button[id*='consent']",
            "button[class*='consent']",
            "button#onetrust-accept-btn-handler"
        ]
        for selector in consent_selectors:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=2000): # Short timeout for visibility check
                    logger.info(f"Consent button found with selector: {selector}. Attempting to click.")
                    button.click(timeout=3000)
                    logger.info("Consent button clicked.")
                    page.wait_for_timeout(1000) # Wait for overlay
                    return True
            except Exception as e:
                logger.debug(f"Consent selector {selector} not found or failed: {e}")
        logger.info("No common consent buttons found or clicked.")
        return False

    def get_private_listings(self, max_pages=1):
        logger.info(f"Starting to get private listings from AutoTrader, max_pages: {max_pages}")
        processed_listings_data = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True) # Set headless=False for debugging
                context = browser.new_context(
                    user_agent=self.headers['User-Agent'],
                    java_script_enabled=True,
                )
                page_obj = context.new_page()
                
                logger.info(f"Navigating to {self.base_url}")
                try:
                    page_obj.goto(self.base_url, wait_until="networkidle", timeout=60000)
                except Exception as e:
                    logger.error(f"Timeout or error navigating to {self.base_url}: {e}")
                    browser.close()
                    return processed_listings_data

                self._handle_consent(page_obj)

                for current_page_num in range(1, max_pages + 1):
                    logger.info(f"Processing page {current_page_num}")

                    time.sleep(random.uniform(self.delay_range[0], self.delay_range[1]))

                    extracted_page_listings_data = self._extract_listings(page_obj)
                    processed_listings_data.extend(extracted_page_listings_data)

                    if self._is_last_page(page_obj):
                        logger.info("Last page determined.")
                        break

                    if current_page_num < max_pages:
                        logger.info("Attempting to go to the next page.")
                        next_page_selectors = [
                            "a[data-cmp='paginationNext']",
                            "button:has-text('Next')",
                            "a[aria-label*='next page i']",
                        ]
                        clicked_next = False
                        for selector in next_page_selectors:
                            try:
                                next_button = page_obj.locator(selector).first
                                if next_button.is_visible(timeout=3000) and next_button.is_enabled(timeout=3000):
                                    logger.info(f"Next page button found with selector: {selector}. Clicking.")
                                    next_button.click(timeout=5000)
                                    page_obj.wait_for_load_state("networkidle", timeout=30000)
                                    logger.info("Navigated to next page.")
                                    clicked_next = True
                                    break
                                else:
                                    logger.debug(f"Next page selector {selector} not visible or not enabled.")
                            except Exception as e:
                                logger.debug(f"Next page selector {selector} failed: {e}")

                        if not clicked_next:
                            logger.warning("Could not find or click a 'Next Page' button.")
                            break
                    else:
                        logger.info(f"Reached max_pages limit ({max_pages}). No further pagination.")

                browser.close()
        except Exception as e:
            logger.error(f"An error occurred during Playwright operations: {e}", exc_info=True)
        
        logger.info(f"Finished getting private listings. Total listings processed: {len(processed_listings_data)}")
        return processed_listings_data

    def _extract_listings(self, page):
        logger.info("Starting extraction of listings from current page.")
        
        for i in range(3): # Perform a few small scrolls
            page.evaluate("window.scrollBy(0, window.innerHeight * 0.7)")
            logger.debug(f"Scrolled down ({i+1}/3).")
            time.sleep(random.uniform(0.5, 1.5))

        listing_elements_selectors = [
            "article[data-cmp='inventoryListing']",
            "div[class*='item-card']", # More generic
            "div[data-qa='vehicle-card']"
        ]
        
        listings_on_page = []
        elements_found = []
        for selector in listing_elements_selectors:
            elements_found = page.query_selector_all(selector)
            if elements_found:
                logger.info(f"Found {len(elements_found)} listing elements with selector: {selector}")
                break
            else:
                logger.debug(f"No listing elements found with selector: {selector}")
        
        if not elements_found:
            logger.warning("No listing elements found on the page with any of the tried selectors.")
            return []

        for element_handle in elements_found:
            parsed_details = self._parse_listing(element_handle, page)
            if parsed_details:
                # Attempt to generate a unique ID if not present from parsing
                if not parsed_details.get('listing_id') and parsed_details.get('listing_url'):
                     try:
                        path_parts = [part for part in parsed_details['listing_url'].split('/') if part]
                        potential_id = path_parts[-1] if path_parts else f"random_{random.randint(10000,99999)}"
                        id_match = re.search(r'(\d{9,})', potential_id) # AutoTrader IDs are often long numbers
                        if id_match:
                            parsed_details['listing_id'] = f"AT_{id_match.group(1)}"
                        else:
                             # Fallback for URLs not ending in a clear numeric ID part
                            cleaned_id_part = re.sub(r'[^a-zA-Z0-9_-]', '', potential_id)[:50] # Clean and truncate
                            parsed_details['listing_id'] = f"AT_{cleaned_id_part}" if cleaned_id_part else f"AT_NOLINKID_{random.randint(10000,99999)}"
                     except Exception as e_id:
                        logger.error(f"Error generating listing_id from URL {parsed_details.get('listing_url')}: {e_id}")
                        parsed_details['listing_id'] = f"AT_ERRORID_{random.randint(10000,99999)}"
                elif not parsed_details.get('listing_id'):
                    parsed_details['listing_id'] = f"AT_MISSINGDATA_{random.randint(10000,99999)}"


                if self.send_to_api(parsed_details):
                    listings_on_page.append(parsed_details)
        return listings_on_page

    def _parse_listing(self, listing_element, page):
        logger.debug("Attempting to parse a single listing element.")
        data = {'features': [], 'images': []} # Initialize with defaults for lists

        def get_text(el_handle, selector, default=""):
            try:
                element = el_handle.query_selector(selector)
                return element.inner_text().strip() if element else default
            except Exception as e:
                logger.debug(f"Selector '{selector}' text extraction error: {e}")
                return default

        def get_attribute(el_handle, selector, attribute, default=""):
            try:
                element = el_handle.query_selector(selector)
                attr_value = element.get_attribute(attribute) if element else default
                return attr_value.strip() if attr_value else default
            except Exception as e:
                logger.debug(f"Selector '{selector}' attribute '{attribute}' extraction error: {e}")
                return default

        data['title'] = get_text(listing_element, "h2[data-cmp='subheading']") or \
                        get_text(listing_element, "a[data-cmp='link']") # Often title is in a link
        if not data['title']: # Fallback selectors for title
             data['title'] = get_text(listing_element, "div[class*='title']") or get_text(listing_element, "h2")
        if not data['title']:
             logger.warning(f"Could not extract title for a listing using primary selectors. Full element text: {listing_element.text_content()[:200]}")


        price_str = get_text(listing_element, "span[data-cmp='text'].text-size-600") or \
                    get_text(listing_element, ".inventory-listing-price span[data-cmp='text']") or \
                    get_text(listing_element, "div[class*='price'] span") # More general price span
        if not price_str: price_str = get_text(listing_element, "span[class*='price']") # even more general

        try:
            # Remove currency, commas, and "Not Priced" or any other non-numeric text before conversion
            cleaned_price_str = re.sub(r"[^\d.]", "", price_str)
            if cleaned_price_str:
                 data['price'] = float(cleaned_price_str)
            else: # If empty after cleaning (e.g. was "Not Priced")
                data['price'] = 0.0
                logger.info(f"Price string '{price_str}' resulted in empty after cleaning. Set to 0.0.")
        except ValueError:
            logger.warning(f"Could not parse price from string: '{price_str}'. Defaulting to 0.0.")
            data['price'] = 0.0
        
        link_href = get_attribute(listing_element, "a[data-cmp='link']", "href") or \
                    get_attribute(listing_element, "a", "href")
        if link_href:
            data['listing_url'] = urljoin(self.base_url, link_href) # Use self.base_url for consistency
        else:
            data['listing_url'] = ""
            logger.warning("Could not extract listing URL.")

        img_src = get_attribute(listing_element, "img[data-cmp='image']", "src") or \
                  get_attribute(listing_element, "img[class*='vehicle-image']", "src")
        if img_src:
            data['images'] = [{'url': urljoin(self.base_url, img_src), 'is_primary': True}]
        
        # Year, Make, Model from title (improved parsing)
        title_text_for_parse = data.get('title', '')
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", title_text_for_parse)
        data['year'] = int(year_match.group(0)) if year_match else None
        
        if data['year']:
            remaining_title = title_text_for_parse.replace(str(data['year']), "").strip()
            # Common pattern: Make Model Trim. Try to split and identify.
            # This is still naive and site-specific.
            parts = [p for p in remaining_title.split(" ") if p] # Remove empty strings
            if parts:
                data['make'] = parts[0]
                if len(parts) > 1:
                    # Model could be one or more words. Assume everything after make is model/trim.
                    data['model'] = " ".join(parts[1:])
                else:
                    data['model'] = None
            else:
                data['make'] = None
                data['model'] = None
        else: # If no year, make/model extraction from title is unreliable
            data['make'] = None
            data['model'] = None

        mileage_text = get_text(listing_element, "span.text-normal:contains('miles')") or \
                       get_text(listing_element, "div.text-size-sm-100:contains('miles')") or \
                       get_text(listing_element, "li:contains('miles')") # mileage often in a list item
        if not mileage_text: # Broader search
             mileage_elements = listing_element.query_selector_all("*:has-text('miles')")
             for me in mileage_elements:
                 try: mileage_text = me.inner_text(); break
                 except: continue

        if mileage_text:
            mileage_match = re.search(r"([\d,]+)\s*miles", mileage_text, re.IGNORECASE)
            if mileage_match:
                try:
                    data['mileage'] = int(mileage_match.group(1).replace(',', ''))
                except ValueError:
                    logger.warning(f"Could not parse mileage from found text: '{mileage_text}'")
                    data['mileage'] = None
            else:
                data['mileage'] = None
        else:
            data['mileage'] = None
            logger.debug("No mileage text found for a listing.")

        features_elements = listing_element.query_selector_all("ul[class*='features'] li") or \
                            listing_element.query_selector_all("div[class*='spec'] li") # Alternative feature list
        
        extracted_features = []
        for el in features_elements:
            try:
                feature_text = el.inner_text().strip()
                if feature_text and len(feature_text) < 100 and feature_text.lower() != "more":
                    extracted_features.append(feature_text)
            except Exception: continue
        data['features'] = extracted_features[:10] # Limit number of features

        if not any([data.get('title'), data.get('price', 0) > 0, data.get('listing_url')]):
             logger.error(f"Core data (title, price, url) extraction failed for element. Skipping. Element HTML snippet: {listing_element.inner_html()[:300]}")
             return None # Skip if essential data is missing
            
        logger.debug(f"Successfully parsed data: {json.dumps(data, indent=2, default=str)}")
        return data

    def _is_last_page(self, page):
        logger.info("Checking if it's the last page.")
        next_page_selectors = [
            "a[data-cmp='paginationNext']",
            "button:has-text('Next')", # common text for next button
            "a[aria-label*='next page i']", # common aria-label pattern
            "a.next-page-link" # example class
        ]
        for selector in next_page_selectors:
            try:
                next_button = page.locator(selector).first
                if next_button.is_visible(timeout=1000): # Quick check for visibility
                    is_disabled = next_button.is_disabled(timeout=1000) or \
                                  next_button.get_attribute("aria-disabled") == "true"
                    if is_disabled:
                        logger.info(f"Next page button ({selector}) is disabled. This is the last page.")
                        return True
                    logger.info(f"Next page button ({selector}) is visible and enabled. Not the last page.")
                    return False
                else:
                    logger.debug(f"Next page button ({selector}) not visible.")
            except Exception as e:
                logger.debug(f"Error checking selector {selector} for last page: {e}")
        
        logger.info("No enabled next page button found with any of the specified selectors. Assuming this is the last page.")
        return True
        
    def _get_sample_data(self): # Kept for reference or isolated testing
        now = datetime.datetime.now()
        return [
            {
                'source': self.source,
                'listing_id': 'AT_SAMPLE_DATA_123', # Updated ID
                'title': '2020 Ford Explorer XLT - Playwright Sample',
                'year': 2020,
                'make': 'Ford',
                'model': 'Explorer',
                'price': 32000.00,
                'mileage': 25000,
                'listing_url': f"{self.base_url}/example-listing-AT_PLAYWRIGHT_SAMPLE_123",
                'images': [{'url': 'http://example.com/img1.jpg', 'is_primary': True}],
                'features': ['Playwright Compatible', 'Sample Data']
            }
        ]

if __name__ == "__main__":
    logger.info("Starting scraper script execution.")
    API_ENDPOINT_URL = "http://localhost:8000/api/vehicles/"

    scraper = AutoTraderScraper(api_url=API_ENDPOINT_URL)
    results = scraper.get_private_listings(max_pages=1)
    
    logger.info(f"Scraping process completed. Results: {len(results)} listings' data were prepared.")
    if results:
        logger.info("Sample of successfully processed data (first item):")
        logger.info(json.dumps(results[0], indent=2))
    # The old Database class and direct database interaction logic have been removed.
    # The scraper now sends data to the FastAPI backend.
