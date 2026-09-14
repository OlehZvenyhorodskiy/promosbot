"""Specialized scraper for Carrefour Belgium promotions and Bonus Card deals."""

import json
import logging
import re
from typing import List, Optional
import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category, generate_fingerprint
from src.scrapers.models import PromoItem

logger = logging.getLogger(__name__)


class CarrefourScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_id="carrefour", name="Carrefour Belgium")
        self.base_url = "https://www.carrefour.be"
        self.url = f"{self.base_url}/nl/promoties"
        self.loyalty_card = "Bonus Card"

    async def fetch_promos(self) -> List[PromoItem]:
        """
        Fetches promotions from Carrefour Belgium with WAF headers,
        JSON-LD parsing, HTML fallback, and Publitas leaflet fallback.
        """
        items: List[PromoItem] = []

        # 1. Realistic HTTP request to bypass WAF
        try:
            html_items = await self._fetch_with_realistic_headers()
            if html_items:
                items.extend(html_items)
                logger.info(f"Carrefour HTTP fetched {len(html_items)} items")
        except Exception as err:
            logger.debug(f"Carrefour HTTP fetch error: {err}")

        # 2. Leaflet fallback if web requests returned few items
        if len(items) < 10:
            try:
                leaflet_items = await self._fetch_from_leaflets()
                if leaflet_items:
                    items.extend(leaflet_items)
                    logger.info(f"Carrefour leaflets fetched {len(leaflet_items)} items")
            except Exception as err:
                logger.debug(f"Carrefour leaflet fetch error: {err}")

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

    async def _fetch_with_realistic_headers(self) -> List[PromoItem]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Cache-Control": "max-age=0",
            "Referer": "https://www.google.com/",
        }

        connector = aiohttp.TCPConnector(ssl=True, limit=10, limit_per_host=5)
        async with aiohttp.ClientSession(
            connector=connector,
            headers=headers,
            max_field_size=65536,
        ) as session:
            try:
                async with session.get(self.base_url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
                    pass
            except Exception:
                pass

            async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=25), allow_redirects=True) as resp:
                if resp.status >= 400:
                    return []
                html = await resp.text(errors="ignore")
                return self._parse_html_with_json_ld(html)

    def _parse_html_with_json_ld(self, html: str) -> List[PromoItem]:
        soup = BeautifulSoup(html, "html.parser")
        items = []

        # 1. Parse JSON-LD scripts
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                entries = data if isinstance(data, list) else [data]
                for entry in entries:
                    if entry.get("@type") == "Product" or "offers" in entry:
                        item = self._parse_json_ld_product(entry)
                        if item:
                            items.append(item)

                    if entry.get("@type") == "ItemList":
                        for item_entry in entry.get("itemListElement", []):
                            target = item_entry.get("item") if isinstance(item_entry, dict) and "item" in item_entry else item_entry
                            if isinstance(target, dict):
                                item = self._parse_json_ld_product(target)
                                if item:
                                    items.append(item)
            except Exception:
                continue

        if items:
            return items

        # 2. Fallback to HTML product cards
        cards = soup.select(".product-card, .promo-item, [data-qa*='product'], article")
        for card in cards[:50]:
            item = self._parse_html_card(card)
            if item:
                items.append(item)

        return items

    def _parse_json_ld_product(self, entry: dict) -> Optional[PromoItem]:
        name = entry.get("name")
        if not name or len(name) < 2:
            return None

        offers = entry.get("offers", {})
        price = None
        if isinstance(offers, dict):
            price = offers.get("price")
        elif isinstance(offers, list) and offers:
            price = offers[0].get("price")

        try:
            promo_price = float(price) if price else None
        except (ValueError, TypeError):
            promo_price = None

        if promo_price is None:
            return None

        image = entry.get("image")
        image_url = image if isinstance(image, str) else (image[0] if isinstance(image, list) and image else None)
        sku = str(entry.get("sku") or entry.get("productID") or "")
        deal_url = entry.get("url") or self.url
        if deal_url and deal_url.startswith("/"):
            deal_url = f"{self.base_url}{deal_url}"

        fp = generate_fingerprint(
            store_id="carrefour",
            title=name,
            promo_price=promo_price,
        )

        return PromoItem(
            store_id="carrefour",
            external_id=f"carrefour_{sku or fp[:8]}",
            fingerprint=fp,
            title=name,
            description=entry.get("description", ""),
            promo_price=promo_price,
            discount_text="Bonus Actie",
            image_url=image_url,
            deal_url=deal_url,
            category_id=infer_category(name, entry.get("description", "")),
            loyalty_card="Bonus Card",
            source_type="json_ld",
        )

    def _parse_html_card(self, card) -> Optional[PromoItem]:
        title_elem = card.select_one("h2, h3, .product-title, .title")
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        if len(title) < 3:
            return None

        price_elem = card.select_one(".price, [class*='price']")
        price_val = None
        if price_elem:
            m = re.search(r"(\d+[\.,]\d{2})", price_elem.get_text())
            if m:
                try:
                    price_val = float(m.group(1).replace(",", "."))
                except ValueError:
                    pass

        if price_val is None:
            return None

        img_elem = card.select_one("img")
        img = img_elem.get("src") if img_elem else None
        if img and img.startswith("/"):
            img = f"{self.base_url}{img}"

        link_elem = card.select_one("a[href]")
        deal_url = link_elem.get("href") if link_elem else self.url
        if deal_url and deal_url.startswith("/"):
            deal_url = f"{self.base_url}{deal_url}"

        fp = generate_fingerprint(
            store_id="carrefour",
            title=title,
            promo_price=price_val,
        )

        return PromoItem(
            store_id="carrefour",
            external_id=f"carrefour_{fp[:8]}",
            fingerprint=fp,
            title=title,
            promo_price=price_val,
            discount_text="Carrefour Bonus",
            image_url=img,
            deal_url=deal_url,
            category_id=infer_category(title),
            loyalty_card="Bonus Card",
            source_type="html",
        )

    async def _fetch_from_leaflets(self) -> List[PromoItem]:
        try:
            from src.scrapers.leaflets.publitas import PublitasLeafletExtractor
            extractor = PublitasLeafletExtractor("carrefour", "carrefour-belgie")
            pubs = await extractor.get_active_publications()
            items = []
            for pub in pubs[:3]:
                slug = pub.get("slug") or str(pub.get("id", ""))
                if slug:
                    extracted = await extractor.extract_from_publication_slug(slug)
                    items.extend(extracted)
            return items
        except Exception as err:
            logger.debug(f"Carrefour leaflet fallback failed: {err}")
            return []
