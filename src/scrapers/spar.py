"""Specialized scraper for Spar (mijnspar.be) promotions.

The Spar promotions page is an Adobe AEM application: it loads its content
model from a `.model.json` export that contains every current promotion
(verified live: HTTP 200, JSON with a `results` list of 42 promo cards).
Each result carries an embedded `promotion` object with split price blocks
({"beforeDecimal": "10", "afterDecimal": "72", "empty": false}), epoch-milli
start/end dates and localized tags such as "1+1 gratis".

Day-price products (vegetables, minced meat) ship with `empty: true` price
blocks; they are still ingested with title/description only — no invented
prices.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from urllib.parse import urljoin

import aiohttp

from src.scrapers.base import BaseScraper, generate_fingerprint, get_ssl_context, infer_category
from src.scrapers.models import PromoItem

logger = logging.getLogger(__name__)

# AEM content model of https://www.mijnspar.be/promoties (nl language tree).
MODEL_URL = (
    "https://www.mijnspar.be/content/spar/nl/promoties/jcr:content/root/"
    "responsivegrid/responsivegrid/responsivegrid/filter_list_store_sp.model.json"
)

IMAGE_BASE = "https://www.mijnspar.be"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "nl-BE,nl;q=0.9",
}

REQUEST_TIMEOUT = 20  # seconds, matches the other API scrapers


def parse_price_block(block: Any) -> Optional[float]:
    """Convert an AEM split price block to a float.

    Blocks look like {"beforeDecimal": "10", "afterDecimal": "72", "empty":
    false}. Day-price products use {"empty": true} (or null fields), which
    must yield None — never an invented price.
    """
    if not isinstance(block, dict) or block.get("empty"):
        return None
    before = block.get("beforeDecimal")
    if before is None:
        return None
    try:
        cents = int(str(block.get("afterDecimal") or "0").strip())
        if not 0 <= cents <= 99:
            return None
        return float(f"{int(str(before).strip())}.{cents:02d}")
    except (TypeError, ValueError):
        return None


def epoch_ms_to_iso(raw: Any) -> Optional[str]:
    """Epoch milliseconds to an ISO YYYY-MM-DD date (UTC calendar day)."""
    try:
        return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def formatted_date_to_iso(raw: Any) -> Optional[str]:
    """'DD/MM/YYYY' to ISO; the short 'D/M' variant AEM sometimes emits is
    unusable without a year, so it yields None."""
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def discount_text_from_tags(tags: Any) -> str:
    """Use the first 'gratis' tag title (e.g. '1+1 gratis', '2+2 gratis'),
    else the generic label."""
    for tag in tags or []:
        if not isinstance(tag, dict):
            continue
        title = (tag.get("title") or "").strip()
        if title and "gratis" in title.lower():
            return title
    return "PROMO"


class SparScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_id="spar", name="Spar")
        self.url = MODEL_URL

    async def fetch_promos(self) -> List[PromoItem]:
        """Fetch the promotions content model, best-effort like the other scrapers."""
        try:
            results = await self._fetch_results()
            items = self._parse_results(results)
        except Exception as err:
            logger.debug(f"Spar fetch failed: {err}")
            return []
        return self._deduplicate(items)

    async def _fetch_results(self) -> List[dict]:
        connector = aiohttp.TCPConnector(ssl=get_ssl_context(verify=True))
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(connector=connector, headers=REQUEST_HEADERS) as session:
            async with session.get(MODEL_URL, timeout=timeout) as resp:
                if resp.status != 200:
                    logger.debug("Spar model endpoint returned HTTP %s", resp.status)
                    return []
                data = await resp.json(content_type=None)
        results = data.get("results") if isinstance(data, dict) else None
        return [r for r in results or [] if isinstance(r, dict)]

    def _parse_results(self, results: List[dict]) -> List[PromoItem]:
        items: List[PromoItem] = []
        for result in results:
            promotion = result.get("promotion")
            if not isinstance(promotion, dict):
                continue
            title = (promotion.get("promoTitle") or "").strip()
            if not title:
                continue
            description = (promotion.get("promoDescription") or "").strip()

            original_price = parse_price_block(promotion.get("normalPrice"))
            promo_price = parse_price_block(promotion.get("promoPrice"))
            # The promo price is never estimated: an empty promoPrice block
            # (day-price vegetables) stays None.
            valid_from = epoch_ms_to_iso(promotion.get("startDate")) or formatted_date_to_iso(
                promotion.get("formattedStartDate")
            )
            valid_until = epoch_ms_to_iso(promotion.get("endDate")) or formatted_date_to_iso(
                promotion.get("formattedEndDate")
            )

            asset_path = (promotion.get("promoAssetPath") or "").strip()
            image_url = urljoin(IMAGE_BASE, asset_path) if asset_path else None

            # The result uuid is a stable short id AEM assigns per promo card.
            result_uuid = (result.get("uuid") or "").strip()
            external_id = f"spar_{result_uuid}" if result_uuid else generate_fingerprint(
                store_id=self.store_id,
                title=title,
                promo_price=promo_price,
                valid_from=valid_from,
                valid_until=valid_until,
            )
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
                    external_id=external_id,
                    fingerprint=fingerprint,
                    title=f"{title} — {description}"[:255] if description else title[:255],
                    description=description[:500],
                    original_price=original_price,
                    promo_price=promo_price,
                    discount_text=discount_text_from_tags(result.get("localizedTags")),
                    price_per_unit=parse_price_block(promotion.get("unitPrice")),
                    unit_info=promotion.get("unitOfUnitPrice") or None,
                    image_url=image_url,
                    category_id=infer_category(title, description),
                    valid_from=valid_from,
                    valid_until=valid_until,
                    loyalty_card="Xtra" if promotion.get("xtraPromoCheck") else None,
                    source_type="api",
                )
            )
        return items

    @staticmethod
    def _deduplicate(items: List[PromoItem]) -> List[PromoItem]:
        result = []
        seen = set()
        for item in items:
            key = item.external_id or item.fingerprint or item.title.lower()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result[:1000]
