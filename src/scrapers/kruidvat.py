"""Scraper for Kruidvat Belgium promotional deals and Club discounts."""

import json
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category
from src.scrapers.models import PromoItem
from src.scrapers.generic import parse_price, prices_from_text

logger = logging.getLogger(__name__)

KRUIDVAT_BASE_URL = "https://www.kruidvat.be"
KRUIDVAT_PROMOS_URL = "https://www.kruidvat.be/nl/acties"
KRUIDVAT_API_URL = "https://www.kruidvat.be/api/v2/kvb/products/search?fields=FULL&query=:relevance:allCategories:promotions&pageSize=48"


class KruidvatScraper(BaseScraper):
    def __init__(self, api_url: str = KRUIDVAT_API_URL, web_url: str = KRUIDVAT_PROMOS_URL):
        super().__init__(store_id="kruidvat", name="Kruidvat")
        self.api_url = api_url
        self.web_url = web_url

    async def fetch_promos(self) -> List[PromoItem]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7",
        }
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            # 1. Attempt Hybris JSON API first
            try:
                async with session.get(self.api_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200 and "json" in resp.headers.get("Content-Type", ""):
                        data = await resp.json()
                        items = self.parse_json_api(data)
                        if items:
                            logger.info(f"Kruidvat API returned {len(items)} promos")
                            return items
            except Exception as e:
                logger.debug(f"Kruidvat API fetch error: {e}")

            # 2. Fallback to HTML promotional landing page
            try:
                async with session.get(self.web_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        html = await resp.text(errors="ignore")
                        return self.parse_html(html)
            except Exception as err:
                logger.error(f"Error scraping Kruidvat HTML: {err}")

        return []

    def parse_json_api(self, data: dict) -> List[PromoItem]:
        items: List[PromoItem] = []
        products = data.get("products", [])
        for prod in products:
            name = prod.get("name")
            if not name or len(name) < 3:
                continue

            code = prod.get("code", "")
            price_info = prod.get("price", {})
            promo_price = parse_price(price_info.get("value"))

            # Extract promotion text (1+1 gratis, -50%, etc.)
            discount_text = "PROMO"
            promos_list = prod.get("potentialPromotions") or prod.get("promotions") or []
            if promos_list and isinstance(promos_list, list):
                first_promo = promos_list[0]
                if isinstance(first_promo, dict):
                    discount_text = first_promo.get("description") or first_promo.get("name") or "PROMO"

            # Image
            img_url = None
            images = prod.get("images", [])
            for img in images:
                if img.get("format") in ("product", "zoom", "thumbnail") or img.get("imageType") == "PRIMARY":
                    raw_img = img.get("url")
                    if raw_img:
                        img_url = urljoin(KRUIDVAT_BASE_URL, raw_img)
                        break

            # Product URL
            deal_url = None
            raw_url = prod.get("url")
            if raw_url:
                deal_url = urljoin(KRUIDVAT_BASE_URL, raw_url)

            summary = prod.get("summary") or prod.get("description") or ""

            item = PromoItem(
                store_id="kruidvat",
                external_id=self.stable_external_id("kruidvat", name, code or deal_url or name),
                title=name[:240],
                description=summary[:500],
                original_price=None,
                promo_price=promo_price,
                discount_text=discount_text,
                image_url=img_url,
                deal_url=deal_url,
                category_id=infer_category(name, summary),
                loyalty_card="Kruidvat Club",
            )
            items.append(item)
        return items

    def parse_html(self, html: str) -> List[PromoItem]:
        items: List[PromoItem] = []
        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select("[class*='product-card'], [class*='ProductCard'], .product-item, .card")
        for card in cards:
            title_elem = card.select_one("h3, h2, [class*='title'], [class*='name']")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            if len(title) < 3 or title.lower() in ("kruidvat", "promoties", "aanbiedingen"):
                continue

            prices = prices_from_text(card.get_text())
            promo_price = prices[0] if prices else None
            orig_price = max(prices) if len(prices) > 1 else None
            if promo_price and orig_price and orig_price == promo_price:
                orig_price = None

            if promo_price is None:
                continue

            # Promo badge
            badge_elem = card.select_one("[class*='badge'], [class*='promo'], [class*='discount'], [class*='tag']")
            disc_text = badge_elem.get_text(strip=True) if badge_elem else "Actie"

            img_elem = card.select_one("img")
            img_url = None
            if img_elem:
                raw_src = img_elem.get("src") or img_elem.get("data-src")
                if raw_src:
                    img_url = urljoin(KRUIDVAT_BASE_URL, raw_src)

            link_elem = card.find("a")
            deal_url = None
            if link_elem and link_elem.get("href"):
                deal_url = urljoin(KRUIDVAT_BASE_URL, link_elem.get("href"))

            items.append(
                PromoItem(
                    store_id="kruidvat",
                    external_id=self.stable_external_id("kruidvat", title, deal_url or title),
                    title=title[:240],
                    description="Kruidvat actie",
                    original_price=orig_price,
                    promo_price=promo_price,
                    discount_text=disc_text,
                    image_url=img_url,
                    deal_url=deal_url,
                    category_id=infer_category(title, disc_text),
                    loyalty_card="Kruidvat Club",
                )
            )
        return items
