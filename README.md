# Vehicle Tracker

This project provides a FastAPI-based API and web scraper for collecting and storing vehicle listings from sites like AutoTrader. It uses Playwright for scraping and SQLAlchemy with SQLite for storage.

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Copy `.env.example` to `.env` and adjust settings as needed.
3. Run the API:
   ```bash
   uvicorn main:app --reload
   ```
4. Trigger scraping via the `/api/v1/vehicles/scrape` endpoint.

The scraper can also be run standalone:
```bash
python main.py scrape_test
```

## Environment Variables

Set the following variables in a `.env` file or your deployment environment:

| Variable | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | Database connection URL | `sqlite+aiosqlite:///./vehicle_data.db` |
| `HEADLESS` | Run the browser in headless mode | `true` |
| `BROWSER_TIMEOUT` | Playwright launch timeout (ms) | `60000` |
| `PAGE_DELAY` | Base delay after page loads (ms) | `5000` |
| `MIN_DELAY_BETWEEN_ACTIONS` | Delay between scraping actions (s) | `2.5` |
| `API_HOST` | Host for the FastAPI server | `127.0.0.1` |
| `API_PORT` | Port for the FastAPI server | `8000` |
| `MAX_LISTINGS_PER_SESSION` | Maximum listings fetched per scrape | `25` |
| `PROXY_SERVER` | *(Optional)* Proxy URL for Playwright | - |
| `PROXY_USERNAME` | *(Optional)* Proxy username | - |
| `PROXY_PASSWORD` | *(Optional)* Proxy password | - |

### Pagination

The `/api/v1/vehicles/` endpoint accepts `skip` and `limit` query parameters to paginate results.
Example: `/api/v1/vehicles/?skip=25&limit=25`.


