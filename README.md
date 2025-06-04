# Vehicle Tracker

This project provides a FastAPI service that scrapes vehicle listings from AutoTrader using Playwright and stores them in a database.

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Docker Usage

Build the Docker image using the included helper script:

```bash
./build.sh
```

Alternatively build manually:

```bash
docker build -t vehicle-tracker .
```

Run the container and expose port `8000`:

```bash
docker run --env-file .env -p 8000:8000 vehicle-tracker
```

The API will then be available at `http://localhost:8000`.
