import re
import ssl
import certifi
import aiohttp
from bs4 import BeautifulSoup
from typing import List
from src.scrapers.base import BaseScraper, infer_category
from src.scrapers.models import PromoItem

class ColruytScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_id="colruyt", name="Colruyt")
        self.url = "https://www.colruyt.be/nl/acties"

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

            soup = BeautifulSoup(html, "html.parser")
            # Parse promo card elements
            cards = soup.select(".action-card, .promo-card, [data-testid*='promo'], .m-card")
            for i, card in enumerate(cards):
                title_elem = card.select_one("h2, h3, h4, .title, [class*='title']")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                desc_elem = card.select_one("p, .description, [class*='desc']")
                desc = desc_elem.get_text(strip=True) if desc_elem else ""

                # Look for discount badge
                badge_elem = card.select_one(".badge, .discount, [class*='discount'], [class*='promo']")
                discount_text = badge_elem.get_text(strip=True) if badge_elem else "Rode Prijzen"

                # Look for prices
                price_text = card.get_text()
                price_match = re.findall(r"€\s*(\d+[\.,]\d{2})", price_text)
                promo_price = None
                if price_match:
                    try:
                        promo_price = float(price_match[0].replace(",", "."))
                    except ValueError:
                        pass

                # Image
                img_elem = card.select_one("img")
                img_url = img_elem.get("src") or img_elem.get("data-src") if img_elem else None
                if img_url and img_url.startswith("/"):
                    img_url = f"https://www.colruyt.be{img_url}"

                link_elem = card.select_one("a[href]")
                deal_url = link_elem.get("href") if link_elem else self.url
                if deal_url and deal_url.startswith("/"):
                    deal_url = f"https://www.colruyt.be{deal_url}"

                category_id = infer_category(title, desc)
                items.append(
                    PromoItem(
                        store_id=self.store_id,
                        external_id=self.stable_external_id(self.store_id, title, deal_url),
                        title=title,
                        description=desc,
                        original_price=None,
                        promo_price=promo_price,
                        discount_text=discount_text,
                        image_url=img_url,
                        deal_url=deal_url,
                        category_id=category_id,
                    )
                )
        except Exception:
            pass

        return items
