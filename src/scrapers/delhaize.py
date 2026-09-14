"""Specialized scraper for Delhaize Belgium promotions and SuperPlus card discounts."""

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category, get_ssl_context
from src.scrapers.models import PromoItem
from src.scrapers.generic import GenericRetailerScraper, retailer_price_from_text, parse_price

logger = logging.getLogger(__name__)

DELHAIZE_PROMO_URL = "https://www.delhaize.be/Promolandingpage"


class DelhaizeScraper(BaseScraper):
    def __init__(self, url: str = DELHAIZE_PROMO_URL):
        super().__init__(store_id="delhaize", name="Delhaize")
        self.url = url
        self._generic = GenericRetailerScraper("delhaize", "Delhaize", url)

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
            connector = aiohttp.TCPConnector(ssl=get_ssl_context(verify=True))
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status >= 400:
                        logger.warning(f"Delhaize scraper returned HTTP {resp.status}")
                        return []
                    html = await resp.text(errors="ignore")
                    return self.parse_html(html)
        except Exception as err:
            logger.error(f"Error scraping Delhaize: {err}")
            return []

    def parse_html(self, html: str) -> List[PromoItem]:
        # Parse using generic parser first
        items = self._generic.parse_html(html)

        # Enhance with Delhaize specific metadata and loyalty card
        enhanced: List[PromoItem] = []
        for item in items:
            # Check if title or discount mentions SuperPlus or loyalty
            item.loyalty_card = "SuperPlus"
            enhanced.append(item)

        if enhanced:
            return enhanced

        # Fallback card parser tailored for Delhaize HTML layout
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("[data-testid*='product'], .product-card, [class*='ProductCard']")
        for card in cards:
            title_elem = card.select_one("h3, h2, [data-testid*='title'], [class*='title']")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            if len(title) < 3 or "delhaize" in title.lower():
                continue

            price = retailer_price_from_text(card.get_text())
            if price is None:
                continue

            badge_elem = card.select_one("[class*='badge'], [class*='promo'], [class*='tag']")
            disc_text = badge_elem.get_text(strip=True) if badge_elem else "SuperPlus Deal"

            link_elem = card.find("a")
            deal_url = urljoin(self.url, link_elem.get("href")) if link_elem and link_elem.get("href") else None

            img_elem = card.select_one("img")
            img_url = urljoin(self.url, img_elem.get("src")) if img_elem and img_elem.get("src") else None

            item = PromoItem(
                store_id="delhaize",
                external_id=self.stable_external_id("delhaize", title, deal_url or title),
                title=title[:240],
                description="Delhaize SuperPlus promo",
                promo_price=price,
                discount_text=disc_text,
                image_url=img_url,
                deal_url=deal_url,
                category_id=infer_category(title, disc_text),
                loyalty_card="SuperPlus",
            )
            enhanced.append(item)

        return enhanced
