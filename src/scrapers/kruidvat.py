"""Specialized scraper for Kruidvat Belgium promotional deals and Club discounts."""

import json
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category, generate_fingerprint, get_ssl_context
from src.scrapers.models import PromoItem
from src.scrapers.generic import parse_price, prices_from_text

logger = logging.getLogger(__name__)

KRUIDVAT_BASE_URL = "https://www.kruidvat.be"
KRUIDVAT_PROMOS_URL = "https://www.kruidvat.be/nl/acties"


class KruidvatScraper(BaseScraper):
    def __init__(self, web_url: str = KRUIDVAT_PROMOS_URL):
        super().__init__(store_id="kruidvat", name="Kruidvat")
        self.api_base = f"{KRUIDVAT_BASE_URL}/api/v2/kvb"
        self.search_url = f"{self.api_base}/products/search"
        self.web_url = web_url
        self.loyalty_card = "Kruidvat Club"

    async def fetch_promos(self) -> List[PromoItem]:
        """
        Fetches promotions through Kruidvat Hybris API with pagination,
        HTML fallback, and Publitas leaflets fallback.
        """
        items: List[PromoItem] = []

        # 1. Attempt Hybris API with pagination
        try:
            api_items = await self._fetch_from_api()
            if api_items:
                items.extend(api_items)
                logger.info(f"Kruidvat API returned {len(api_items)} items")
        except Exception as err:
            logger.debug(f"Kruidvat API fetch failed: {err}")

        # 2. Fallback to HTML promotional landing page
        if len(items) < 10:
            try:
                html_items = await self._fetch_from_html()
                items.extend(html_items)
            except Exception as err:
                logger.debug(f"Kruidvat HTML fetch error: {err}")

        # 3. Leaflet fallback
        if len(items) < 10:
            try:
                leaflet_items = await self._fetch_from_leaflets()
                if leaflet_items:
                    items.extend(leaflet_items)
                    logger.info(f"Kruidvat leaflets returned {len(leaflet_items)} items")
            except Exception as err:
                logger.debug(f"Kruidvat leaflet fallback error: {err}")

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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7",
            "Referer": "https://www.kruidvat.be/aanbiedingen",
            "X-Requested-With": "XMLHttpRequest",
        }
        params = {
            "query": ":relevance:category:promotions",
            "pageSize": "100",
            "currentPage": "0",
            "sort": "relevance",
            "fields": "FULL",
        }
        items = []
        connector = aiohttp.TCPConnector(ssl=get_ssl_context(verify=True))
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            for page in range(3):
                params["currentPage"] = str(page)
                try:
                    async with session.get(
                        self.search_url,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        if resp.status != 200:
                            break
                        data = await resp.json()
                        page_items = self._parse_hybris_response(data)
                        items.extend(page_items)
                        if len(page_items) < 100:
                            break
                except Exception:
                    break
        return items

    def _parse_hybris_response(self, data: dict) -> List[PromoItem]:
        items = []
        products = data.get("products", [])
        for product in products:
            title = product.get("name") or product.get("summary") or ""
            if not title or len(title) < 2:
                continue

            price_data = product.get("price") or {}
            promo_price = None
            orig_price = None
            if isinstance(price_data, dict):
                promo_price = price_data.get("value")
                was_price = price_data.get("wasPrice") or price_data.get("previousPrice")
                if isinstance(was_price, dict):
                    orig_price = was_price.get("value")
                elif isinstance(was_price, (int, float)):
                    orig_price = float(was_price)

            if promo_price is None:
                continue

            discount_text = "PROMO"
            promos_list = product.get("potentialPromotions") or product.get("promotions") or []
            if promos_list and isinstance(promos_list, list):
                first_promo = promos_list[0]
                if isinstance(first_promo, dict):
                    discount_text = first_promo.get("description") or first_promo.get("name") or "PROMO"

            valid_from = product.get("validFrom") or product.get("startDate")
            valid_until = product.get("validUntil") or product.get("endDate")

            images = product.get("images") or []
            image_url = None
            if images and isinstance(images, list):
                first_img = images[0]
                if isinstance(first_img, dict):
                    image_url = first_img.get("url")
                elif isinstance(first_img, str):
                    image_url = first_img

            if image_url and image_url.startswith("/"):
                image_url = f"{KRUIDVAT_BASE_URL}{image_url}"

            product_code = str(product.get("code") or product.get("id") or "")
            raw_url = product.get("url")
            deal_url = urljoin(KRUIDVAT_BASE_URL, raw_url) if raw_url else f"{KRUIDVAT_BASE_URL}/p/{product_code}"
            description = product.get("description") or product.get("summary") or ""

            fp = generate_fingerprint(
                store_id="kruidvat",
                title=title,
                promo_price=promo_price,
                valid_from=valid_from,
                valid_until=valid_until,
            )

            item = PromoItem(
                store_id="kruidvat",
                external_id=f"kruidvat_{product_code or fp[:8]}",
                fingerprint=fp,
                title=title[:255],
                description=description[:500],
                original_price=orig_price,
                promo_price=promo_price,
                discount_text=discount_text,
                unit_info=product.get("unitPrice") or product.get("unit"),
                image_url=image_url,
                deal_url=deal_url,
                category_id=infer_category(title, description),
                valid_from=valid_from,
                valid_until=valid_until,
                loyalty_card="Kruidvat Club",
                source_type="api",
            )
            items.append(item)
        return items

    # Backward compatibility alias
    parse_json_api = _parse_hybris_response

    async def _fetch_from_html(self) -> List[PromoItem]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        connector = aiohttp.TCPConnector(ssl=get_ssl_context(verify=True))
        items = []
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.get(self.web_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return items
                html = await resp.text(errors="ignore")

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

            fp = generate_fingerprint(
                store_id="kruidvat",
                title=title,
                promo_price=promo_price,
            )

            items.append(
                PromoItem(
                    store_id="kruidvat",
                    external_id=f"kruidvat_{fp[:8]}",
                    fingerprint=fp,
                    title=title[:240],
                    description="Kruidvat actie",
                    original_price=orig_price,
                    promo_price=promo_price,
                    discount_text=disc_text,
                    image_url=img_url,
                    deal_url=deal_url,
                    category_id=infer_category(title, disc_text),
                    loyalty_card="Kruidvat Club",
                    source_type="html",
                )
            )
        return items

    async def _fetch_from_leaflets(self) -> List[PromoItem]:
        try:
            from src.scrapers.leaflets.publitas import PublitasLeafletExtractor
            extractor = PublitasLeafletExtractor("kruidvat", "kruidvat-belgie")
            pubs = await extractor.get_active_publications()
            items = []
            for pub in pubs[:3]:
                slug = pub.get("slug") or str(pub.get("id", ""))
                if slug:
                    extracted = await extractor.extract_from_publication_slug(slug)
                    items.extend(extracted)
            return items
        except Exception as err:
            logger.debug(f"Kruidvat leaflet fallback failed: {err}")
            return []
