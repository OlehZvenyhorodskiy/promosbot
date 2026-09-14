import logging
import re
from typing import List, Dict, Any, Optional
import aiohttp
from src.scrapers.models import PromoItem
from src.scrapers.base import infer_category, generate_fingerprint

logger = logging.getLogger(__name__)

RETAILER_MAPPING = {
    "colruyt": "colruyt",
    "carrefour": "carrefour",
    "carrefour-market": "carrefour",
    "carrefour-hyper": "carrefour",
    "delhaize": "delhaize",
    "ad-delhaize": "delhaize",
    "proxy-delhaize": "delhaize",
    "aldi": "aldi",
    "lidl": "lidl",
    "albert-heijn": "albert_heijn",
    "albertheijn": "albert_heijn",
    "jumbo": "jumbo",
    "spar": "spar",
    "cora": "cora",
    "intermarche": "intermarche",
    "action": "action",
    "kruidvat": "kruidvat",
    "okay": "okay",
    "bioplanet": "bioplanet",
    "bio-planet": "bioplanet",
}

class TiendeoAggregator:
    """
    Ingests digital promotions and catalog data from Tiendeo.be / Belgian aggregators.
    """

    def __init__(self):
        self.base_url = "https://www.tiendeo.be"
        self.api_url = "https://api.tiendeo.be/v1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7",
        }

    @staticmethod
    def map_store_id(raw_slug: str) -> str:
        slug = (raw_slug or "").lower().strip()
        for pattern, internal_id in RETAILER_MAPPING.items():
            if pattern in slug:
                return internal_id
        return "generic"

    def parse_deal(self, deal: Dict[str, Any], default_store_id: str = "") -> Optional[PromoItem]:
        title = (deal.get("title") or deal.get("name") or "").strip()
        if not title:
            return None

        store_raw = deal.get("retailer") or deal.get("retailer_name") or deal.get("store") or default_store_id
        store_id = self.map_store_id(str(store_raw))

        price_raw = deal.get("price") or deal.get("promo_price")
        promo_price = None
        if isinstance(price_raw, (int, float)):
            promo_price = float(price_raw)
        elif isinstance(price_raw, str):
            m = re.search(r"(\d+[\.,]\d{2})", price_raw)
            if m:
                promo_price = float(m.group(1).replace(",", "."))

        orig_price_raw = deal.get("original_price") or deal.get("strike_price")
        orig_price = None
        if isinstance(orig_price_raw, (int, float)):
            orig_price = float(orig_price_raw)
        elif isinstance(orig_price_raw, str):
            m = re.search(r"(\d+[\.,]\d{2})", orig_price_raw)
            if m:
                orig_price = float(m.group(1).replace(",", "."))

        discount_text = deal.get("discount") or deal.get("discount_label") or "PROMO"
        valid_from = deal.get("valid_from") or deal.get("start_date")
        valid_until = deal.get("valid_until") or deal.get("end_date")
        desc = deal.get("description") or ""

        fp = generate_fingerprint(
            store_id=store_id,
            title=title,
            promo_price=promo_price,
            valid_from=valid_from,
            valid_until=valid_until,
        )

        return PromoItem(
            store_id=store_id,
            external_id=str(deal.get("id") or fp),
            fingerprint=fp,
            title=title,
            description=desc,
            promo_price=promo_price,
            original_price=orig_price,
            discount_text=discount_text,
            unit_info=deal.get("unit") or deal.get("unit_info"),
            image_url=deal.get("image") or deal.get("image_url"),
            deal_url=deal.get("url") or deal.get("deal_url"),
            category_id=infer_category(title, desc),
            valid_from=valid_from,
            valid_until=valid_until,
            leaflet_id=str(deal.get("catalogue_id") or deal.get("leaflet_id") or ""),
            page_number=deal.get("page") or deal.get("page_number"),
            source_type="aggregator",
        )

    def parse_catalogue(self, catalogue: Dict[str, Any]) -> List[PromoItem]:
        """Extract product items contained within a catalogue object."""
        items: List[PromoItem] = []
        store_raw = catalogue.get("retailer") or catalogue.get("retailer_name") or ""
        products = catalogue.get("products") or catalogue.get("deals") or []
        for p in products:
            item = self.parse_deal(p, default_store_id=store_raw)
            if item:
                items.append(item)
        return items

    async def fetch_retailer_deals(self, retailer_slug: str) -> List[PromoItem]:
        """Fetch active deals for a given retailer from aggregator feed."""
        url = f"{self.api_url}/retailers/{retailer_slug}/deals"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        deals = data if isinstance(data, list) else data.get("deals", [])
                        return [
                            item
                            for item in (self.parse_deal(d, default_store_id=retailer_slug) for d in deals)
                            if item is not None
                        ]
        except Exception as err:
            logger.debug(f"Tiendeo deals fetch for {retailer_slug} returned: {err}")
        return []
