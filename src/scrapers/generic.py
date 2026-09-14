"""Best-effort parser for public retailer promotion pages.

Retailers do not share one API: some expose JSON-LD, some render product cards
in HTML, and some only expose a JavaScript application or a protected endpoint.
This adapter handles the public JSON/HTML cases and returns an empty result for
protected pages so a failing retailer never blocks the other stores.
"""

import json
import re
import ssl
from html import unescape
from typing import Any, Iterable, List, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, infer_category
from src.scrapers.models import PromoItem

PRICE_RE = re.compile(r"(?:€|�)\s*([0-9]{1,3}(?:[.\s][0-9]{3})*[,\.][0-9]{2})")
DISCOUNT_RE = re.compile(r"(?:\d+\s*[+]\s*\d+\s*(?:gratis|free)|-\s*\d+\s*%)", re.I)
GENERIC_DISCOUNTS = {"", "promo", "actie", "promotie", "promotion", "discount"}
NON_PRODUCT_TITLES = {
    "mydelhaize",
    "delhaize",
    "promoties",
    "promotions",
    "filteren",
    "filters",
    "aanmelden",
    "inloggen",
}


def parse_price(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        for key in ("priceValue", "value", "amount", "price", "formatted"):
            if key in raw:
                parsed = parse_price(raw.get(key))
                if parsed is not None:
                    return parsed
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", str(raw).replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def prices_from_text(text: str) -> list[float]:
    prices = []
    for match in PRICE_RE.findall(text):
        normalized = match.replace(".", "").replace(" ", "").replace(",", ".")
        # A dot is a decimal separator when there is only one dot.
        if match.count(".") == 1 and "," not in match:
            normalized = match.replace(" ", "")
        try:
            prices.append(float(normalized))
        except ValueError:
            continue
    return prices


def retailer_price_from_text(text: str) -> Optional[float]:
    """Parse both normal euro text and Delhaize's split accessible price."""
    prices = prices_from_text(text)
    if prices:
        return prices[-1]
    normalized = " ".join(text.replace("\xa0", " ").split())
    split_number = re.fullmatch(r"(\d{1,3})\s+(\d{2})", normalized)
    if split_number:
        return float(f"{split_number.group(1)}.{split_number.group(2)}")
    euro_cents = re.search(r"(?:€|�)\s*(\d{1,3})\s+(\d{2})(?:\D|$)", normalized)
    if euro_cents:
        return float(f"{euro_cents.group(1)}.{euro_cents.group(2)}")
    accessible = re.search(r"(\d{1,3})\s*euro\s*(\d{1,2})\s*cent", normalized, re.I)
    if accessible:
        return float(f"{accessible.group(1)}.{int(accessible.group(2)):02d}")
    return None


class GenericRetailerScraper(BaseScraper):
    def __init__(
        self,
        store_id: str,
        name: str,
        url: str,
        ssl_verify: bool = True,
    ):
        super().__init__(store_id=store_id, name=name)
        self.url = url
        self.ssl_verify = ssl_verify

    async def fetch_promos(self) -> List[PromoItem]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-BE,nl;q=0.9,fr;q=0.8,en;q=0.7",
        }
        ssl_context = None
        if self.ssl_verify:
            ssl_context = ssl.create_default_context()
        else:
            ssl_context = False

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                    if response.status >= 400:
                        return []
                    html = await response.text(errors="ignore")
        except Exception:
            return []

        return self.parse_html(html)

    def parse_html(self, html: str, prefer_cards: bool = False) -> List[PromoItem]:
        """Parse either server-rendered or browser-rendered retailer HTML."""
        soup = BeautifulSoup(html, "html.parser")
        if prefer_cards:
            items = self._parse_cards(soup)
            if items:
                return self._deduplicate(items)
        items = self._parse_json_ld(soup)
        if not items:
            items = self._parse_embedded_json(soup)
        if not items:
            items = self._parse_cards(soup)
        return self._deduplicate(items)

    def _make_item(
        self,
        title: str,
        description: str = "",
        promo_price: Optional[float] = None,
        original_price: Optional[float] = None,
        discount_text: str = "",
        image_url: Optional[str] = None,
        deal_url: Optional[str] = None,
        source_key: str = "",
    ) -> Optional[PromoItem]:
        title = " ".join(title.split()).strip()
        normalized_title = re.sub(r"\s+", " ", title.casefold()).strip(" .:-")
        if len(title) < 3 or normalized_title in NON_PRODUCT_TITLES:
            return None
        if "mydelhaize" in normalized_title:
            return None

        promo_value = promo_price if promo_price is not None and promo_price > 0 else None
        original_value = original_price if original_price is not None and original_price > 0 else None
        clean_discount = (discount_text or "").strip().casefold()
        # Navigation/placeholder cards often contain a zero price and a generic
        # promo label. They are not actual products and must never enter the DB.
        if promo_value is None and original_value is None and clean_discount in GENERIC_DISCOUNTS:
            return None

        resolved_deal_url = urljoin(self.url, deal_url) if deal_url else None
        # A landing page is useful as a folder link, but not as a per-product
        # "open deal" button. Keep it empty so the Telegram card hides that
        # misleading action.
        if resolved_deal_url:
            base = resolved_deal_url.split("?", 1)[0].rstrip("/").casefold()
            landing = self.url.split("?", 1)[0].rstrip("/").casefold()
            if base == landing:
                resolved_deal_url = None

        return PromoItem(
            store_id=self.store_id,
            external_id=self.stable_external_id(self.store_id, title, source_key or deal_url or self.url),
            title=title[:240],
            description=" ".join(description.split())[:500],
            original_price=original_price,
            promo_price=promo_price,
            discount_text=discount_text or "PROMO",
            image_url=urljoin(self.url, image_url) if image_url else None,
            deal_url=resolved_deal_url,
            category_id=infer_category(title, description),
        )

    def _parse_json_ld(self, soup: BeautifulSoup) -> List[PromoItem]:
        items = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                payload = json.loads(script.string or script.get_text())
            except (TypeError, ValueError):
                continue
            entries = payload if isinstance(payload, list) else payload.get("@graph", [payload]) if isinstance(payload, dict) else []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                offers = entry.get("offers") or {}
                offer = offers[0] if isinstance(offers, list) and offers else offers
                if not name or not isinstance(offer, dict):
                    continue
                promo_price = parse_price(offer.get("price"))
                original_price = parse_price(offer.get("highPrice"))
                if original_price is not None and promo_price is not None and original_price <= promo_price:
                    original_price = None
                item = self._make_item(
                    name,
                    entry.get("description", ""),
                    promo_price,
                    original_price,
                    "PROMO",
                    entry.get("image") if isinstance(entry.get("image"), str) else None,
                    entry.get("url"),
                    str(entry.get("sku") or entry.get("url") or name),
                )
                if item:
                    items.append(item)
        return items

    def _parse_embedded_json(self, soup: BeautifulSoup) -> List[PromoItem]:
        items = []

        def walk(value: Any) -> Iterable[dict[str, Any]]:
            if isinstance(value, dict):
                name = value.get("name") or value.get("productName") or value.get("title")
                current = value.get("currentPrice") or value.get("price")
                if name and (isinstance(current, (int, float, str, dict)) or value.get("promoPrice")):
                    yield value
                for child in value.values():
                    yield from walk(child)
            elif isinstance(value, list):
                for child in value:
                    yield from walk(child)

        for script in soup.find_all("script"):
            raw = script.string or script.get_text()
            if not raw or len(raw) < 20 or len(raw) > 3_000_000:
                continue
            if script.get("id") not in {"__NEXT_DATA__", "__NUXT_DATA__"} and "currentPrice" not in raw:
                continue
            try:
                payload = json.loads(unescape(raw))
            except (TypeError, ValueError):
                continue
            for entry in walk(payload):
                current = entry.get("currentPrice") or entry.get("promoPrice") or entry.get("price")
                current = current.get("priceValue") if isinstance(current, dict) else current
                promotion_prices = entry.get("promotionPrices") or []
                promo_info = promotion_prices[0] if isinstance(promotion_prices, list) and promotion_prices else {}
                original = entry.get("originalPrice") or (promo_info.get("strikePrice") or {}).get("strikePriceValue")
                item = self._make_item(
                    entry.get("name") or entry.get("productName") or entry.get("title"),
                    entry.get("description") or entry.get("shortDescription") or "",
                    parse_price(current),
                    parse_price(original),
                    (entry.get("discount") or entry.get("promoText") or "PROMO"),
                    entry.get("image") or entry.get("imageUrl"),
                    entry.get("url") or entry.get("link"),
                    str(entry.get("id") or entry.get("sku") or entry.get("name")),
                )
                if item:
                    items.append(item)
        return items

    def _parse_cards(self, soup: BeautifulSoup) -> List[PromoItem]:
        selectors = [
            "[data-testid='product-block']",
            "[data-testid*='product-tile']",
            "article",
            "[class*='pdw-product-item']",
            "[class*='promotion']",
            "[class*='product-card']",
            "[class*='offer-card']",
            "[class*='promo-card']",
            "[data-testid*='product']",
            "[data-testid*='offer']",
        ]
        items = []
        seen_titles = set()
        for card in soup.select(",".join(selectors)):
            text = card.get_text(" ", strip=True)
            price_node = card.select_one(
                "[data-testid='product-block-price'], [data-testid*='current-price'], "
                ".pdw-price:not(.pdw-price-alt), [class*='current-price']"
            )
            price_text = price_node.get("aria-label", "") if price_node else ""
            price_text = price_text or (price_node.get_text(" ", strip=True) if price_node else text)
            current_price = retailer_price_from_text(price_text)
            if current_price is None and price_node:
                current_price = parse_price(price_text)
            prices = prices_from_text(text)
            if current_price is None and prices:
                current_price = prices[-1]
            promo_tag = card.select_one(
                "[data-testid*='tag-promo'], [class*='promo-banner'], [class*='promotion-label']"
            )
            discount = promo_tag.get_text(" ", strip=True) if promo_tag else (
                DISCOUNT_RE.search(text).group(0) if DISCOUNT_RE.search(text) else "PROMO"
            )
            if current_price is None and discount.casefold() in GENERIC_DISCOUNTS:
                continue
            image_link = card.select_one("[data-testid='product-block-image-link']")
            title_elem = card.select_one(
                "[data-testid='product-block-product-name'], "
                "[data-testid='product-block-name-link'], "
                "[data-testid*='product-name'], "
                ".card-text p b, .pdw-product-name, "
                "h2, h3, h4, [class*='title'], [class*='name']"
            )
            title = (
                image_link.get("aria-label")
                if image_link and image_link.get("aria-label")
                else title_elem.get_text(" ", strip=True) if title_elem else ""
            )
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            image = card.select_one("img")
            link = image_link or card.select_one("a[href]")
            original_node = card.select_one(
                "[data-testid*='original-price'], [class*='price-stroke'], [class*='old-price']"
            )
            original_price = parse_price(original_node.get_text(" ", strip=True)) if original_node else None
            supplementary = card.select_one(
                "[data-testid='product-block-attributes'], [data-testid*='price-unit'], "
                "[class*='price-unit'], [class*='unit']"
            )
            unit_info = supplementary.get_text(" ", strip=True) if supplementary else ""
            href = link.get("href") if link else None
            item = self._make_item(
                title,
                text[:500],
                current_price,
                original_price or (prices[-2] if len(prices) > 1 and prices[-2] > prices[-1] else None),
                discount,
                (image.get("src") or image.get("data-src")) if image else None,
                href,
                href or title,
            )
            if item and unit_info:
                item.unit_info = unit_info[:120]
            if item:
                items.append(item)
        return items

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
