"""Tests for the Bio-Planet gateway scraper (apip.bioplanet.be).

Fixtures mirror the structures verified against the live gateway:
products with price.basicPrice and a promotion[] list carrying techPromoId /
promotionId / publication dates (DD-MM-YYYY), plus promotion details from the
promotionretrsvc endpoint with benefit tiers.
"""

import asyncio

import aiohttp
import pytest

from src.scrapers.bioplanet import BioplanetScraper, _normalize_date


def make_product(index: int = 1, **overrides) -> dict:
    """A promo product exactly as returned by the products endpoint."""
    product = {
        "name": "komkommer Bio",
        "description": "Biologische komkommer per stuk",
        "fullImage": f"https://static.colruytgroup.com/images/bioplanet/{index}/full.jpg",
        "thumbNail": f"https://static.colruytgroup.com/images/bioplanet/{index}/thumb.jpg",
        "commercialArticleNumber": f"5000{index:03d}",
        "price": {
            "basicPrice": 3.95,
            "measurementUnit": "stuk",
            "pricePerUOM": 3.95,
        },
        "promotion": [
            {
                "techPromoId": f"9000001{index}",
                "promotionId": f"8000001{index}",
                "promotionType": "PERCENTAGE",
                "isPersonalized": "N",
                "publicationStartDate": "12-09-2026",
                "publicationEndDate": "26-09-2026",
                "topPromo": True,
            }
        ],
    }
    product.update(overrides)
    return product


def make_promotion_detail(promotion_id: str, **overrides) -> dict:
    """A promotion detail as returned by the promotionretrsvc endpoint."""
    detail = {
        "promotionId": promotion_id,
        "commercialPromotionId": f"C{promotion_id}",
        "promotionKind": "PERCENTAGE",
        "publicationStartDate": "2026-09-12",
        "publicationEndDate": "2026-09-26",
        "activeStartDate": "2026-09-14",
        "activeEndDate": "2026-09-25",
        "benefit": [
            {
                "benefitPercentage": 25.0,
                "minLimit": 2,
                "maxLimit": None,
                "limitUnit": "PCE",
                "sequence": 1,
            }
        ],
    }
    detail.update(overrides)
    return detail


def test_parse_product_with_promotion_details():
    scraper = BioplanetScraper()
    product = make_product(1)
    detail = make_promotion_detail("80000011")
    items = scraper._parse_products([product], {"80000011": detail})

    assert len(items) == 1
    item = items[0]
    assert item.store_id == "bioplanet"
    assert item.title == "komkommer Bio"
    assert item.description == "Biologische komkommer per stuk"
    assert item.original_price == 3.95
    assert item.discount_text == "-25% vanaf 2"
    assert item.promo_price == 2.96  # 3.95 * (1 - 0.25), rounded to cents
    assert item.valid_from == "2026-09-14"  # active window preferred
    assert item.valid_until == "2026-09-25"
    assert item.external_id == "bioplanet_90000011_5000001"
    assert item.image_url == "https://static.colruytgroup.com/images/bioplanet/1/full.jpg"
    assert item.unit_info == "stuk"
    assert item.price_per_unit == 3.95
    assert item.category_id == "fruits_veg"
    assert item.loyalty_card == "Xtra"
    assert item.source_type == "api"
    assert item.fingerprint


def test_parse_product_falls_back_to_product_promotion():
    """When the details service answers 200 with nothing, use product data only."""
    scraper = BioplanetScraper()
    items = scraper._parse_products([make_product(1)], {})

    assert len(items) == 1
    item = items[0]
    assert item.discount_text == "PROMO"
    assert item.promo_price is None
    assert item.original_price == 3.95
    # DD-MM-YYYY publication dates from the product are normalized to ISO.
    assert item.valid_from == "2026-09-12"
    assert item.valid_until == "2026-09-26"


def test_personalized_promotions_are_skipped():
    scraper = BioplanetScraper()
    product = make_product(1)
    product["promotion"][0]["isPersonalized"] = "Y"
    assert scraper._parse_products([product], {}) == []


def test_products_without_name_or_promotions_are_skipped():
    scraper = BioplanetScraper()
    assert scraper._parse_products([make_product(1, name="")], {}) == []
    assert scraper._parse_products([make_product(1, promotion=[])], {}) == []


def test_discount_text_from_benefit_percentage():
    scraper = BioplanetScraper()
    # Percentage without a minimum limit
    discount, price = scraper._discount_from_benefit({"benefitPercentage": 50.0}, 4.00)
    assert discount == "-50%"
    assert price == 2.00

    # Missing benefit -> generic label, no invented promo price
    discount, price = scraper._discount_from_benefit(None, 4.00)
    assert discount == "PROMO"
    assert price is None

    discount, price = scraper._discount_from_benefit({"benefitPercentage": None}, 4.00)
    assert discount == "PROMO"
    assert price is None


def test_primary_benefit_uses_lowest_sequence_tier():
    scraper = BioplanetScraper()
    detail = {
        "benefit": [
            {"benefitPercentage": 10.0, "minLimit": 1, "sequence": 2},
            {"benefitPercentage": 25.0, "minLimit": 2, "sequence": 1},
        ]
    }
    items = scraper._parse_products([make_product(1)], {"80000011": detail})
    assert items[0].discount_text == "-25% vanaf 2"


def test_external_id_is_stable_per_promotion_and_article():
    scraper = BioplanetScraper()
    items = scraper._parse_products([make_product(1)], {})
    again = scraper._parse_products([make_product(1)], {})
    assert items[0].external_id == again[0].external_id


def test_chunk_ids_limits_url_length():
    ids = [str(i) for i in range(25)]
    chunks = BioplanetScraper._chunk_ids(ids)
    assert [len(c) for c in chunks] == [10, 10, 5]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12-09-2026", "2026-09-12"),
        ("2026-09-12", "2026-09-12"),
        (None, None),
        ("", None),
        ("12/09/2026", "12/09/2026"),  # unknown format is passed through
    ],
)
def test_normalize_date(raw, expected):
    assert _normalize_date(raw) == expected


async def test_pagination_stops_on_short_page(monkeypatch):
    scraper = BioplanetScraper()
    pages = {
        1: [make_product(i) for i in range(50)],
        2: [make_product(100 + i) for i in range(50)],
        3: [],
    }
    calls = []

    async def fake_products_page(session, page):
        calls.append(page)
        return pages.get(page)

    async def fake_details(products):
        return {}

    monkeypatch.setattr(scraper, "_fetch_products_page", fake_products_page)
    monkeypatch.setattr(scraper, "_fetch_promotion_details", fake_details)

    items = await scraper.fetch_promos()
    assert calls == [1, 2, 3]
    assert len(items) == 100


async def test_pagination_caps_at_max_pages(monkeypatch):
    scraper = BioplanetScraper()
    calls = []

    async def fake_products_page(session, page):
        calls.append(page)
        return [make_product(page * 100 + i) for i in range(50)]

    async def fake_details(products):
        return {}

    monkeypatch.setattr(scraper, "_fetch_products_page", fake_products_page)
    monkeypatch.setattr(scraper, "_fetch_promotion_details", fake_details)

    items = await scraper.fetch_promos()
    assert calls == [1, 2, 3, 4, 5, 6]
    assert len(items) == 300


class FakeResponse:
    def __init__(self, status: int = 200, payload: dict | None = None, exc: Exception | None = None):
        self.status = status
        self.payload = payload or {}
        self.exc = exc

    async def json(self):
        if self.exc:
            raise self.exc
        return self.payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeApiSession:
    """Session returning queued responses for each GET, recording URLs."""

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
    def factory(*args, **kwargs):
        return session

    monkeypatch.setattr("src.scrapers.bioplanet.aiohttp.ClientSession", factory)


async def test_http_500_returns_empty_list(monkeypatch):
    scraper = BioplanetScraper()
    _patch_session(monkeypatch, FakeApiSession([FakeResponse(status=500)]))
    assert await scraper.fetch_promos() == []


async def test_timeout_returns_empty_list(monkeypatch):
    scraper = BioplanetScraper()
    timeout = asyncio.TimeoutError()
    _patch_session(monkeypatch, FakeApiSession([FakeResponse(exc=timeout)]))
    assert await scraper.fetch_promos() == []


async def test_promotion_details_chunks_and_client_code(monkeypatch):
    """Every details call must carry clientCode=BIOBE and <=10 ids per URL."""
    scraper = BioplanetScraper()
    products = [make_product(i) for i in range(1, 26)]  # 25 distinct promotion ids
    # Each product exposes both techPromoId and promotionId -> 50 ids total.
    session = FakeApiSession([FakeResponse(status=200, payload={"promotion": []}) for _ in range(5)])
    _patch_session(monkeypatch, session)

    details = await scraper._fetch_promotion_details(products)
    assert details == {}
    assert len(session.urls) == 5  # 50 ids / 10 per chunk
    for url in session.urls:
        assert "clientCode=BIOBE" in url
        query_ids = url.split("promotionIds=")[1].split("&")[0].split(",")
        assert 1 <= len(query_ids) <= 10


async def test_promotion_details_error_is_swallowed(monkeypatch):
    scraper = BioplanetScraper()

    class ExplodingSession:
        def get(self, url, timeout=None):
            raise aiohttp.ClientError("connection reset")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

    _patch_session(monkeypatch, ExplodingSession())
    assert await scraper._fetch_promotion_details([make_product(1)]) == {}


async def test_promotion_details_join_by_tech_promo_id(monkeypatch):
    scraper = BioplanetScraper()
    detail = make_promotion_detail("80000011")
    payload = {"clientCode": "BIOBE", "promotion": [detail]}
    session = FakeApiSession([FakeResponse(status=200, payload=payload)])
    _patch_session(monkeypatch, session)

    details = await scraper._fetch_promotion_details([make_product(1)])
    items = scraper._parse_products([make_product(1)], details)
    assert items[0].discount_text == "-25% vanaf 2"
    assert items[0].promo_price == 2.96
