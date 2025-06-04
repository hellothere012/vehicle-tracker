# Vehicle Tracker

This project provides a FastAPI service that scrapes private listings from AutoTrader and stores the results in a database. The API exposes endpoints to trigger scraping jobs, ingest listings, and query saved data.

## Requirements

- Python 3.11+
- [Playwright](https://playwright.dev/python/)
- A supported browser for Playwright (installed automatically with `playwright install`)

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies and Playwright browsers:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Copy `.env.example` to `.env` and adjust values as needed.
4. Initialize the database tables:
   ```bash
   python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"
   ```

## Running the API

Start the server locally with Uvicorn:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` by default.

### Docker

To run the service in Docker:

```bash
docker build -t vehicle-tracker .
docker run --env-file .env -p 8000:8000 vehicle-tracker
```

## Environment Variables

The application uses the following environment variables (see `.env.example`):

- `AUTOTRADER_URL` – URL to scrape listings from.
- `DATABASE_URL` – SQLAlchemy database URL (SQLite by default).
- `LOG_LEVEL` – Logging verbosity, e.g. `INFO` or `DEBUG`.
- `HEADLESS_BROWSER` – Set to `True` to run Playwright headless.
- `SCRAPE_TIMEOUT` – Page timeout in milliseconds.
- Optional proxy settings: `PROXY_HOST`, `PROXY_PORT`, `WEBSHARE_USERNAME`, `WEBSHARE_PASSWORD`.
- `PORT` – Port for Uvicorn when deployed (defaults to `8000`).

## Database

SQLite is used by default and stores data in `./data/vehicle_tracker.db`. To switch to another database such as PostgreSQL, set `DATABASE_URL` accordingly.

