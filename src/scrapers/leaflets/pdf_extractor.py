import io
import logging
import re
from typing import List, Optional
from src.scrapers.models import PromoItem
from src.scrapers.base import infer_category, generate_fingerprint

logger = logging.getLogger(__name__)

try:
    import pypdf
except ImportError:
    pypdf = None

class PDFLeafletExtractor:
    """
    Extracts promotional items from the vector text layer of supermarket PDF flyers.
    """

    def __init__(self, store_id: str = "generic"):
        self.store_id = store_id

    def parse_page_text(self, text: str, page_num: int = 1, store_id: Optional[str] = None) -> List[PromoItem]:
        """Extract product promotions from a single text block/page."""
        store = store_id or self.store_id
        items: List[PromoItem] = []
        if not text:
            return items

        # Split into blocks by double newlines or clear delimiters
        raw_blocks = re.split(r"\n\s*\n", text)
        for block in raw_blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            # Check if block contains price information
            price_matches = re.findall(r"€\s*(\d+[\.,]\d{2})|(\d+[\.,]\d{2})\s*€", block)
            if not price_matches:
                continue

            prices = []
            for m in price_matches:
                p_str = m[0] or m[1]
                try:
                    prices.append(float(p_str.replace(",", ".")))
                except ValueError:
                    continue

            if not prices:
                continue

            # Candidate title: first line with sufficient length that is not a solitary price
            title = None
            desc_lines = []
            for line in lines:
                if not re.search(r"^[€\d\s\.,\+\-%]+$", line) and len(line) >= 3:
                    if title is None:
                        title = line
                    else:
                        desc_lines.append(line)

            if not title:
                continue

            promo_price = min(prices)
            orig_price = max(prices) if len(prices) > 1 and max(prices) > promo_price else None

            # Discount label search
            discount_text = "PROMO"
            for line in lines:
                if any(kw in line.lower() for kw in ["%", "gratis", "gratuit", "1+1", "2+2", "korting", "réduction"]):
                    discount_text = line
                    break

            fp = generate_fingerprint(
                store_id=store,
                title=title,
                promo_price=promo_price,
            )

            item = PromoItem(
                store_id=store,
                external_id=f"{store}_pdf_p{page_num}_{fp[:8]}",
                fingerprint=fp,
                title=title,
                description=" ".join(desc_lines[:2]),
                promo_price=promo_price,
                original_price=orig_price,
                discount_text=discount_text,
                category_id=infer_category(title, " ".join(desc_lines)),
                page_number=page_num,
                source_type="leaflet",
            )
            items.append(item)
        return items

    def extract_from_pdf_bytes(self, pdf_bytes: bytes, store_id: Optional[str] = None) -> List[PromoItem]:
        """Extract deals from vector text streams in a PDF."""
        store = store_id or self.store_id
        if not pypdf:
            logger.debug("pypdf is not installed. PDF vector extraction skipped.")
            return []

        items: List[PromoItem] = []
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for idx, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                page_items = self.parse_page_text(page_text, page_num=idx, store_id=store)
                items.extend(page_items)
        except Exception as err:
            logger.error(f"Error parsing PDF bytes for {store}: {err}")
        return items
