"""Scraper for Action Belgium weekly deals (Weekactie) and Action Club discounts."""

import json
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category, generate_fingerprint
from src.scrapers.models import PromoItem
from src.scrapers.generic import parse_price, prices_from_text

logger = logging.getLogger(__name__)

ACTION_WEEKACTIE_URL = "https://www.action.com/nl-be/weekactie/"


class ActionScraper(BaseScraper):
    def __init__(self, url: str = ACTION_WEEKACTIE_URL):
        super().__init__(store_id="action", name="Action")
        self.url = url
        self.loyalty_card = "Action Club"

    async def fetch_promos(self) -> List[PromoItem]:
        items: List[PromoItem] = []

        # 1. HTML and Next.js parsing
        try:
            html_items = await self._fetch_from_html()
            if html_items:
                items.extend(html_items)
                logger.info(f"Action HTML fetched {len(html_items)} items")
        except Exception as err:
            logger.debug(f"Action HTML fetch error: {err}")

        # 2. Leaflet fallback
        if len(items) < 10:
            try:
                leaflet_items = await self._fetch_from_leaflets()
                if leaflet_items:
                    items.extend(leaflet_items)
                    logger.info(f"Action leaflets fetched {len(leaflet_items)} items")
            except Exception as err:
                logger.debug(f"Action leaflet fetch error: {err}")

        # 3. Tiendeo aggregator fallback
        if len(items) < 10:
            try:
                tiendeo_items = await self._fetch_from_tiendeo()
                if tiendeo_items:
                    items.extend(tiendeo_items)
                    logger.info(f"Action Tiendeo fetched {len(tiendeo_items)} items")
            except Exception as err:
                logger.debug(f"Action Tiendeo fetch error: {err}")

        # Deduplication by fingerprint
        seen = set()
        unique_items = []
        for item in items:
            if item.fingerprint and item.fingerprint not in seen:
                seen.add(item.fingerprint)
                unique_items.append(item)
            elif not item.fingerprint:
                unique_items.append(item)

        return unique_items

    async def _fetch_from_html(self) -> List[PromoItem]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7",
        }
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status >= 400:
                    return []
                html = await resp.text(errors="ignore")
                return self.parse_html(html)

    def parse_html(self, html: str) -> List[PromoItem]:
        items: List[PromoItem] = []
        soup = BeautifulSoup(html, "html.parser")

        # 1. Try __NEXT_DATA__
        next_script = soup.find("script", id="__NEXT_DATA__")
        if next_script and next_script.string:
            try:
                data = json.loads(next_script.string)
                items = self._parse_next_data(data)
                if items:
                    return items
            except Exception as e:
                logger.debug(f"Action __NEXT_DATA__ parsing error: {e}")

        # 2. Try HTML product cards
        cards = soup.select("[class*='product-card'], [class*='ProductCard'], .action-product, article, .card")
        for card in cards:
            title_elem = card.select_one("h3, h2, [class*='title'], [class*='heading']")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            if len(title) < 3 or title.lower() in ("action", "weekactie", "aanbiedingen"):
                continue

            promo_price: Optional[float] = None
            orig_price: Optional[float] = None

            current_elem = card.select_one("[class*='current'], [class*='promo'], [class*='price-wrapper'], .price")
            if current_elem:
                promo_price = parse_price(current_elem.get_text())

            strike_elem = card.select_one("[class*='strike'], [class*='original'], [class*='old'], [class*='before'], s, del")
            if strike_elem:
                orig_price = parse_price(strike_elem.get_text())

            if promo_price is None:
                card_prices = prices_from_text(card.get_text())
                if card_prices:
                    promo_price = card_prices[0]
                    if len(card_prices) > 1:
                        orig_price = max(card_prices)
                        promo_price = min(card_prices)

            if promo_price is None and orig_price is None:
                continue

            img_elem = card.select_one("img")
            img_url = None
            if img_elem:
                img_url = img_elem.get("src") or img_elem.get("data-src")
                if img_url:
                    img_url = urljoin(self.url, img_url)

            link_elem = card.find("a")
            deal_url = None
            if link_elem and link_elem.get("href"):
                deal_url = urljoin(self.url, link_elem.get("href"))

            discount_badge = card.select_one("[class*='badge'], [class*='discount'], [class*='label']")
            disc_text = discount_badge.get_text(strip=True) if discount_badge else "Weekactie"

            fp = generate_fingerprint(
                store_id="action",
                title=title,
                promo_price=promo_price,
            )

            item = PromoItem(
                store_id="action",
                external_id=f"action_{fp[:8]}",
                fingerprint=fp,
                title=title[:240],
                description="Action Weekactie aanbieding",
                original_price=orig_price,
                promo_price=promo_price,
                discount_text=disc_text,
                image_url=img_url,
                deal_url=deal_url,
                category_id=infer_category(title, "action weekactie"),
                loyalty_card="Action Club",
                source_type="html",
            )
            items.append(item)

        return items

    def _parse_next_data(self, data: dict) -> List[PromoItem]:
        items: List[PromoItem] = []

        def walk(val):
            if isinstance(val, dict):
                title = val.get("title") or val.get("name") or val.get("webTitle")
                price = val.get("price") or val.get("promoPrice") or val.get("currentPrice")
                if title and price and isinstance(title, str) and len(title) > 3:
                    parsed_promo = parse_price(price)
                    orig = parse_price(val.get("oldPrice") or val.get("strikePrice") or val.get("recommendedPrice"))
                    if parsed_promo:
                        web_url = val.get("url") or val.get("webPath") or val.get("href")
                        full_url = urljoin(self.url, web_url) if web_url else None
                        img = val.get("image") or val.get("imageUrl") or val.get("assetUrl")
                        full_img = urljoin(self.url, img) if img and isinstance(img, str) else None

                        fp = generate_fingerprint(
                            store_id="action",
                            title=title,
                            promo_price=parsed_promo,
                        )
                        items.append(
                            PromoItem(
                                store_id="action",
                                external_id=f"action_{fp[:8]}",
                                fingerprint=fp,
                                title=title[:240],
                                description=str(val.get("description") or "Action Weekactie")[:500],
                                original_price=orig,
                                promo_price=parsed_promo,
                                discount_text=str(val.get("discountBadge") or "Weekactie"),
                                image_url=full_img,
                                deal_url=full_url,
                                category_id=infer_category(title, str(val.get("category", ""))),
                                loyalty_card="Action Club",
                                source_type="next_data",
                            )
                        )
                for v in val.values():
                    walk(v)
            elif isinstance(val, list):
                for v in val:
                    walk(v)

        walk(data)
        return items

    async def _fetch_from_leaflets(self) -> List[PromoItem]:
        try:
            from src.scrapers.leaflets.publitas import PublitasLeafletExtractor
            extractor = PublitasLeafletExtractor("action", "action-belgie")
            pubs = await extractor.get_active_publications()
            items = []
            for pub in pubs[:3]:
                slug = pub.get("slug") or str(pub.get("id", ""))
                if slug:
                    extracted = await extractor.extract_from_publication_slug(slug)
                    items.extend(extracted)
            return items
        except Exception as err:
            logger.debug(f"Action leaflet fallback failed: {err}")
            return []

    async def _fetch_from_tiendeo(self) -> List[PromoItem]:
        try:
            from src.scrapers.leaflets.tiendeo import TiendeoAggregator
            aggregator = TiendeoAggregator()
            return await aggregator.fetch_retailer_deals("action")
        except Exception as err:
            logger.debug(f"Action Tiendeo fallback failed: {err}")
            return []
