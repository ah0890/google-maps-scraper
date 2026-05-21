# Google Maps Business Scraper

Production-ready Streamlit dashboard for scraping Google Maps business listings by keyword and location batch (CSV).

## Features

- Premium dark SaaS UI
- Playwright async scraping with anti-bot helpers
- Multi-location CSV batch runs
- Live metrics, progress, ETA, pause/stop controls
- AgGrid table with search, sort, and pagination
- Auto-save exports (CSV / XLSX)
- Error screenshots and daily logs

## Project Structure

```
google-maps-scraper/
├── app.py
├── scraper.py
├── ui.py
├── utils.py
├── requirements.txt
├── sample_locations.csv
├── assets/
│   └── styles.css
├── screenshots/
├── exports/
└── logs/
```

## Installation

### 1. Create virtual environment (recommended)

```bash
cd C:\Users\amjad\Projects\google-maps-scraper
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers

```bash
playwright install chromium
```

## Run

```bash
streamlit run app.py
```

Open the URL shown in the terminal (typically `http://localhost:8501`).

## Usage

1. Enter a business keyword (e.g. `plumber`, `coffee shop`).
2. Upload a CSV with a `location` column (see `sample_locations.csv`).
3. Adjust sidebar settings (max results, headless, delay, concurrency, proxy).
4. Click **Start Scraping**.
5. Monitor live results and download **Export CSV**.

## CSV Format

```csv
location
Los Angeles
Chicago
New York
```

## Settings

| Setting | Description |
|---------|-------------|
| Max Results Per Location | Cap listings per city |
| Headless Mode | Run browser without UI |
| Delay Between Requests | Min/max human-like delay |
| Concurrent Browser Tabs | Parallel locations (1–3) |
| Proxy | Optional `http://host:port` |
| Export Format | CSV or XLSX auto-save |

## Legal Notice

Scraping may be restricted by Google's Terms of Service. Use this tool only for permitted purposes and respect rate limits, robots policies, and local laws.

## Troubleshooting

- **No results:** Increase delay, disable headless for debugging, verify keyword/location.
- **Playwright errors:** Re-run `playwright install chromium`.
- **Blocked by Google:** Use proxy, lower concurrency, increase delays.
- **Logs:** Check `logs/scraper_YYYYMMDD.log`
- **Error screenshots:** See `screenshots/`
