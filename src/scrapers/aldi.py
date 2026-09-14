import json
import re
import ssl
import certifi
import aiohttp
from typing import List
from src.scrapers.base import BaseScraper, infer_category
from src.scrapers.models import PromoItem

class AldiScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_id="aldi", name="Aldi Belgium")
        self.url = "https://www.aldi.be/nl/aanbiedingen.html"

    async def fetch_promos(self) -> List[PromoItem]:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
        }

        items: List[PromoItem] = []
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status != 200:
                        return items
                    html = await resp.text()

            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if not match:
                return items

            data = json.loads(match.group(1))
            api_data_raw = data.get("props", {}).get("pageProps", {}).get("apiData", "")
            if not api_data_raw or not isinstance(api_data_raw, str):
                return items

            api_data = json.loads(api_data_raw)
            for action in api_data:
                if isinstance(action, list) and len(action) > 1 and action[0] == "OFFER_GET":
                    res = action[1].get("res", {})
                    algolia_map = res.get("algoliaDataMap", {})
                    for ext_id, item_data in algolia_map.items():
                        name = item_data.get("name")
                        if not name:
                            continue

                        desc = item_data.get("longDescription") or item_data.get("shortDescription") or ""
                        current_price_info = item_data.get("currentPrice") or {}
                        promo_price = current_price_info.get("priceValue")
                        strike_info = current_price_info.get("strikePrice") or {}
                        original_price = strike_info.get("strikePriceValue")

                        labels = current_price_info.get("priceTagLabels") or {}
                        discount_text = labels.get("promoText1") or ""

                        unit_info = item_data.get("salesUnit") or ""
                        base_prices = current_price_info.get("basePrice") or []
                        if base_prices and isinstance(base_prices, list):
                            base = base_prices[0]
                            base_value = base.get("basePriceValue")
                            base_scale = base.get("basePriceScale")
                            if base_value is not None and base_scale:
                                unit_info = f"{unit_info} (€{float(base_value):.2f}/{base_scale})"

                        # Images
                        image_url = None
                        assets = item_data.get("assets") or []
                        if assets and isinstance(assets, list):
                            image_url = assets[0].get("url")

                        # Validity dates
                        valid_from = None
                        valid_until = None
                        promo_prices = item_data.get("promotionPrices") or []
                        if promo_prices and isinstance(promo_prices, list):
                            first_promo = promo_prices[0]
                            if original_price is None:
                                original_price = (first_promo.get("strikePrice") or {}).get("strikePriceValue")
                            valid_from = first_promo.get("validFromLocalDate")
                            valid_until = first_promo.get("validUntilLocalDate")

                        category_id = infer_category(name, desc)
                        slug = item_data.get("productSlug")
                        deal_url = f"https://www.aldi.be/nl/aanbiedingen/{slug}.html" if slug else self.url

                        items.append(
                            PromoItem(
                                store_id=self.store_id,
                                external_id=str(ext_id),
                                title=name.strip(),
                                description=desc.strip(),
                                original_price=original_price,
                                promo_price=promo_price,
                                discount_text=discount_text,
                                unit_info=unit_info,
                                image_url=image_url,
                                deal_url=deal_url,
                                category_id=category_id,
                                valid_from=valid_from,
                                valid_until=valid_until,
                            )
                        )
        except Exception as e:
            # Safe catch, returns collected items
            pass

        return items
