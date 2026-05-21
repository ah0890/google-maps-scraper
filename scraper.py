"""
Google Maps business scraper using Playwright async API.
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

from fake_useragent import UserAgent
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from utils import (
    LOGGER,
    SCREENSHOTS_DIR,
    ScraperState,
    deduplicate_results,
    random_delay,
    save_export,
)

ua_generator = UserAgent()


class GoogleMapsScraper:
    """Async Playwright scraper for Google Maps business listings."""

    def __init__(
        self,
        keyword: str,
        locations: list[str],
        settings: dict[str, Any],
        state: ScraperState,
    ) -> None:
        self.keyword = keyword.strip()
        self.locations = locations
        self.settings = settings
        self.state = state
        self.max_per_location = int(settings.get("max_results", 10))
        self.headless = bool(settings.get("headless", True))
        self.delay_min = float(settings.get("delay_min", 1.5))
        self.delay_max = float(settings.get("delay_max", 3.5))
        self.concurrent_tabs = max(1, min(int(settings.get("concurrent_tabs", 1)), 3))
        self.proxy = (settings.get("proxy") or "").strip()
        self.export_format = settings.get("export_format", "CSV")
        self.max_retries = int(settings.get("max_retries", 3))

    async def run(self) -> list[dict[str, Any]]:
        self.state.reset()
        with self.state._lock:
            self.state.is_running = True
            self.state.stop_requested = False
            self.state.is_paused = False
            self.state.locations_total = len(self.locations)
            self.state.businesses_target = len(self.locations) * self.max_per_location
            self.state.current_keyword = self.keyword

        all_results: list[dict[str, Any]] = []

        try:
            async with async_playwright() as pw:
                browser = await self._launch_browser(pw)
                try:
                    semaphore = asyncio.Semaphore(self.concurrent_tabs)

                    async def scrape_one(loc: str) -> list[dict[str, Any]]:
                        async with semaphore:
                            if self.state.should_stop():
                                return []
                            return await self._scrape_location(browser, loc)

                    tasks = [scrape_one(loc) for loc in self.locations]
                    batches = await asyncio.gather(*tasks, return_exceptions=True)

                    for i, batch in enumerate(batches):
                        if isinstance(batch, Exception):
                            self.state.add_error(f"Location error: {batch}")
                            LOGGER.exception("Location scrape failed")
                        else:
                            all_results.extend(batch)
                        self.state.update_progress(locations_done=i + 1)

                finally:
                    await browser.close()
        except Exception as exc:
            self.state.add_error(f"Fatal scraper error: {exc}")
            LOGGER.exception("Scraper run failed")
        finally:
            self.state.set_running(False)

        all_results = deduplicate_results(all_results)
        if all_results and self.settings.get("auto_save", True):
            import pandas as pd
            from utils import rows_to_dataframe

            df = rows_to_dataframe(all_results)
            save_export(df, self.export_format)

        return all_results

    async def _launch_browser(self, pw: Playwright) -> Browser:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        proxy_config = None
        if self.proxy:
            proxy_config = {"server": self.proxy}

        browser = await pw.chromium.launch(
            headless=self.headless,
            args=launch_args,
            proxy=proxy_config,
        )
        return browser

    async def _new_context(self, browser: Browser) -> BrowserContext:
        user_agent = ua_generator.random
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1366, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
        )
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            """
        )
        return context

    async def _scrape_location(self, browser: Browser, location: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        context = await self._new_context(browser)
        page = await context.new_page()
        page.set_default_timeout(45000)

        with self.state._lock:
            self.state.current_location = location

        try:
            query = f"{self.keyword} in {location}"
            url = f"https://www.google.com/maps/search/{quote_plus(query)}"
            self.state.update_progress(message=f"Searching: {query}")

            for attempt in range(1, self.max_retries + 1):
                if self.state.should_stop():
                    return results
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                    await asyncio.sleep(random_delay(2.0, 4.0))
                    await self._dismiss_consent(page)
                    await self._wait_for_feed(page)
                    break
                except Exception as exc:
                    if attempt == self.max_retries:
                        raise
                    self.state.update_progress(message=f"Retry {attempt}/{self.max_retries} for {location}")
                    await asyncio.sleep(random_delay(2, 5))
                    LOGGER.warning("Navigation retry %s: %s", attempt, exc)

            listing_urls = await self._collect_listing_urls(page, self.max_per_location)
            self.state.update_progress(
                message=f"{location}: found {len(listing_urls)} listings"
            )

            for idx, listing_url in enumerate(listing_urls):
                if self.state.should_stop():
                    break
                self.state.wait_if_paused()

                row = await self._scrape_listing(
                    browser, listing_url, location, idx + 1, len(listing_urls)
                )
                if row:
                    results.append(row)
                    self.state.add_result(row)
                await asyncio.sleep(random_delay(self.delay_min, self.delay_max))

        except Exception as exc:
            msg = f"{location}: {exc}"
            self.state.add_error(msg)
            await self._capture_error_screenshot(page, location)
            LOGGER.exception("Failed location %s", location)
        finally:
            await context.close()

        return results

    async def _scrape_listing(
        self,
        browser: Browser,
        url: str,
        location: str,
        index: int,
        total: int,
    ) -> dict[str, Any] | None:
        context = await self._new_context(browser)
        page = await context.new_page()
        page.set_default_timeout(35000)

        try:
            self.state.update_progress(
                message=f"{location}: detail {index}/{total}"
            )
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(random_delay(1.2, 2.5))
            await self._human_mouse_wiggle(page)
            await self._dismiss_consent(page)

            data = await self._extract_business_details(page)
            data.update(
                {
                    "location": location,
                    "keyword": self.keyword,
                    "scraped_at": datetime.now().isoformat(timespec="seconds"),
                    "status": "success",
                }
            )
            return data
        except Exception as exc:
            self.state.add_error(f"Listing failed ({url}): {exc}")
            await self._capture_error_screenshot(page, f"{location}_{index}")
            return {
                "location": location,
                "keyword": self.keyword,
                "business_name": "",
                "address": "",
                "website": "",
                "phone": "",
                "rating": "",
                "reviews_count": "",
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "status": f"error: {exc}",
            }
        finally:
            await context.close()

    async def _dismiss_consent(self, page: Page) -> None:
        selectors = [
            'button:has-text("Accept all")',
            'button:has-text("Reject all")',
            'button[aria-label="Accept all"]',
            'form[action*="consent"] button',
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await asyncio.sleep(0.8)
                    return
            except Exception:
                continue

    async def _wait_for_feed(self, page: Page) -> None:
        feed_selectors = [
            'div[role="feed"]',
            'div[aria-label*="Results"]',
            "div.m6QErb",
        ]
        for sel in feed_selectors:
            try:
                await page.wait_for_selector(sel, timeout=15000)
                return
            except Exception:
                continue
        await asyncio.sleep(2)

    async def _collect_listing_urls(self, page: Page, max_results: int) -> list[str]:
        """Scroll results feed and collect unique place URLs."""
        seen: set[str] = set()
        urls: list[str] = []
        stagnant_rounds = 0

        feed = page.locator('div[role="feed"]').first
        if await feed.count() == 0:
            feed = page.locator("div.m6QErb").first

        while len(urls) < max_results and stagnant_rounds < 6:
            if self.state.should_stop():
                break
            self.state.wait_if_paused()

            anchors = page.locator('a[href*="/maps/place"]')
            count = await anchors.count()
            for i in range(count):
                href = await anchors.nth(i).get_attribute("href")
                if not href or "/maps/place" not in href:
                    continue
                clean = href.split("&")[0]
                if clean not in seen:
                    seen.add(clean)
                    urls.append(clean)
                    if len(urls) >= max_results:
                        break

            prev_len = len(urls)
            await self._human_scroll_feed(page, feed)
            await asyncio.sleep(random_delay(0.8, 1.6))

            if len(urls) == prev_len:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0

        return urls[:max_results]

    async def _human_scroll_feed(self, page: Page, feed) -> None:
        try:
            if await feed.count() > 0:
                await feed.evaluate(
                    "el => { el.scrollTop = el.scrollTop + (280 + Math.random() * 220); }"
                )
            else:
                await page.mouse.wheel(0, random.randint(350, 650))
        except Exception:
            await page.mouse.wheel(0, random.randint(350, 650))

    async def _human_mouse_wiggle(self, page: Page) -> None:
        try:
            for _ in range(random.randint(2, 4)):
                x = random.randint(200, 1100)
                y = random.randint(150, 700)
                await page.mouse.move(x, y, steps=random.randint(5, 12))
                await asyncio.sleep(random.uniform(0.05, 0.15))
        except Exception:
            pass

    async def _extract_business_details(self, page: Page) -> dict[str, str]:
        name = await self._first_text(
            page,
            [
                "h1.DUwDvf",
                "h1.fontHeadlineLarge",
                "h1 span",
                "h1",
            ],
        )
        address = await self._extract_by_labels(page, ["Address", "address"])
        if not address:
            address = await self._first_text(
                page,
                [
                    'button[data-item-id="address"]',
                    'div[data-item-id="address"]',
                ],
            )

        website = await self._extract_link(page, 'a[data-item-id="authority"]')
        if not website:
            website = await self._extract_link(page, 'a[aria-label*="Website"]')

        phone = await self._extract_by_labels(page, ["Phone", "phone"])
        if not phone:
            phone = await self._first_text(
                page,
                [
                    'button[data-item-id^="phone"]',
                    'button[aria-label*="Phone"]',
                ],
            )

        rating = await self._first_text(
            page,
            [
                "div.F7nice span span",
                'span[aria-label*="stars"]',
                "span.ceNzKf",
            ],
        )
        if rating:
            rating = rating.split()[0]

        reviews = await self._extract_reviews_count(page)

        return {
            "business_name": self._clean(name),
            "address": self._clean(address),
            "website": self._clean(website),
            "phone": self._clean(phone),
            "rating": self._clean(rating),
            "reviews_count": self._clean(reviews),
        }

    async def _extract_reviews_count(self, page: Page) -> str:
        candidates = [
            'button[aria-label*="reviews"]',
            'span[aria-label*="reviews"]',
            "div.F7nice",
        ]
        for sel in candidates:
            try:
                loc = page.locator(sel).first
                if await loc.count() == 0:
                    continue
                aria = await loc.get_attribute("aria-label")
                text = aria or (await loc.inner_text())
                match = re.search(r"([\d,]+)\s*review", text or "", re.I)
                if match:
                    return match.group(1).replace(",", "")
                match2 = re.search(r"\(([\d,]+)\)", text or "")
                if match2:
                    return match2.group(1).replace(",", "")
            except Exception:
                continue
        return ""

    async def _extract_by_labels(self, page: Page, labels: list[str]) -> str:
        for label in labels:
            try:
                loc = page.locator(f'button[aria-label*="{label}"]').first
                if await loc.count() > 0:
                    aria = await loc.get_attribute("aria-label")
                    if aria:
                        return aria.replace(f"{label}:", "").strip()
                    return (await loc.inner_text()).strip()
            except Exception:
                continue
        return ""

    async def _extract_link(self, page: Page, selector: str) -> str:
        try:
            loc = page.locator(selector).first
            if await loc.count() > 0:
                href = await loc.get_attribute("href")
                return href or ""
        except Exception:
            pass
        return ""

    async def _first_text(self, page: Page, selectors: list[str]) -> str:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    text = (await loc.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                continue
        return ""

    async def _capture_error_screenshot(self, page: Page, label: str) -> None:
        try:
            safe = re.sub(r"[^\w\-]", "_", label)[:80]
            path = SCREENSHOTS_DIR / f"error_{safe}_{datetime.now().strftime('%H%M%S')}.png"
            await page.screenshot(path=str(path), full_page=True)
            LOGGER.info("Error screenshot saved: %s", path)
        except Exception:
            pass

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip())


def run_scraper_in_thread(
    keyword: str,
    locations: list[str],
    settings: dict[str, Any],
    state: ScraperState,
) -> None:
    """Entry point for background thread from Streamlit."""

    async def _main() -> None:
        scraper = GoogleMapsScraper(keyword, locations, settings, state)
        await scraper.run()

    try:
        asyncio.run(_main())
    except Exception as exc:
        state.add_error(str(exc))
        LOGGER.exception("Thread runner failed")
    finally:
        state.set_running(False)
