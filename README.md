# 🗺️ Google Maps Business Scraper (Maps Scraper Pro)

Production-ready **Streamlit** dashboard for scraping Google Maps business listings by **keyword** + **location CSV**. Premium dark SaaS UI, live results, and CSV/XLSX export.

**Repository:** [github.com/ah0890/google-maps-scraper](https://github.com/ah0890/google-maps-scraper)

---

## ✨ Features

| Feature | Description |
|--------|-------------|
| 🔍 Keyword search | e.g. `dentist`, `plumber`, `coffee shop` |
| 📍 Batch locations | Upload CSV with multiple cities |
| 🤖 Playwright (async) | Reliable browser automation |
| 🛡️ Anti-bot | Random delays, human scroll, fake user agents, retries, proxy |
| 📊 Live dashboard | Metrics, progress bar, ETA, pause/stop |
| 📋 AgGrid table | Search, sort, pagination |
| 💾 Export | Download CSV or auto-save to `exports/` |
| 📸 Debug | Error screenshots + daily logs |

**Extracted fields:** Business name · Address · Website · Phone · Rating · Review count

---

## 🖥️ Screenshots

_Add screenshots of your dashboard here after first run._

---

## 📁 Project Structure

```
google-maps-scraper/
├── app.py                 # Streamlit entry (run this with streamlit)
├── scraper.py             # Playwright async scraper
├── ui.py                  # UI components & AgGrid
├── utils.py               # Logging, CSV, state helpers
├── requirements.txt
├── sample_locations.csv
├── assets/
│   └── styles.css
├── exports/               # Auto-saved results
├── logs/                  # Daily log files
└── screenshots/           # Error screenshots
```

---

## ⚙️ Requirements

- **Python 3.10+**
- **Windows / macOS / Linux**
- Internet connection
- ~500 MB disk (Playwright Chromium)

---

## 🚀 Installation

### 1. Clone repository

```bash
git clone https://github.com/ah0890/google-maps-scraper.git
cd google-maps-scraper
```

### 2. Create virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser

```bash
playwright install chromium
```

---

## ▶️ How to Run (Important)

> ⚠️ **Do NOT run** `python app.py` — that will not start the web UI.  
> **Always use:**

```bash
streamlit run app.py
```

When you see:

```text
Local URL: http://localhost:8501
```

Open **http://localhost:8501** in your browser. Keep the terminal open while using the app.

---

## 📖 Usage Guide

1. Open the app (`streamlit run app.py`).
2. Enter a **business keyword** (Step 1).
3. Upload a **CSV** with a `location` column (Step 2) — see `sample_locations.csv`.
4. Adjust **Settings** in the sidebar (optional).
5. Click **Start Scraping**.
6. Watch live results in the dashboard.
7. Click **Export CSV** or find auto-saved files in `exports/`.

### CSV format

```csv
location
Los Angeles
Chicago
New York
```

### Sidebar settings

| Setting | Description |
|---------|-------------|
| Max Results Per Location | Max businesses per city (1–50) |
| Headless Mode | Hide browser window |
| Delay Between Requests | Slower = safer, fewer blocks |
| Concurrent Browser Tabs | Parallel cities (1–3) |
| Proxy | Optional `http://user:pass@host:port` |
| Export Format | CSV or XLSX |
| Auto-save Results | Save to `exports/` when done |

---

## 🔧 VS Code Tips

- Open folder: `google-maps-scraper`
- Select interpreter: `.venv\Scripts\python.exe` (Windows)
- Run in terminal: `streamlit run app.py` (not the ▶ Run button on `app.py`)

---

## 🌐 Push to GitHub (first time)

If you already have code locally and an empty GitHub repo:

```powershell
cd google-maps-scraper
git add .
git commit -m "Initial commit: Google Maps Scraper"
git branch -M main
git remote add origin https://github.com/ah0890/google-maps-scraper.git
git push -u origin main
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| `ERR_CONNECTION_REFUSED` on :8501 | Run `streamlit run app.py` and wait for Local URL |
| `missing ScriptRunContext` warnings | You used `python app.py` — use `streamlit run app.py` |
| No scrape results | Increase delay; try headless **off**; check keyword/CSV |
| Playwright error | Run `playwright install chromium` again |
| Blocked by Google | Add proxy, lower concurrency, increase delays |
| Logs | `logs/scraper_YYYYMMDD.log` |
| Error images | `screenshots/` folder |

---

## ⚖️ Legal & Ethics

Scraping may be restricted by **Google Maps Terms of Service**. Use this tool only for **lawful, permitted purposes**. Respect rate limits and data privacy laws. The author is not responsible for misuse.

---

## 🛠️ Tech Stack

- Python · Streamlit · Playwright (async) · Pandas · asyncio  
- fake-useragent · streamlit-aggrid · Custom CSS  

---

## 📌 Urdu Guide (اردو)

### یہ ٹول کیا کرتا ہے؟

Google Maps سے کاروبار کی معلومات نکالتا ہے: نام، پتہ، ویب سائٹ، فون، ریٹنگ وغیرہ۔

### انسٹال (خلاصہ)

```powershell
git clone https://github.com/ah0890/google-maps-scraper.git
cd google-maps-scraper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### چلانا (ضروری)

```powershell
streamlit run app.py
```

پھر براؤزر میں کھولیں: **http://localhost:8501**

> ❌ `python app.py` مت چلائیں — ایپ کھلے گی نہیں۔

### استعمال

1. Keyword لکھیں (مثلاً `dentist`)
2. CSV اپ لوڈ کریں (`location` کالم ضروری)
3. **Start Scraping** دبائیں
4. نتائج دیکھیں اور CSV ڈاؤن لوڈ کریں

### مستقبل میں دوبارہ استعمال

- GitHub سے `git clone` یا `git pull`
- ہر نئے PC پر: venv + `pip install` + `playwright install chromium`
- ہر بار: `streamlit run app.py`

---

## 👤 Author

**GitHub:** [@ah0890](https://github.com/ah0890)

---

## 📄 License

Use responsibly. Add a license file (e.g. MIT) if you plan to share publicly.
