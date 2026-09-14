"""Specialized scraper for Lidl Belgium deals and Lidl Plus promotions."""

import logging
from typing import List, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category
from src.scrapers.models import PromoItem
from src.scrapers.generic import GenericRetailerScraper, parse_price, prices_from_text

logger = logging.getLogger(__name__)

LIDL_URL = "https://www.lidl.be/"


class LidlScraper(BaseScraper):
    def __init__(self, url: str = LIDL_URL):
        super().__init__(store_id="lidl", name="Lidl")
        self.url = url
        self._generic = GenericRetailerScraper("lidl", "Lidl", url, ssl_verify=False)

    async def fetch_promos(self) -> List[PromoItem]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7",
        }
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status >= 400:
                        logger.warning(f"Lidl scraper returned HTTP {resp.status}")
                        return []
                    html = await resp.text(errors="ignore")
                    return self.parse_html(html)
        except Exception as err:
            logger.error(f"Error scraping Lidl: {err}")
            return []

    def parse_html(self, html: str) -> List[PromoItem]:
        items = self._generic.parse_html(html)
        enhanced: List[PromoItem] = []
        for item in items:
            item.loyalty_card = "Lidl Plus"
            enhanced.append(item)

        if enhanced:
            return enhanced

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("[class*='product-grid-box'], [class*='grid-box'], article, .product")
        for card in cards:
            title_elem = card.select_one("h3, h2, [class*='title']")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            if len(title) < 3 or "lidl" in title.lower():
                continue

            prices = prices_from_text(card.get_text())
            promo_price = prices[0] if prices else None
            orig_price = max(prices) if len(prices) > 1 else None
            if promo_price and orig_price and orig_price == promo_price:
                orig_price = None

            if promo_price is None:
                continue

            badge_elem = card.select_one("[class*='badge'], [class*='discount'], [class*='tag']")
            disc_text = badge_elem.get_text(strip=True) if badge_elem else "Lidl Plus Deal"

            link_elem = card.find("a")
            deal_url = urljoin(self.url, link_elem.get("href")) if link_elem and link_elem.get("href") else None

            img_elem = card.select_one("img")
            img_url = urljoin(self.url, img_elem.get("src")) if img_elem and img_elem.get("src") else None

            item = PromoItem(
                store_id="lidl",
                external_id=self.stable_external_id("lidl", title, deal_url or title),
                title=title[:240],
                description="Lidl actie",
                original_price=orig_price,
                promo_price=promo_price,
                discount_text=disc_text,
                image_url=img_url,
                deal_url=deal_url,
                category_id=infer_category(title, disc_text),
                loyalty_card="Lidl Plus",
            )
            enhanced.append(item)

        return enhanced
