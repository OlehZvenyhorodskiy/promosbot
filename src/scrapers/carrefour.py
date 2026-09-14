import json
import re
import ssl
import certifi
import aiohttp
from bs4 import BeautifulSoup
from typing import List
from src.scrapers.base import BaseScraper, infer_category
from src.scrapers.models import PromoItem

class CarrefourScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_id="carrefour", name="Carrefour Belgium")
        self.url = "https://www.carrefour.be/nl/promoties"

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

            # Parse JSON-LD scripts
            soup = BeautifulSoup(html, "html.parser")
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        json_items = data
                    else:
                        json_items = [data]

                    for entry in json_items:
                        if entry.get("@type") == "Product" or "offers" in entry:
                            name = entry.get("name")
                            if not name:
                                continue
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

                            image = entry.get("image")
                            image_url = image if isinstance(image, str) else (image[0] if isinstance(image, list) and image else None)

                            items.append(
                                PromoItem(
                                    store_id=self.store_id,
                                    external_id=str(entry.get("sku") or self.stable_external_id(self.store_id, name, entry.get("url") or "")),
                                    title=name,
                                    description=entry.get("description", ""),
                                    promo_price=promo_price,
                                    discount_text="Bonus Actie",
                                    image_url=image_url,
                                    deal_url=entry.get("url") or self.url,
                                    category_id=infer_category(name, entry.get("description", "")),
                                )
                            )
                except Exception:
                    continue

            # Fallback HTML product cards
            if not items:
                cards = soup.select(".product-card, .promo-item, [data-qa*='product']")
                for idx, card in enumerate(cards[:25]):
                    title_elem = card.select_one("h2, h3, .product-title, .title")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    price_elem = card.select_one(".price, [class*='price']")
                    price_val = None
                    if price_elem:
                        m = re.search(r"(\d+[\.,]\d{2})", price_elem.get_text())
                        if m:
                            price_val = float(m.group(1).replace(",", "."))

                    img_elem = card.select_one("img")
                    img = img_elem.get("src") if img_elem else None

                    items.append(
                        PromoItem(
                            store_id=self.store_id,
                            external_id=self.stable_external_id(self.store_id, title, self.url),
                            title=title,
                            promo_price=price_val,
                            discount_text="Carrefour Bonus",
                            image_url=img,
                            deal_url=self.url,
                            category_id=infer_category(title),
                        )
                    )
        except Exception:
            pass

        return items
