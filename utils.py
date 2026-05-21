"""
Shared utilities: paths, logging, CSV I/O, deduplication, and timing helpers.
"""

from __future__ import annotations

import csv
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Project root (directory containing app.py)
ROOT_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = ROOT_DIR / "exports"
LOGS_DIR = ROOT_DIR / "logs"
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"
ASSETS_DIR = ROOT_DIR / "assets"

for folder in (EXPORTS_DIR, LOGS_DIR, SCREENSHOTS_DIR):
    folder.mkdir(parents=True, exist_ok=True)

RESULT_COLUMNS = [
    "location",
    "keyword",
    "business_name",
    "address",
    "website",
    "phone",
    "rating",
    "reviews_count",
    "scraped_at",
    "status",
]


def setup_logger(name: str = "gmaps_scraper") -> logging.Logger:
    """Configure file + console logging."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    log_file = LOGS_DIR / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


LOGGER = setup_logger()


class ScraperState:
    """Thread-safe shared state between scraper thread and Streamlit UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.results: list[dict[str, Any]] = []
            self.errors: list[str] = []
            self.is_running = False
            self.is_paused = False
            self.stop_requested = False
            self.current_location = ""
            self.current_keyword = ""
            self.locations_total = 0
            self.locations_done = 0
            self.businesses_scraped = 0
            self.businesses_target = 0
            self.started_at: float | None = None
            self.last_message = ""
            self.progress_pct = 0.0

    def request_stop(self) -> None:
        with self._lock:
            self.stop_requested = True

    def request_pause(self) -> None:
        with self._lock:
            self.is_paused = True

    def request_resume(self) -> None:
        with self._lock:
            self.is_paused = False

    def should_stop(self) -> bool:
        with self._lock:
            return self.stop_requested

    def wait_if_paused(self) -> None:
        while True:
            with self._lock:
                if self.stop_requested:
                    return
                if not self.is_paused:
                    return
            time.sleep(0.4)

    def update_progress(
        self,
        *,
        message: str = "",
        locations_done: int | None = None,
        businesses_scraped: int | None = None,
    ) -> None:
        with self._lock:
            if message:
                self.last_message = message
            if locations_done is not None:
                self.locations_done = locations_done
            if businesses_scraped is not None:
                self.businesses_scraped = businesses_scraped

            loc_total = max(self.locations_total, 1)
            biz_target = max(self.businesses_target, 1)
            loc_pct = (self.locations_done / loc_total) * 50
            biz_pct = (self.businesses_scraped / biz_target) * 50
            self.progress_pct = min(100.0, loc_pct + biz_pct)

    def add_result(self, row: dict[str, Any]) -> None:
        with self._lock:
            self.results.append(row)
            self.businesses_scraped = len(self.results)

    def add_error(self, msg: str) -> None:
        with self._lock:
            self.errors.append(msg)
            LOGGER.error(msg)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "results": list(self.results),
                "errors": list(self.errors),
                "is_running": self.is_running,
                "is_paused": self.is_paused,
                "stop_requested": self.stop_requested,
                "current_location": self.current_location,
                "current_keyword": self.current_keyword,
                "locations_total": self.locations_total,
                "locations_done": self.locations_done,
                "businesses_scraped": self.businesses_scraped,
                "businesses_target": self.businesses_target,
                "started_at": self.started_at,
                "last_message": self.last_message,
                "progress_pct": self.progress_pct,
            }

    def set_running(self, running: bool) -> None:
        with self._lock:
            self.is_running = running
            if running:
                self.started_at = time.time()
            else:
                self.started_at = None


def random_delay(min_sec: float, max_sec: float) -> float:
    import random

    return random.uniform(min_sec, max_sec)


def sleep_delay(min_sec: float, max_sec: float) -> None:
    time.sleep(random_delay(min_sec, max_sec))


def normalize_phone(value: str) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 10:
        return value.strip()
    return value.strip()


def deduplicate_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicates by business name + address within same location."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("location", "")).lower().strip(),
            str(row.get("business_name", "")).lower().strip(),
            str(row.get("address", "")).lower().strip(),
        )
        if key in seen or not key[1]:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    df = pd.DataFrame(rows)
    for col in RESULT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[RESULT_COLUMNS]


def load_locations_csv(file_bytes: bytes) -> list[str]:
    """Parse uploaded CSV; expects a 'location' column."""
    import io

    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV is empty or has no header row.")

    field_map = {f.lower().strip(): f for f in reader.fieldnames}
    loc_key = field_map.get("location") or field_map.get("locations") or field_map.get("city")
    if not loc_key:
        raise ValueError("CSV must include a 'location' column.")

    locations: list[str] = []
    for row in reader:
        val = (row.get(loc_key) or "").strip()
        if val:
            locations.append(val)
    if not locations:
        raise ValueError("No locations found in CSV.")
    return locations


def save_export(df: pd.DataFrame, export_format: str = "CSV") -> Path:
    """Auto-save scrape results to exports folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if export_format.upper() == "XLSX":
        path = EXPORTS_DIR / f"gmaps_results_{timestamp}.xlsx"
        df.to_excel(path, index=False)
    else:
        path = EXPORTS_DIR / f"gmaps_results_{timestamp}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
    LOGGER.info("Exported %s rows to %s", len(df), path)
    return path


def compute_metrics(df: pd.DataFrame) -> dict[str, int]:
    total = len(df)
    successful = int((df["status"] == "success").sum()) if total and "status" in df.columns else total
    with_phone = int(df["phone"].astype(str).str.strip().ne("").sum()) if total else 0
    with_website = int(df["website"].astype(str).str.strip().ne("").sum()) if total else 0
    return {
        "total": total,
        "successful": successful,
        "with_phone": with_phone,
        "with_website": with_website,
    }


def estimate_eta_seconds(started_at: float | None, progress_pct: float) -> int | None:
    if not started_at or progress_pct <= 0:
        return None
    elapsed = time.time() - started_at
    remaining_pct = max(0.0, 100.0 - progress_pct)
    if progress_pct >= 99:
        return 0
    rate = elapsed / progress_pct
    return int(rate * remaining_pct)
