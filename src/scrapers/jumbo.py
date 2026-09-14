"""Specialized scraper for Jumbo Belgium via the weekly in-store PDF flyer.

The aanbiedingen page (https://www.jumbo.com/nl-be/aanbiedingen) links the
weekly flyer PDF directly on www.jumbo.com/dam/belgie/... The PDF carries a
vector text layer that pypdf extracts cleanly, with price lines such as:

    Dr. Oetker Ristorante
    Verpakking 295-390 gram. Alle soorten.
    Prijsvoorbeeld: Dr. Oetker ristorante pizza salami 320 gram
    €8.55 nu €6 voor 3 - €6.25/kg

Flyer selection note (verified live 2026-09-15): the page does NOT order the
PDF links freshest-first — the expired Week-37 flyer link appears in the HTML
before the current Week-38 link. The scraper therefore picks the link with
the highest (year, week) in the filename, capped at the current ISO week so
a pre-published future flyer is only used when nothing current exists, and
falls back to the first link when no filename carries a week number.
"""

import logging
import re
from datetime import date, datetime
from typing import List, Optional, Tuple

import aiohttp

from src.core.constants import SUPERMARKETS
from src.scrapers.base import BaseScraper, generate_fingerprint, get_ssl_context, infer_category
from src.scrapers.leaflets.pdf_extractor import PDFLeafletExtractor
from src.scrapers.models import PromoItem

logger = logging.getLogger(__name__)

PAGE_TIMEOUT = 25  # seconds; the aanbiedingen page is ~437 KB of plain HTML
PDF_TIMEOUT = 60  # seconds; the flyer PDF is tens of MB
MAX_ITEMS = 200  # hard cap: a flyer never contains anywhere near this many deals

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
    "Accept-Language": "nl-BE,nl;q=0.9",
}

PDF_LINK_RE = re.compile(r"https://www\.jumbo\.com/dam/belgie/[^\"\s]+\.pdf", re.IGNORECASE)
WEEK_RE = re.compile(r"-(\d{4})-Week-(\d{1,2})\.pdf", re.IGNORECASE)

# "€8.55 nu €6 voor 3 - €6.25/kg" — the original price is optional, the promo
# price is not; both separators and integer euro amounts occur in the flyer.
PRICE_LINE_RE = re.compile(r"(?:€\s*(\d+(?:[.,]\d{1,2})?)\s+)?nu\s+€\s*(\d+(?:[.,]\d{1,2})?)", re.IGNORECASE)
UNIT_PRICE_RE = re.compile(r"-\s*€\s*(\d+(?:[.,]\d{1,2})?)\s*/\s*\S+", re.IGNORECASE)
VOOR_RE = re.compile(r"\bvoor\s+(\d{1,2})\b", re.IGNORECASE)

# Standalone deal markers ("1+1 gratis", "2e gratis") printed inside a product
# block. Footnote lines ("*1+1 gratis: 50% korting op de totaalprijs ...") do
# not full-match and are excluded separately.
GRATIS_MARKER_RE = re.compile(r"(?:\d{1,2}\s*\+\s*\d{1,2}\s+gratis|2e\s+(?:voor\s+)?(?:gratis|halve\s+prijs))", re.IGNORECASE)

# Price badges scattered by the text layer between products: "6.-", "1 .8 9",
# "25%", "3 voor", "vanaf", decorative headings and validity/service phrases.
BADGE_RE = re.compile(r"^[\d\s.,%€+\-]+$", re.IGNORECASE)
SERVICE_RE = re.compile(r"\bt/m\b|korting op de totaalprijs|^vanaf$", re.IGNORECASE)
DECORATION = {"de promo", "op je bord", "inspiratie", "voor vandaag"}

# Standalone unit-price badge ("€6.95/kg") printed under a neighbouring
# product: a hard block boundary, never part of the name.
UNIT_BADGE_RE = re.compile(r"^€\s*\d+(?:[.,]\d{1,2})?\s*/\s*\S+$")

# Lines that describe packaging rather than the product itself; they are used
# as description and the title is taken from the line(s) above them.
PACKAGING_RE = re.compile(
    r"^(?:Verpakking|Zak\b|Fles\b|Pot\b|Blik\b|Krat\b|Per kilogram|M\.u\.v\.|Denk aan)", re.IGNORECASE
)
PRIJSVOORBEELD_RE = re.compile(r"^Prijsvoorbeeld:\s*(.+)$", re.IGNORECASE)

NL_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}
# "Woensdag 16 september t/m dinsdag 22 september 2026" (weekday names optional)
VALIDITY_RE = re.compile(
    r"(\d{1,2})\s+([A-Za-zà-ÿ]+)\s+t/m\s+(?:[A-Za-zà-ÿ]+\s+)?(\d{1,2})\s+([A-Za-zà-ÿ]+)\s+(\d{4})",
    re.IGNORECASE,
)


def _to_price(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


class JumboScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_id="jumbo", name="Jumbo")
        self.url = SUPERMARKETS["jumbo"]["url"]

    async def fetch_promos(self) -> List[PromoItem]:
        """Page -> PDF link -> PDF text -> items; any failure yields []."""
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=get_ssl_context(verify=True)),
                headers=REQUEST_HEADERS,
            ) as session:
                html = await self._fetch_page_text(session)
                if not html:
                    return []
                flyer_url = self._select_flyer_url(self._extract_pdf_links(html))
                if not flyer_url:
                    return []
                pdf_bytes = await self._fetch_pdf_bytes(session, flyer_url)
                if not pdf_bytes:
                    return []
            pages_text = PDFLeafletExtractor().extract_page_texts(pdf_bytes)
            items = self.parse_leaflet_text(pages_text)
        except Exception as err:
            logger.debug(f"Jumbo fetch failed: {err}")
            return []
        return items

    async def _fetch_page_text(self, session: aiohttp.ClientSession) -> Optional[str]:
        async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=PAGE_TIMEOUT)) as resp:
            if resp.status != 200:
                logger.debug("Jumbo aanbiedingen page returned HTTP %s", resp.status)
                return None
            return await resp.text(errors="ignore")

    async def _fetch_pdf_bytes(self, session: aiohttp.ClientSession, url: str) -> Optional[bytes]:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=PDF_TIMEOUT)) as resp:
            if resp.status != 200:
                logger.debug("Jumbo flyer PDF returned HTTP %s", resp.status)
                return None
            return await resp.read()

    @staticmethod
    def _extract_pdf_links(html: str) -> List[str]:
        """Unique flyer PDF links in document order (the page also references
        Thumb .jpg previews, which never match the .pdf regex, but are filtered
        defensively)."""
        links: List[str] = []
        for link in PDF_LINK_RE.findall(html or ""):
            if "thumb" in link.lower():
                continue
            if link not in links:
                links.append(link)
        return links

    @staticmethod
    def _select_flyer_url(links: List[str], today: Optional[date] = None) -> Optional[str]:
        """Pick the current weekly flyer.

        See the module docstring: link order is not freshest-first, so the
        highest (year, week) at or before the current ISO week wins; ties keep
        the earliest link. Without week numbers, the first link is used.
        """
        if not links:
            return None
        today = today or datetime.now().date()
        year, week = today.isocalendar()[0], today.isocalendar()[1]

        def week_key(link: str) -> Optional[Tuple[int, int]]:
            match = WEEK_RE.search(link)
            if match:
                return int(match.group(1)), int(match.group(2))
            return None

        current = [(week_key(link), link) for link in links]
        with_weeks = [(key, link) for key, link in current if key is not None]
        if not with_weeks:
            return links[0]
        eligible = [(key, link) for key, link in with_weeks if key <= (year, week)]
        pool = eligible or with_weeks  # only fall back to future flyers if nothing else exists
        best_key = max(key for key, _ in pool)
        return next(link for key, link in pool if key == best_key)

    @staticmethod
    def parse_leaflet_text(pages_text: List[str]) -> List[PromoItem]:
        """Parse extracted flyer page texts into promo items.

        Pure function so the fragile flyer-text rules are unit-testable.
        """
        pages_text = pages_text or []
        valid_from, valid_until = JumboScraper._parse_validity_window("\n".join(pages_text))
        items: List[PromoItem] = []
        seen: set = set()
        for page_num, text in enumerate(pages_text, start=1):
            lines = [line.strip() for line in (text or "").split("\n") if line.strip()]
            for idx, line in enumerate(lines):
                if PRICE_LINE_RE.search(line):
                    item = JumboScraper._item_from_price_block(lines, idx, page_num, valid_from, valid_until)
                elif GRATIS_MARKER_RE.fullmatch(line):
                    item = JumboScraper._item_from_marker_block(lines, idx, page_num, valid_from, valid_until, line)
                else:
                    continue
                if item is None:
                    continue
                if item.fingerprint in seen:
                    continue
                seen.add(item.fingerprint)
                items.append(item)
                if len(items) >= MAX_ITEMS:
                    return items
        return items

    @staticmethod
    def _is_noise(line: str) -> bool:
        """Scattered price badges, footnotes and decorative/service text."""
        lowered = line.lower()
        if line.startswith("*") or lowered in DECORATION:
            return True
        if SERVICE_RE.search(line):
            return True
        return bool(BADGE_RE.fullmatch(line)) or bool(re.fullmatch(r"\d{1,2}\s+voor", lowered))

    @staticmethod
    def _block_before(lines: List[str], idx: int) -> List[str]:
        """Non-noise lines of the product block above a price/marker line,
        bounded by the previous price line."""
        block: List[str] = []
        for line in reversed(lines[:idx]):
            if PRICE_LINE_RE.search(line) or UNIT_BADGE_RE.fullmatch(line):
                break
            if not JumboScraper._is_noise(line):
                block.insert(0, line)
        return block

    @staticmethod
    def _title_from_block(block: List[str], price_line: str) -> Tuple[Optional[str], str]:
        """Title and description of a product block.

        'Prijsvoorbeeld: X' describes the concrete priced product, so its
        remainder becomes the title (whether it shares the price line or is a
        block line of its own); the remaining lines (group heading, packaging)
        become the description. Without an example line, the product name is
        the tail of non-packaging lines (Jumbo splits names over up to two
        lines) and the packaging lines above it become the description.
        """
        # Price and example share one line: everything before the price is the
        # product name.
        inline = PRIJSVOORBEELD_RE.search(price_line)
        if inline:
            prefix = inline.group(1)
            price_start = prefix.find("€")
            name = prefix[:price_start].strip() if price_start != -1 else prefix.strip()
            if name:
                return name, " ".join(block)[:500]

        for pos, line in enumerate(block):
            example = PRIJSVOORBEELD_RE.match(line)
            if not example:
                continue
            name = example.group(1)
            price_start = name.find("€")
            if price_start != -1:
                name = name[:price_start]
            name = name.strip()
            if name:
                rest = [other for other_pos, other in enumerate(block) if other_pos != pos]
                return name, " ".join(rest)[:500]

        named = [line for line in block if not PACKAGING_RE.match(line)]
        title = " ".join(named).strip() or None
        description_lines = [line for line in block if PACKAGING_RE.match(line)]
        return title, " ".join(description_lines)[:500]

    @staticmethod
    def _item_from_price_block(
        lines: List[str], idx: int, page_num: int, valid_from: Optional[str], valid_until: Optional[str]
    ) -> Optional[PromoItem]:
        line = lines[idx]
        match = PRICE_LINE_RE.search(line)
        promo_price = _to_price(match.group(2))
        original_price = _to_price(match.group(1))
        if promo_price is None:
            return None

        block = JumboScraper._block_before(lines, idx)
        title, description = JumboScraper._title_from_block(block, line)
        if not title:
            return None

        if original_price and original_price > 0 and promo_price < original_price:
            discount_text = f"-{int((1 - promo_price / original_price) * 100)}%"
        else:
            discount_text = f"nu {promo_price:.2f}"

        voor = VOOR_RE.search(line)
        unit = UNIT_PRICE_RE.search(line)
        return JumboScraper._build_item(
            title=title,
            description=description,
            promo_price=promo_price,
            original_price=original_price,
            discount_text=discount_text,
            page_num=page_num,
            valid_from=valid_from,
            valid_until=valid_until,
            unit_info=f"voor {voor.group(1)}" if voor else None,
            price_per_unit=_to_price(unit.group(1)) if unit else None,
        )

    @staticmethod
    def _item_from_marker_block(
        lines: List[str], idx: int, page_num: int, valid_from: Optional[str], valid_until: Optional[str], marker: str
    ) -> Optional[PromoItem]:
        """Deal without a printed price ("1+1 gratis"): keep title and label,
        never invent a promo price."""
        block = JumboScraper._block_before(lines, idx)
        title, description = JumboScraper._title_from_block(block, "")
        if not title:
            return None
        return JumboScraper._build_item(
            title=title,
            description=description,
            promo_price=None,
            original_price=None,
            discount_text=marker.strip(),
            page_num=page_num,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    @staticmethod
    def _build_item(
        title: str,
        description: str,
        promo_price: Optional[float],
        original_price: Optional[float],
        discount_text: str,
        page_num: int,
        valid_from: Optional[str],
        valid_until: Optional[str],
        unit_info: Optional[str] = None,
        price_per_unit: Optional[float] = None,
    ) -> PromoItem:
        fingerprint = generate_fingerprint(
            store_id="jumbo",
            title=title,
            promo_price=promo_price,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        return PromoItem(
            store_id="jumbo",
            external_id=f"jumbo_leaflet_p{page_num}_{fingerprint[:8]}",
            fingerprint=fingerprint,
            title=title[:255],
            description=description,
            original_price=original_price,
            promo_price=promo_price,
            discount_text=discount_text,
            unit_info=unit_info,
            price_per_unit=price_per_unit,
            category_id=infer_category(title, description),
            valid_from=valid_from,
            valid_until=valid_until,
            source_type="leaflet",
            page_number=page_num,
        )

    @staticmethod
    def _parse_validity_window(text: str) -> Tuple[Optional[str], Optional[str]]:
        """'Woensdag 16 september t/m dinsdag 22 september 2026' ->
        ('2026-09-16', '2026-09-22'). The printed year applies to the whole
        period (the flyer never spans a year change)."""
        if not text:
            return None, None
        normalized = re.sub(r"[ \xa0]+", " ", text)
        for match in VALIDITY_RE.finditer(normalized):
            start_month = NL_MONTHS.get(match.group(2).lower())
            end_month = NL_MONTHS.get(match.group(4).lower())
            if not start_month or not end_month:
                continue
            year = int(match.group(5))
            try:
                start = date(year, start_month, int(match.group(1))).isoformat()
                end = date(year, end_month, int(match.group(3))).isoformat()
            except ValueError:
                continue
            return start, end
        return None, None
