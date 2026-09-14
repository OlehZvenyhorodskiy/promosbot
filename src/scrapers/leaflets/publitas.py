import json
import logging
import re
from typing import List, Dict, Any, Optional
import aiohttp
from src.scrapers.models import PromoItem
from src.scrapers.base import infer_category, generate_fingerprint

logger = logging.getLogger(__name__)

class PublitasLeafletExtractor:
    """
    Extracts structured promotional deals directly from Publitas interactive
    digital brochures without requiring OCR.
    """

    def __init__(self, store_id: str, retailer_group: str = "", default_slug: str = ""):
        self.store_id = store_id
        self.retailer_group = retailer_group or store_id
        self.default_slug = default_slug
        self.base_url = f"https://view.publitas.com/{self.retailer_group}"

    async def get_active_publications(self, session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
        """Discover active publications/leaflets for this retailer."""
        url = f"{self.base_url}/publications.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*",
        }
        close_session = False
        if session is None:
            session = aiohttp.ClientSession(headers=headers)
            close_session = True

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict):
                        return data.get("publications", [])
                return []
        except Exception as err:
            logger.debug(f"Publitas discovery at {url} returned: {err}")
            return []
        finally:
            if close_session:
                await session.close()

    def parse_hotspots_data(self, hotspots: List[Dict[str, Any]], publication_id: str = "pub") -> List[PromoItem]:
        """Parse raw Publitas hotspots into normalized PromoItem objects."""
        items: List[PromoItem] = []
        for idx, hotspot in enumerate(hotspots):
            title = (
                hotspot.get("title")
                or hotspot.get("name")
                or hotspot.get("product", {}).get("name")
                or ""
            ).strip()

            if not title or len(title) < 2:
                continue

            desc = (
                hotspot.get("description")
                or hotspot.get("product", {}).get("description")
                or ""
            )

            # Price extraction
            price_info = hotspot.get("price") or hotspot.get("product", {}).get("price") or {}
            promo_price = None
            orig_price = None
            if isinstance(price_info, dict):
                promo_price = price_info.get("current") or price_info.get("promo") or price_info.get("value")
                orig_price = price_info.get("original") or price_info.get("regular")
            elif isinstance(price_info, (int, float)):
                promo_price = float(price_info)

            # Fallback to regex extraction from description or title if price missing
            if promo_price is None:
                matches = re.findall(r"€\s*(\d+[\.,]\d{2})", f"{title} {desc}")
                if matches:
                    try:
                        promo_price = float(matches[0].replace(",", "."))
                        if len(matches) > 1:
                            orig_price = float(matches[1].replace(",", "."))
                    except ValueError:
                        pass

            # Discount text
            discount_text = (
                hotspot.get("discount_label")
                or hotspot.get("discount_text")
                or "PROMO"
            )

            page_num = hotspot.get("page") or hotspot.get("position", {}).get("page") or 1
            bounds = hotspot.get("bounds") or hotspot.get("position")

            image_url = hotspot.get("image_url") or hotspot.get("product", {}).get("image_url")
            deal_url = hotspot.get("url") or hotspot.get("link") or f"{self.base_url}/{publication_id}#page={page_num}"

            fp = generate_fingerprint(
                store_id=self.store_id,
                title=title,
                promo_price=promo_price,
                valid_from=hotspot.get("valid_from"),
                valid_until=hotspot.get("valid_until"),
            )

            item = PromoItem(
                store_id=self.store_id,
                external_id=str(hotspot.get("id") or f"{self.store_id}_pub_{publication_id}_{idx}"),
                fingerprint=fp,
                title=title,
                description=desc,
                promo_price=promo_price,
                original_price=orig_price,
                discount_text=discount_text,
                unit_info=hotspot.get("unit") or hotspot.get("unit_info"),
                image_url=image_url,
                deal_url=deal_url,
                category_id=infer_category(title, desc),
                valid_from=hotspot.get("valid_from"),
                valid_until=hotspot.get("valid_until"),
                leaflet_id=publication_id,
                page_number=int(page_num),
                coordinates=bounds if isinstance(bounds, dict) else None,
                source_type="leaflet",
            )
            items.append(item)
        return items

    async def extract_from_publication_slug(self, slug: str) -> List[PromoItem]:
        """Fetch publication details and hotspots for a specific slug."""
        url = f"{self.base_url}/{slug}/pages/1/hotspots.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hotspots = data if isinstance(data, list) else data.get("hotspots", [])
                        return self.parse_hotspots_data(hotspots, publication_id=slug)
        except Exception as err:
            logger.debug(f"Publitas fetch for {slug} failed: {err}")
        return []
