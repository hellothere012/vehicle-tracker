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

## Docker

1. Build the image:
   ```bash
   ./build.sh
   ```
2. Run the container:
   ```bash
   docker run -p 8000:8000 vehicle-tracker
   ```

The API will be available at `http://localhost:8000`.
