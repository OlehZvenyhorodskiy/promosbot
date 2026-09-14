"""Tests for the Jumbo Belgium PDF flyer scraper.

The text fixtures are real fragments extracted with pypdf from the verified
Week-38 in-store flyer (Jumbo-BE-Instore-Folder-2026-Week-38.pdf, 20 pages),
including the noise the text layer scatters between products ("6.-", "3 voor",
"1 .8 9", footnotes, decorative headings).
"""

import asyncio
import io
from datetime import date

import aiohttp
import pypdf
import pytest

from src.scrapers.jumbo import JumboScraper
from src.scrapers.leaflets.pdf_extractor import PDFLeafletExtractor

# --- real flyer fragments (page 1, 2, 3, 15, 16 and 17 of Week 38) ---------

PAGE_1 = """6.-
3 voor
  Woensdag 16  september t/m dinsdag 22 september 2026
Dr. Oetker Ristorante
Verpakking 295-390 gram. Alle soorten.
Prijsvoorbeeld: Dr. Oetker ristorante pizza salami 320 gram
€8.55 nu €6 voor 3 - €6.25/kg
Vanavond pizza? 
Da’s zo geregeld!"""

PAGE_2 = """Jumbo wokgranalen
Verpakking ca. 270 gram. Curry en provençal. 
Prijsvoorbeeld: Jumbo wokgarnalen provençaals ca. 270 gram
€17.49 nu €13.12 voor 2 - €24.29/kg
Jumbo kipdijfiletblokjes
Verpakking 350 gram.
€9.98 nu €7.49 voor 2 - €10.70/kg
de promo
op je bord
Inspiratie 
voor vandaag"""

PAGE_3 = """Jumbo 
rundshamburgers
Verpakking 400 gram. 
€7.99 nu €6 voor 1 - €15/kg
Jumbo broccoli, bloemkool, sperziebonen en snijbonen
Verpakking 400 gram.
Prijsvoorbeeld: Jumbo broccoliroosjes 400 gram
€2.99 nu €1.89 voor 1 - €4.73/kg
*3+1 gratis: 25% korting op de totaalprijs van 4 producten. Alle combinaties mogelijk. 
**2e halve prijs: 25% korting op de totaalprijs van 2 producten. Alle combinaties mogelijk."""

PAGE_16 = """1 .3 9 25%
Jumbo plantaardig 
gehakt rul gegaard 
Verpakking 200 gram - 
€6.95/kg
Jumbo gehakt mix van 
rund en plantaardig
Verpakking ca. 300 gram.
€5.40 nu €4.05 voor 1 - €13.50/kg
Niet elke dag 
vlees op je bord?"""

# The exact layout the reporter quoted for the Rummo deal: example and price
# share one line.
RUMMO_LINE = (
    "Prijsvoorbeeld: Rummo penne rigate № 66 500 gram €3.90 nu €1.95 voor 2 - €3.90/kg"
)

VALIDITY = "Woensdag 16  september t/m dinsdag 22 september 2026"


def parse(*pages: str):
    return JumboScraper.parse_leaflet_text(list(pages))


# --- parsing rules ---------------------------------------------------------

def test_real_page_1_yields_pizza_deal():
    items = parse(PAGE_1)

    assert len(items) == 1
    item = items[0]
    assert item.store_id == "jumbo"
    assert item.title == "Dr. Oetker ristorante pizza salami 320 gram"
    # Group heading + packaging lines above the example become the description.
    assert item.description == "Dr. Oetker Ristorante Verpakking 295-390 gram. Alle soorten."
    assert item.original_price == 8.55
    assert item.promo_price == 6.0
    assert item.discount_text == "-29%"
    assert item.unit_info == "voor 3"
    assert item.price_per_unit == 6.25
    assert item.valid_from == "2026-09-16"
    assert item.valid_until == "2026-09-22"
    assert item.page_number == 1
    assert item.source_type == "leaflet"
    assert item.external_id.startswith("jumbo_leaflet_p1_")
    assert item.fingerprint


def test_real_page_2_yields_both_products_and_drops_noise():
    items = parse(PAGE_2)

    assert [item.title for item in items] == [
        "Jumbo wokgarnalen provençaals ca. 270 gram",
        "Jumbo kipdijfiletblokjes",
    ]
    assert (items[0].original_price, items[0].promo_price) == (17.49, 13.12)
    assert items[0].discount_text == "-24%"
    # Packaging line walks title back to the product name.
    assert (items[1].original_price, items[1].promo_price) == (9.98, 7.49)
    assert items[1].description == "Verpakking 350 gram."
    # Decorative headings never leak into titles.
    assert all("promo" not in item.title.lower() for item in items)


def test_multiline_product_name_is_joined():
    items = parse(PAGE_3)

    assert items[0].title == "Jumbo rundshamburgers"
    assert items[0].description == "Verpakking 400 gram."
    assert items[0].valid_from is None  # no validity line on this page
    assert items[1].title == "Jumbo broccoliroosjes 400 gram"
    assert items[1].discount_text == "-36%"
    # Both footnotes are dropped, not turned into products.
    assert len(items) == 2


def test_unit_price_badge_bounds_the_block():
    items = parse(PAGE_16)

    assert len(items) == 1
    assert items[0].title == "Jumbo gehakt mix van rund en plantaardig"
    assert items[0].description == "Verpakking ca. 300 gram."
    assert (items[0].original_price, items[0].promo_price) == (5.4, 4.05)


def test_prijsvoorbeeld_and_price_on_one_line():
    items = parse(RUMMO_LINE)

    assert len(items) == 1
    assert items[0].title == "Rummo penne rigate № 66 500 gram"
    assert items[0].original_price == 3.9
    assert items[0].promo_price == 1.95
    assert items[0].discount_text == "-50%"


@pytest.mark.parametrize(
    ("line", "original", "promo"),
    [
        ("€8.55 nu €6 voor 3 - €6.25/kg", 8.55, 6.0),          # integer promo price
        ("€17.49 nu €13.12 voor 2", 17.49, 13.12),
        ("€19,99 nu €10,00", 19.99, 10.0),                      # comma separators
        ("€3,90 nu €1,95 voor 2 - €3,90/kg", 3.9, 1.95),
        ("nu €1.99", None, 1.99),                               # no original price
    ],
)
def test_price_line_variants(line, original, promo):
    items = parse("Jumbo testproduct\n" + line)

    assert len(items) == 1
    assert items[0].original_price == original
    assert items[0].promo_price == promo


def test_missing_original_price_uses_nu_label():
    items = parse("Jumbo cola\nFles 1,5 l\nnu €1.99")
    assert items[0].discount_text == "nu 1.99"


def test_gratis_marker_keeps_label_without_price():
    items = parse("Jumbo cola\nFles 1,5 l\n1+1 gratis")

    assert len(items) == 1
    assert items[0].title == "Jumbo cola"
    assert items[0].description == "Fles 1,5 l"
    assert items[0].discount_text == "1+1 gratis"
    assert items[0].promo_price is None
    assert items[0].original_price is None


@pytest.mark.parametrize("marker", ["2e gratis", "2e voor gratis", "2+2 gratis", "3+1 GRATIS"])
def test_gratis_marker_variants(marker):
    items = parse(f"Jumbo kaas\n{marker}")
    assert items[0].discount_text == marker


def test_gratis_marker_without_product_yields_nothing():
    assert parse("1+1 gratis") == []
    assert parse("€4.99 nu €2.49", "1+1 gratis") == []


def test_footnotes_are_not_products():
    assert parse("*1+1 gratis: 50% korting op de totaalprijs van 2 producten. Alle combinaties mogelijk.") == []
    assert parse("**2e halve prijs: 25% korting op de totaalprijs van 2 producten.") == []


def test_unicode_quotes_are_preserved():
    items = parse("Jumbo’s quiche zalm asperge 400 gram\n€7.49 nu €5.62 voor 1 - €14.05/kg")
    assert items[0].title == "Jumbo’s quiche zalm asperge 400 gram"


def test_badges_and_service_lines_never_become_titles():
    items = parse("1 .3 9 25%\n6.-\n1 voor\n€4.99 nu €2.49 voor 2")
    # No product name above the price line -> nothing to store.
    assert items == []


def test_price_badge_line_inside_block_is_ignored():
    items = parse("Jumbo verse soep\n6.-\n1 .8 9\nVerpakking 500 ml.\n€2.99 nu €1.99 voor 1")
    assert items[0].title == "Jumbo verse soep"
    assert items[0].description == "Verpakking 500 ml."


def test_validity_line_is_never_a_title():
    items = parse(VALIDITY, "Jumbo kaas\n€4.99 nu €2.49")
    assert [item.title for item in items] == ["Jumbo kaas"]


def test_pages_without_products_yield_nothing():
    assert parse("") == []
    assert parse("Trots oponze kwaliteit\nen prijs\n1 .2 8\nJumbo vegan burger\nVerpakking 200 gram - \n€6.40/kg") == []
    assert JumboScraper.parse_leaflet_text([]) == []


def test_page_numbers_are_assigned():
    items = parse("Jumbo kaas\n€4.99 nu €2.49", "Jumbo melk\n€1.99 nu €0.99")
    assert [item.page_number for item in items] == [1, 2]


def test_duplicate_products_are_deduplicated_by_fingerprint():
    page = "Jumbo kaas\n€4.99 nu €2.49"
    items = parse(page, page)
    assert len(items) == 1


def test_different_prices_are_not_deduplicated():
    items = parse("Jumbo kaas\n€4.99 nu €2.49", "Jumbo kaas\n€4.99 nu €1.99")
    assert len(items) == 2


def test_item_cap_is_200():
    page = "\n".join(f"Product {i}\n€{2 + i}.99 nu €1.99" for i in range(250))
    items = parse(page)
    assert len(items) == 200


def test_long_title_is_truncated():
    items = parse("Jumbo " + "x" * 400 + "\n€4.99 nu €2.49")
    assert len(items[0].title) == 255


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (VALIDITY, ("2026-09-16", "2026-09-22")),
        ("Woensdag 16 september t/m 22 september 2026", ("2026-09-16", "2026-09-22")),
        ("1 oktober t/m zondag 7 oktober 2026", ("2026-10-01", "2026-10-07")),
        ("geen datum hier", (None, None)),
        ("1 smarch t/m 7 smarch 2026", (None, None)),  # unknown month name
        ("30 februari t/m 2 maart 2026", (None, None)),  # impossible date
        ("", (None, None)),
    ],
)
def test_parse_validity_window(text, expected):
    assert JumboScraper._parse_validity_window(text) == expected


# --- flyer link selection --------------------------------------------------

HTML_WITH_FLYERS = """
<a href="https://www.jumbo.com/dam/belgie/2024/folder/2026/Jumbo-BE-Instore-Folder-2026-Week-37.pdf">
  <img src="https://www.jumbo.com/dam/belgie/2024/folder/2026/Jumbo-BE-Folder-2026-Aanbiedingen-Week-37-Thumb.jpg">
</a>
<a href="https://www.jumbo.com/dam/belgie/2026/folders/Jumbo-BE-Instore-Folder-2026-Week-38.pdf">
  <img src="https://www.jumbo.com/dam/belgie/2026/folders/Jumbo-BE-Folder-2026-Aanbiedingen-Week-38-Thumb.jpg">
</a>
<a href="https://www.jumbo.com/dam/belgie/2026/folders/Jumbo-BE-Instore-Folder-2026-Week-38.pdf">duplicate</a>
"""


def test_extract_pdf_links_dedupes_and_skips_thumbs():
    links = JumboScraper._extract_pdf_links(HTML_WITH_FLYERS)

    assert links == [
        "https://www.jumbo.com/dam/belgie/2024/folder/2026/Jumbo-BE-Instore-Folder-2026-Week-37.pdf",
        "https://www.jumbo.com/dam/belgie/2026/folders/Jumbo-BE-Instore-Folder-2026-Week-38.pdf",
    ]
    assert all(link.endswith(".pdf") and "Thumb" not in link for link in links)
    assert JumboScraper._extract_pdf_links("") == []
    assert JumboScraper._extract_pdf_links(None) == []


def test_select_flyer_url_ignores_document_order():
    """Verified live: the expired Week-37 link precedes the current Week-38."""
    links = JumboScraper._extract_pdf_links(HTML_WITH_FLYERS)
    assert JumboScraper._select_flyer_url(links, today=date(2026, 9, 15)).endswith("Week-38.pdf")


def test_select_flyer_url_ignores_future_flyers():
    links = [
        "https://www.jumbo.com/dam/belgie/2026/folders/Jumbo-BE-Instore-Folder-2026-Week-38.pdf",
        "https://www.jumbo.com/dam/belgie/2026/folders/Jumbo-BE-Instore-Folder-2026-Week-50.pdf",
    ]
    assert JumboScraper._select_flyer_url(links, today=date(2026, 9, 15)).endswith("Week-38.pdf")


def test_select_flyer_url_falls_back_to_future_flyer_when_only_option():
    links = ["https://www.jumbo.com/dam/belgie/2026/folders/Jumbo-BE-Instore-Folder-2026-Week-50.pdf"]
    assert JumboScraper._select_flyer_url(links, today=date(2026, 9, 15)).endswith("Week-50.pdf")


def test_select_flyer_url_without_week_numbers_uses_first_link():
    links = ["https://www.jumbo.com/dam/belgie/x/folder.pdf", "https://www.jumbo.com/dam/belgie/x/other.pdf"]
    assert JumboScraper._select_flyer_url(links) == links[0]


def test_select_flyer_url_handles_empty_input():
    assert JumboScraper._select_flyer_url([]) is None


# --- PDF text extraction ---------------------------------------------------

def test_extract_page_texts_reads_a_real_pdf():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)

    pages = PDFLeafletExtractor().extract_page_texts(buffer.getvalue())
    assert pages == [""]


def test_extract_page_texts_returns_empty_for_garbage():
    assert PDFLeafletExtractor().extract_page_texts(b"not a pdf") == []


# --- fetch flow ------------------------------------------------------------

class FakeResponse:
    def __init__(self, status: int = 200, text: str = "", payload: bytes = b"", exc: Exception | None = None):
        self.status = status
        self._text = text
        self._payload = payload
        self.exc = exc

    async def text(self, errors="ignore"):
        if self.exc:
            raise self.exc
        return self._text

    async def read(self):
        if self.exc:
            raise self.exc
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        return self.responses.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _patch_session(monkeypatch, session):
    monkeypatch.setattr("src.scrapers.jumbo.aiohttp.ClientSession", lambda *a, **kw: session)


def _pdf_bytes_with_page_text(text: str) -> bytes:
    """A minimal one-page PDF; pypdf reads an empty text layer from it, so the
    fetch flow is asserted on URL order rather than on parsed items."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def test_fetch_promos_walks_page_then_pdf(monkeypatch):
    scraper = JumboScraper()
    session = FakeSession([
        FakeResponse(status=200, text=HTML_WITH_FLYERS),
        FakeResponse(status=200, payload=_pdf_bytes_with_page_text("")),
    ])
    _patch_session(monkeypatch, session)

    assert await scraper.fetch_promos() == []
    assert session.urls[0] == "https://www.jumbo.com/nl-be/aanbiedingen"
    # The current flyer is downloaded, not the first link on the page.
    assert session.urls[1].endswith("Week-38.pdf")


async def test_fetch_promos_uses_parsed_leaflet_text(monkeypatch):
    scraper = JumboScraper()
    session = FakeSession([
        FakeResponse(status=200, text=HTML_WITH_FLYERS),
        FakeResponse(status=200, payload=b"%PDF-fake"),
    ])
    _patch_session(monkeypatch, session)
    monkeypatch.setattr(
        "src.scrapers.jumbo.PDFLeafletExtractor.extract_page_texts",
        lambda self, pdf_bytes: ["Jumbo kaas\n€4.99 nu €2.49"],
    )

    items = await scraper.fetch_promos()
    assert [item.title for item in items] == ["Jumbo kaas"]
    assert items[0].store_id == "jumbo"


async def test_fetch_promos_page_http_error_returns_empty(monkeypatch):
    scraper = JumboScraper()
    _patch_session(monkeypatch, FakeSession([FakeResponse(status=500)]))
    assert await scraper.fetch_promos() == []


async def test_fetch_promos_pdf_http_error_returns_empty(monkeypatch):
    scraper = JumboScraper()
    session = FakeSession([FakeResponse(status=200, text=HTML_WITH_FLYERS), FakeResponse(status=404)])
    _patch_session(monkeypatch, session)
    assert await scraper.fetch_promos() == []


async def test_fetch_promos_without_pdf_links_returns_empty(monkeypatch):
    scraper = JumboScraper()
    session = FakeSession([FakeResponse(status=200, text="<html>no flyers today</html>")])
    _patch_session(monkeypatch, session)
    assert await scraper.fetch_promos() == []
    assert len(session.urls) == 1


async def test_fetch_promos_unreadable_pdf_returns_empty(monkeypatch):
    scraper = JumboScraper()
    session = FakeSession([FakeResponse(status=200, text=HTML_WITH_FLYERS), FakeResponse(status=200, payload=b"not a pdf")])
    _patch_session(monkeypatch, session)
    assert await scraper.fetch_promos() == []


async def test_fetch_promos_timeout_returns_empty(monkeypatch):
    scraper = JumboScraper()
    _patch_session(monkeypatch, FakeSession([FakeResponse(exc=asyncio.TimeoutError())]))
    assert await scraper.fetch_promos() == []


async def test_fetch_promos_connection_error_returns_empty(monkeypatch):
    scraper = JumboScraper()

    class ExplodingSession:
        def get(self, url, timeout=None):
            raise aiohttp.ClientError("connection reset")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

    _patch_session(monkeypatch, ExplodingSession())
    assert await scraper.fetch_promos() == []
