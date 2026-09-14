"""Specialized scraper for Lidl Belgium deals and Lidl Plus promotions."""

import logging
from typing import List, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category, generate_fingerprint, get_ssl_context
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
        """
        Fetches promotions from Lidl with max_field_size=65536 to prevent
        Akamai header size overflow errors, with leaflet fallback.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        try:
            connector = aiohttp.TCPConnector(ssl=get_ssl_context(verify=True), limit=10, limit_per_host=5)
            async with aiohttp.ClientSession(
                connector=connector,
                headers=headers,
                max_field_size=65536,
                max_line_size=65536,
            ) as session:
                async with session.get(
                    self.url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    allow_redirects=True,
                ) as resp:
                    if resp.status >= 400:
                        logger.warning(f"Lidl scraper returned HTTP {resp.status}, trying leaflet fallback")
                        return await self._fetch_from_leaflets()
                    html = await resp.text(errors="ignore")
                    items = self.parse_html(html)
                    if not items or len(items) < 5:
                        leaflet_items = await self._fetch_from_leaflets()
                        items.extend(leaflet_items)
                    return items
        except Exception as err:
            logger.error(f"Error scraping Lidl: {err}, falling back to leaflets")
            return await self._fetch_from_leaflets()

    def parse_html(self, html: str) -> List[PromoItem]:
        items = self._generic.parse_html(html)
        enhanced: List[PromoItem] = []
        for item in items:
            item.loyalty_card = "Lidl Plus"
            item.fingerprint = generate_fingerprint(
                store_id="lidl",
                title=item.title,
                promo_price=item.promo_price,
                valid_from=item.valid_from,
                valid_until=item.valid_until,
            )
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

            fp = generate_fingerprint(
                store_id="lidl",
                title=title,
                promo_price=promo_price,
            )

            item = PromoItem(
                store_id="lidl",
                external_id=f"lidl_{fp[:8]}",
                fingerprint=fp,
                title=title[:240],
                description="Lidl actie",
                original_price=orig_price,
                promo_price=promo_price,
                discount_text=disc_text,
                image_url=img_url,
                deal_url=deal_url,
                category_id=infer_category(title, disc_text),
                loyalty_card="Lidl Plus",
                source_type="html",
            )
            enhanced.append(item)

        return enhanced

    async def _fetch_from_leaflets(self) -> List[PromoItem]:
        """Fallback to extract promotions from Lidl digital brochures."""
        try:
            from src.scrapers.leaflets.publitas import PublitasLeafletExtractor
            extractor = PublitasLeafletExtractor("lidl", "lidl-belgie")
            pubs = await extractor.get_active_publications()
            items = []
            for pub in pubs[:3]:
                slug = pub.get("slug") or str(pub.get("id", ""))
                if slug:
                    extracted = await extractor.extract_from_publication_slug(slug)
                    items.extend(extracted)
            if items:
                logger.info(f"Lidl leaflets extracted {len(items)} items")
            return items
        except Exception as err:
            logger.debug(f"Lidl leaflet fallback failed: {err}")
            return []
