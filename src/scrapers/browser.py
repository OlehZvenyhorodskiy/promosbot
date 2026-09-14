"""Browser fallback for retailer pages that render promotions in JavaScript.

The normal HTTP scrapers stay the fast path. This module is deliberately a
fallback: it shares one Chromium process, limits concurrent pages, waits for
lazy-loaded product tiles, and feeds the resulting DOM back through the same
validated parser used by the HTTP path.
"""

import asyncio
import logging
from typing import List, Optional

from src.scrapers.generic import GenericRetailerScraper
from src.scrapers.models import PromoItem

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import Browser, Playwright, async_playwright
except ImportError:  # pragma: no cover - exercised only in minimal local envs
    Browser = None
    Playwright = None
    async_playwright = None


class _BrowserRuntime:
    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()
        # Chromium pages are memory-heavy in Cloud Run. One rendered retailer
        # at a time keeps the bot and SQLite process well below the limit.
        self._semaphore = asyncio.Semaphore(1)

    async def get_browser(self):
        if async_playwright is None:
            return None
        async with self._lock:
            if self._browser is None:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
        return self._browser

    async def close(self) -> None:
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None


_runtime = _BrowserRuntime()


class BrowserRetailerScraper(GenericRetailerScraper):
    """Render one official retailer page when plain HTTP cannot expose offers."""

    async def fetch_promos(self) -> List[PromoItem]:
        browser = await _runtime.get_browser()
        if browser is None:
            logger.warning("Browser scraper unavailable for %s: Playwright is not installed", self.name)
            return []

        async with _runtime._semaphore:
            context = await browser.new_context(
                locale="nl-BE",
                viewport={"width": 1440, "height": 1200},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            try:
                await page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in {"image", "font", "media"}
                    else route.continue_(),
                )
                await page.goto(self.url, wait_until="domcontentloaded", timeout=45_000)
                await self._dismiss_cookie_dialog(page)

                # Retailers commonly lazy-load the promotion grid as the user
                # scrolls. A few bounded scrolls are enough without keeping an
                # infinite page alive.
                for _ in range(12):
                    await page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 0.9, 900))")
                    await page.wait_for_timeout(600)
                await page.wait_for_timeout(2_000)

                html = await page.content()
                items = self.parse_html(html, prefer_cards=True)
                logger.info("Browser scraper %s rendered %s items", self.name, len(items))
                return items
            except Exception as exc:
                logger.warning("Browser scraper %s failed: %s", self.name, exc)
                return []
            finally:
                try:
                    await context.close()
                except Exception:
                    # Cloud Run can terminate an instance while a page is
                    # waiting on a retailer. The next instance starts cleanly.
                    pass

    @staticmethod
    async def _dismiss_cookie_dialog(page) -> None:
        for selector in (
            "button:has-text('Akkoord')",
            "button:has-text('Accepteren')",
            "button:has-text('Accept')",
            "button:has-text('Tout accepter')",
            "[id*='accept']",
        ):
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=500):
                    await locator.click(timeout=1_000)
                    return
            except Exception:
                continue


async def close_browser_runtime() -> None:
    await _runtime.close()
