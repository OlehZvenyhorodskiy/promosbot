import re
import hashlib
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from src.scrapers.base import infer_category
from src.scrapers.models import PromoItem
from src.core.constants import SUPERMARKETS

class NewsletterParser:
    @staticmethod
    def detect_store_id(sender: str, subject: str, body_text: str) -> str:
        combined = f"{sender} {subject} {body_text[:1000]}".lower()
        for store_id in SUPERMARKETS.keys():
            if store_id.replace("_", " ") in combined:
                return store_id
            if store_id == "albert_heijn" and ("ah.be" in combined or "albert heijn" in combined):
                return "albert_heijn"
        return "colruyt"

    @classmethod
    def parse_newsletter_html(
        cls,
        html_content: str,
        sender: str = "",
        subject: str = "",
        deal_url: Optional[str] = None
    ) -> List[PromoItem]:
        soup = BeautifulSoup(html_content, "html.parser")
        store_id = cls.detect_store_id(sender, subject, soup.get_text())
        items: List[PromoItem] = []

        # Find potential product cards / table cells / sections in newsletter
        elements = soup.select("table, div, td")
        extracted_titles = set()

        discount_regex = re.compile(
            r"(\d+\s*\+\s*\d+\s*(?:gratis|gratuit)|-\s*\d+%\s*|\d+e\s*(?:halve prijs|à -?\d+%)|rode prijzen|bonus)",
            re.IGNORECASE,
        )
        price_regex = re.compile(r"€\s*(\d+[\.,]\d{2})|(\d+[\.,]\d{2})\s*€")

        for el in elements:
            text = el.get_text(" ", strip=True)
            if len(text) < 10 or len(text) > 400:
                continue

            disc_match = discount_regex.search(text)
            if not disc_match:
                continue

            discount_text = disc_match.group(1).upper().strip()

            # Find image in the same container or parent container
            img_elem = el.find("img")
            if not img_elem and el.parent:
                img_elem = el.parent.find("img")
            img_url = img_elem.get("src") if img_elem else None
            if img_url and ("spacer" in img_url.lower() or "icon" in img_url.lower() or "logo" in img_url.lower()):
                img_url = None

            # Find link
            a_elem = el.find("a")
            link = a_elem.get("href") if a_elem else deal_url or SUPERMARKETS.get(store_id, {}).get("url", "")

            # Extract price
            prices = price_regex.findall(text)
            promo_price = None
            orig_price = None
            if prices:
                parsed_prices = []
                for p1, p2 in prices:
                    raw = p1 or p2
                    try:
                        parsed_prices.append(float(raw.replace(",", ".")))
                    except ValueError:
                        pass
                if len(parsed_prices) >= 2:
                    orig_price = max(parsed_prices)
                    promo_price = min(parsed_prices)
                elif len(parsed_prices) == 1:
                    promo_price = parsed_prices[0]

            # Extract title (first line or heading-like text)
            lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 3]
            if not lines:
                continue
            title = lines[0]
            # Clean up title if it contains discount regex
            title = discount_regex.sub("", title).strip(" -:;,")
            if not title or len(title) < 3 or title.lower() in extracted_titles:
                continue
            extracted_titles.add(title.lower())

            desc = " ".join(lines[1:3]) if len(lines) > 1 else ""
            category_id = infer_category(title, desc)

            items.append(
                PromoItem(
                    store_id=store_id,
                    external_id=hashlib.sha256(
                        f"{store_id}:{title.strip().lower()}".encode("utf-8")
                    ).hexdigest()[:20],
                    title=title,
                    description=desc,
                    original_price=orig_price,
                    promo_price=promo_price,
                    discount_text=discount_text,
                    image_url=img_url,
                    deal_url=link,
                    category_id=category_id,
                )
            )

        return items
