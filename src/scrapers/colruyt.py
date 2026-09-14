"""Specialized scraper for Colruyt Belgium promotions and Xtra deals."""

import json
import logging
import re
import ssl
import certifi
from typing import List, Optional
import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category, generate_fingerprint
from src.scrapers.models import PromoItem

logger = logging.getLogger(__name__)


class ColruytScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_id="colruyt", name="Colruyt")
        self.base_url = "https://www.colruyt.be"
        self.url = f"{self.base_url}/nl/acties"
        self.search_url = f"{self.base_url}/nl/search"
        self.loyalty_card = "Xtra"

    async def fetch_promos(self) -> List[PromoItem]:
        """
        Fetches promotions through Colruyt search API, HTML card parsing,
        and leaflet fallback with fingerprint deduplication.
        """
        items: List[PromoItem] = []

        # 1. Colruyt API
        try:
            api_items = await self._fetch_from_api()
            if api_items:
                items.extend(api_items)
                logger.info(f"Colruyt API returned {len(api_items)} items")
        except Exception as err:
            logger.debug(f"Colruyt API fetch failed: {err}")

        # 2. HTML parsing fallback if API returned few items
        if len(items) < 10:
            try:
                html_items = await self._fetch_from_html()
                items.extend(html_items)
            except Exception as err:
                logger.debug(f"Colruyt HTML fetch failed: {err}")

        # 3. Leaflet fallback
        if len(items) < 10:
            try:
                leaflet_items = await self._fetch_from_leaflets()
                items.extend(leaflet_items)
                if leaflet_items:
                    logger.info(f"Colruyt leaflets returned {len(leaflet_items)} items")
            except Exception as err:
                logger.debug(f"Colruyt leaflet fetch failed: {err}")

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

    async def _fetch_from_api(self) -> List[PromoItem]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7",
            "Referer": self.url,
            "X-Requested-With": "XMLHttpRequest",
        }
        params = {
            "query": "*",
            "promotion": "true",
            "pageSize": "100",
            "currentPage": "0",
        }
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.get(self.search_url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return self._parse_api_response(data)

    def _parse_api_response(self, data: dict) -> List[PromoItem]:
        items = []
        products = data.get("products") or data.get("results") or data.get("items") or []
        for product in products:
            title = product.get("name") or product.get("title") or ""
            if not title:
                continue

            price_info = product.get("price") or {}
            promo_price = None
            orig_price = None
            if isinstance(price_info, dict):
                promo_price = price_info.get("current") or price_info.get("value")
                orig_price = price_info.get("original") or price_info.get("regular")
            elif isinstance(price_info, (int, float)):
                promo_price = float(price_info)

            if promo_price is None:
                price_text = product.get("priceText") or ""
                matches = re.findall(r"(\d+[\.,]\d{2})", price_text)
                if matches:
                    try:
                        prices = [float(m.replace(",", ".")) for m in matches]
                        promo_price = min(prices)
                        orig_price = max(prices) if len(prices) > 1 else None
                    except ValueError:
                        pass

            if promo_price is None:
                continue

            discount_text = product.get("promotionLabel") or product.get("discountText") or "Rode Prijzen"
            valid_from = product.get("validFrom") or product.get("startDate")
            valid_until = product.get("validUntil") or product.get("endDate")
            image_url = product.get("imageUrl") or product.get("image")
            if image_url and image_url.startswith("/"):
                image_url = f"{self.base_url}{image_url}"

            product_id = product.get("id") or product.get("productId") or ""
            deal_url = f"{self.base_url}/nl/p/{product_id}" if product_id else self.url
            fp = generate_fingerprint(
                store_id="colruyt",
                title=title,
                promo_price=promo_price,
                valid_from=valid_from,
                valid_until=valid_until,
            )

            item = PromoItem(
                store_id="colruyt",
                external_id=f"colruyt_{product_id or fp[:8]}",
                fingerprint=fp,
                title=title[:255],
                description=product.get("description", ""),
                original_price=orig_price,
                promo_price=promo_price,
                discount_text=discount_text,
                unit_info=product.get("unit") or product.get("unitInfo"),
                image_url=image_url,
                deal_url=deal_url,
                category_id=infer_category(title, product.get("description", "")),
                valid_from=valid_from,
                valid_until=valid_until,
                loyalty_card="Xtra",
                source_type="api",
            )
            items.append(item)
        return items

    async def _fetch_from_html(self) -> List[PromoItem]:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
        }
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        items = []
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return items
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".action-card, .promo-card, [data-testid*='promo'], .m-card, article")
        for card in cards:
            title_elem = card.select_one("h2, h3, h4, .title, [class*='title']")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            desc_elem = card.select_one("p, .description, [class*='desc']")
            desc = desc_elem.get_text(strip=True) if desc_elem else ""

            badge_elem = card.select_one(".badge, .discount, [class*='discount'], [class*='promo']")
            discount_text = badge_elem.get_text(strip=True) if badge_elem else "Rode Prijzen"

            price_text = card.get_text()
            price_match = re.findall(r"€\s*(\d+[\.,]\d{2})", price_text)
            promo_price = None
            if price_match:
                try:
                    promo_price = float(price_match[0].replace(",", "."))
                except ValueError:
                    pass

            img_elem = card.select_one("img")
            img_url = img_elem.get("src") or img_elem.get("data-src") if img_elem else None
            if img_url and img_url.startswith("/"):
                img_url = f"{self.base_url}{img_url}"

            link_elem = card.select_one("a[href]")
            deal_url = link_elem.get("href") if link_elem else self.url
            if deal_url and deal_url.startswith("/"):
                deal_url = f"{self.base_url}{deal_url}"

            fp = generate_fingerprint(
                store_id="colruyt",
                title=title,
                promo_price=promo_price,
            )
            items.append(
                PromoItem(
                    store_id="colruyt",
                    external_id=f"colruyt_{fp[:8]}",
                    fingerprint=fp,
                    title=title,
                    description=desc,
                    original_price=None,
                    promo_price=promo_price,
                    discount_text=discount_text,
                    image_url=img_url,
                    deal_url=deal_url,
                    category_id=infer_category(title, desc),
                    loyalty_card="Xtra",
                    source_type="html",
                )
            )
        return items

    async def _fetch_from_leaflets(self) -> List[PromoItem]:
        try:
            from src.scrapers.leaflets.publitas import PublitasLeafletExtractor
            extractor = PublitasLeafletExtractor("colruyt", "colruyt")
            pubs = await extractor.get_active_publications()
            items = []
            for pub in pubs[:3]:
                slug = pub.get("slug") or str(pub.get("id", ""))
                if slug:
                    extracted = await extractor.extract_from_publication_slug(slug)
                    items.extend(extracted)
            return items
        except Exception as err:
            logger.debug(f"Colruyt leaflet fallback error: {err}")
            return []
