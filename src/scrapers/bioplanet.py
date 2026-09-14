"""Specialized scraper for Bio-Planet (Colruyt Group) promotions.

Bio-Planet exposes the same public API gateway as the other Colruyt Group
brands. The gateway key is not a secret: www.bioplanet.be itself ships it in
its HTML (parsed config), but it is hardcoded here for stability.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from src.scrapers.base import BaseScraper, generate_fingerprint, get_ssl_context, infer_category
from src.scrapers.models import PromoItem

logger = logging.getLogger(__name__)

# FIXME: rotate if blocked. The site serves this key in its own HTML, but a
# hardcoded verified value keeps requests stable across releases.
BIOPLANET_API_KEY = "f0187bee-04aa-11eb-ba0f-e73e45a3f0f2"

PRODUCTS_URL = "https://apip.bioplanet.be/gateway/emec.bioplanet.protected.bffsvc/cg/nl/api/products"
PROMOTIONS_URL = "https://apip.bioplanet.be/gateway/ictmgmt.emarkecom.promotionretrsvc.v1/v1/v1/nl/promotion"

# Default store placeId used by the Bio-Planet web shop.
PLACE_ID = "1811"
PAGE_SIZE = 50
MAX_PAGES = 6  # Safety cap against endless pagination loops
PROMO_CHUNK_SIZE = 10  # Keep promotionIds URLs short

# The sort value is passed as a raw URL segment ("popularity+asc") exactly as
# the verified site requests do, so it must not go through params encoding.
PRODUCTS_QUERY = f"placeId={PLACE_ID}&page={{page}}&size={PAGE_SIZE}&sort=popularity+asc&isAvailable=true&inPromo=true"

REQUEST_HEADERS = {
    "x-cg-apikey": BIOPLANET_API_KEY,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "nl-BE",
    "Origin": "https://www.bioplanet.be",
    "Referer": "https://www.bioplanet.be/",
}


def _normalize_date(raw: Any) -> Optional[str]:
    """Normalize API dates ('DD-MM-YYYY' or ISO 'YYYY-MM-DD') to ISO format."""
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


class BioplanetScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_id="bioplanet", name="Bio-Planet")
        self.url = "https://www.bioplanet.be/nl/acties"

    async def fetch_promos(self) -> List[PromoItem]:
        """Fetch promo products through the public gateway, best-effort."""
        try:
            products = await self._fetch_all_products()
            if not products:
                return []
            promo_details = await self._fetch_promotion_details(products)
            items = self._parse_products(products, promo_details)
        except Exception as err:
            logger.debug(f"Bio-Planet fetch failed: {err}")
            return []
        return self._deduplicate(items)

    async def _fetch_all_products(self) -> List[dict]:
        products: List[dict] = []
        connector = aiohttp.TCPConnector(ssl=get_ssl_context(verify=True))
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(connector=connector, headers=REQUEST_HEADERS) as session:
            for page in range(1, MAX_PAGES + 1):
                page_products = await self._fetch_products_page(session, page)
                if page_products is None:
                    break
                products.extend(page_products)
                if len(page_products) < PAGE_SIZE:
                    break
        return products

    async def _fetch_products_page(self, session: aiohttp.ClientSession, page: int) -> Optional[List[dict]]:
        url = f"{PRODUCTS_URL}?{PRODUCTS_QUERY.format(page=page)}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    logger.debug("Bio-Planet products page %s returned HTTP %s", page, resp.status)
                    return None
                data = await resp.json()
        except Exception as err:
            logger.debug(f"Bio-Planet products page {page} request failed: {err}")
            return None
        return data.get("products") or []

    async def _fetch_promotion_details(self, products: List[dict]) -> Dict[str, dict]:
        """Best-effort lookup of promotion details keyed by promotion id.

        The endpoint answers 200 with an empty list for some ids (the browser
        flow uses an extra authorization call), so an empty result is normal:
        callers then fall back to the promotion data embedded in each product.
        """
        ids: set[str] = set()
        for product in products:
            for promo in product.get("promotion") or []:
                if isinstance(promo, dict):
                    for key in ("techPromoId", "promotionId"):
                        if promo.get(key):
                            ids.add(str(promo[key]))

        details: Dict[str, dict] = {}
        connector = aiohttp.TCPConnector(ssl=get_ssl_context(verify=True))
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(connector=connector, headers=REQUEST_HEADERS) as session:
            for chunk in self._chunk_ids(sorted(ids)):
                url = f"{PROMOTIONS_URL}?promotionIds={','.join(chunk)}&clientCode=BIOBE"
                try:
                    async with session.get(url, timeout=timeout) as resp:
                        if resp.status != 200:
                            logger.debug("Bio-Planet promotion details returned HTTP %s", resp.status)
                            continue
                        data = await resp.json()
                except Exception as err:
                    logger.debug(f"Bio-Planet promotion details request failed: {err}")
                    continue
                promotions = data.get("promotion") or data.get("promotions") or []
                for promo in promotions:
                    if not isinstance(promo, dict):
                        continue
                    for key in ("promotionId", "commercialPromotionId"):
                        if promo.get(key):
                            details[str(promo[key])] = promo
        return details

    @staticmethod
    def _chunk_ids(ids: List[str], size: int = PROMO_CHUNK_SIZE) -> List[List[str]]:
        return [ids[start:start + size] for start in range(0, len(ids), size)]

    def _parse_products(self, products: List[dict], promo_details: Dict[str, dict]) -> List[PromoItem]:
        items: List[PromoItem] = []
        for product in products:
            title = (product.get("name") or "").strip()
            if not title:
                continue

            price_info = product.get("price") or {}
            basic_price = price_info.get("basicPrice")
            description = product.get("description") or ""
            image_url = product.get("fullImage") or product.get("squareImage") or product.get("thumbNail")
            article_number = product.get("commercialArticleNumber") or ""

            for promo in product.get("promotion") or []:
                if not isinstance(promo, dict):
                    continue
                if str(promo.get("isPersonalized") or "").upper() == "Y":
                    # Personalized promos are not available to other customers.
                    continue

                detail = None
                for key in (promo.get("techPromoId"), promo.get("promotionId")):
                    if key and str(key) in promo_details:
                        detail = promo_details[str(key)]
                        break

                benefit = self._primary_benefit(detail)
                discount_text, promo_price = self._discount_from_benefit(benefit, basic_price)
                valid_from, valid_until = self._validity_window(promo, detail)

                promo_key = promo.get("techPromoId") or promo.get("promotionId") or ""
                fingerprint = generate_fingerprint(
                    store_id=self.store_id,
                    title=title,
                    promo_price=promo_price,
                    valid_from=valid_from,
                    valid_until=valid_until,
                )
                items.append(
                    PromoItem(
                        store_id=self.store_id,
                        external_id=f"bioplanet_{promo_key}_{article_number}",
                        fingerprint=fingerprint,
                        title=title[:255],
                        description=description,
                        original_price=basic_price,
                        promo_price=promo_price,
                        discount_text=discount_text,
                        unit_info=price_info.get("measurementUnit"),
                        price_per_unit=price_info.get("pricePerUOM"),
                        image_url=image_url,
                        category_id=infer_category(title, description),
                        valid_from=valid_from,
                        valid_until=valid_until,
                        loyalty_card="Xtra",
                        source_type="api",
                    )
                )
        return items

    @staticmethod
    def _primary_benefit(detail: Optional[dict]) -> Optional[dict]:
        """Pick the first benefit tier (lowest sequence) of a promotion."""
        if not detail:
            return None
        entries = [b for b in detail.get("benefit") or [] if isinstance(b, dict)]
        if not entries:
            return None
        return min(entries, key=lambda b: b.get("sequence") if isinstance(b.get("sequence"), (int, float)) else 0)

    @staticmethod
    def _discount_from_benefit(benefit: Optional[dict], basic_price: Any) -> tuple[str, Optional[float]]:
        """Build the discount label and estimated promo price from a benefit."""
        if not benefit or benefit.get("benefitPercentage") is None:
            return "PROMO", None
        try:
            percentage = float(benefit["benefitPercentage"])
        except (TypeError, ValueError):
            return "PROMO", None

        discount_text = f"-{int(percentage)}%"
        min_limit = benefit.get("minLimit")
        if min_limit:
            discount_text = f"{discount_text} vanaf {min_limit}"

        promo_price = None
        if basic_price is not None:
            try:
                promo_price = round(float(basic_price) * (1 - percentage / 100.0), 2)
            except (TypeError, ValueError):
                promo_price = None
        return discount_text, promo_price

    @staticmethod
    def _validity_window(product_promo: dict, detail: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
        """ISO validity dates; prefer gateway details, fall back to the product's own dates."""
        detail_start = detail_end = None
        if detail:
            detail_start = detail.get("activeStartDate") or detail.get("publicationStartDate")
            detail_end = detail.get("activeEndDate") or detail.get("publicationEndDate")
        valid_from = _normalize_date(detail_start) or _normalize_date(product_promo.get("publicationStartDate"))
        valid_until = _normalize_date(detail_end) or _normalize_date(product_promo.get("publicationEndDate"))
        return valid_from, valid_until

    @staticmethod
    def _deduplicate(items: List[PromoItem]) -> List[PromoItem]:
        result = []
        seen = set()
        for item in items:
            key = item.external_id or item.title.lower()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result[:1000]
