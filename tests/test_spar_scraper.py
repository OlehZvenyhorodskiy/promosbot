"""Tests for the Spar AEM model scraper (mijnspar.be).

Fixtures mirror the structures verified against the live endpoint
(2026-09-15): a `results` list of promo cards, each with a `promotion` object
carrying split price blocks, epoch-milli dates and `localizedTags` such as
"1+1 gratis". Three of the 42 live cards are day-price vegetables without any
price block (`empty: true`).
"""

import asyncio

import aiohttp
import pytest

from src.scrapers.spar import (
    SparScraper,
    discount_text_from_tags,
    epoch_ms_to_iso,
    formatted_date_to_iso,
    parse_price_block,
)

# Real values from the live endpoint: 2026-09-09 .. 2026-09-22.
START_MS = 1788991200000
END_MS = 1790114400000


def make_result(index: int = 1, **overrides) -> dict:
    """A promo card exactly as returned by the model endpoint."""
    result = {
        "uuid": f"cefc129{index}",
        "localizedTags": [
            {"iconPath": "", "title": "1+1 gratis", "tagID": "spar:promoties-system/labels/11-gratis", "name": "11-gratis"},
            {"iconPath": "", "title": "Vlees vis veggie traiteur", "tagID": "spar:promoties-system/category/x", "name": "x"},
        ],
        "promotion": {
            "promoTitle": "Spar",
            "promoDescription": "loempia’s met kip en groenten 2 stuks 400 g",
            "normalPrice": {"beforeDecimal": "10", "afterDecimal": "72", "afterDecimalStringCheck": "72", "empty": False},
            "promoPrice": {"beforeDecimal": "5", "afterDecimal": "36", "afterDecimalStringCheck": "36", "empty": False},
            "unitPrice": {"beforeDecimal": "2", "afterDecimal": "68", "empty": False},
            "unitOfUnitPrice": "kg",
            "xtraPromoCheck": True,
            "startDate": START_MS,
            "endDate": END_MS,
            "formattedStartDate": "10/9",
            "formattedEndDate": "23/9/2026",
            "promoAssetPath": "/content/dam/spar/promo-nieuw/productfotos/10639-58740-58720.jpg",
            "campaignLabel": "",
        },
    }
    result.update(overrides)
    return result


def make_day_price_result() -> dict:
    """Card verified live: aubergine on a day price has no price block at all."""
    return make_result(
        2,
        uuid="cd35982d",
        localizedTags=[
            {"iconPath": "", "title": "-25%", "tagID": "spar:promoties-system/labels/25-korting", "name": "25-korting"},
            {"iconPath": "", "title": "Groenten & fruit", "tagID": "spar:promoties-system/category/groenten-fruit", "name": "groenten-fruit"},
        ],
        promotion={
            "promoTitle": "aubergine",
            "promoDescription": "België/Nederland, op dagprijs",
            "normalPrice": {"beforeDecimal": None, "afterDecimal": None, "empty": True},
            "unitPrice": {"beforeDecimal": None, "afterDecimal": None, "empty": True},
            "promoPrice": {"beforeDecimal": None, "afterDecimal": None, "empty": True},
            "startDate": START_MS,
            "endDate": END_MS,
            "formattedStartDate": "10/9/2026",
            "formattedEndDate": "23/9/2026",
            "promoAssetPath": "/content/dam/spar/promo-nieuw/productfotos/aubergine.jpg",
        },
    )


def test_parse_full_result():
    scraper = SparScraper()
    items = scraper._parse_results([make_result(1)])

    assert len(items) == 1
    item = items[0]
    assert item.store_id == "spar"
    assert item.title == "Spar — loempia’s met kip en groenten 2 stuks 400 g"
    assert item.description == "loempia’s met kip en groenten 2 stuks 400 g"
    assert item.original_price == 10.72
    assert item.promo_price == 5.36
    assert item.discount_text == "1+1 gratis"
    assert item.valid_from == "2026-09-09"  # epoch wins over the short "10/9"
    assert item.valid_until == "2026-09-22"
    assert item.image_url == (
        "https://www.mijnspar.be/content/dam/spar/promo-nieuw/productfotos/10639-58740-58720.jpg"
    )
    assert item.external_id == "spar_cefc1291"
    assert item.price_per_unit == 2.68
    assert item.unit_info == "kg"
    assert item.loyalty_card == "Xtra"
    assert item.source_type == "api"
    assert item.fingerprint


def test_three_live_shaped_results_yield_two_items():
    """1 full card, 1 day-price card, 1 card without a promotion -> 2 items."""
    scraper = SparScraper()
    results = [make_result(1), make_day_price_result(), {"uuid": "no-promo", "localizedTags": []}]
    items = scraper._parse_results(results)

    assert len(items) == 2
    assert [item.title.split(" —")[0] for item in items] == ["Spar", "aubergine"]


def test_day_price_card_keeps_title_without_inventing_prices():
    scraper = SparScraper()
    item = scraper._parse_results([make_day_price_result()])[0]

    assert item.promo_price is None
    assert item.original_price is None
    assert item.price_per_unit is None
    assert item.title == "aubergine — België/Nederland, op dagprijs"
    # No "gratis" tag on this card -> generic label, not a fabricated discount.
    assert item.discount_text == "PROMO"


def test_multiple_gratis_tag_keeps_its_own_title():
    scraper = SparScraper()
    result = make_result(
        3,
        localizedTags=[
            {"title": "Groenten & fruit"},
            {"title": "2+2 gratis "},  # live data carries a trailing space
        ],
    )
    assert scraper._parse_results([result])[0].discount_text == "2+2 gratis"


def test_dates_fall_back_to_formatted_when_epoch_missing():
    scraper = SparScraper()
    result = make_result(4)
    result["promotion"].pop("startDate")
    result["promotion"].pop("endDate")
    item = scraper._parse_results([result])[0]

    assert item.valid_from is None  # "10/9" has no year
    assert item.valid_until == "2026-09-23"

    result["promotion"]["formattedStartDate"] = "10/09/2026"
    item = scraper._parse_results([result])[0]
    assert item.valid_from == "2026-09-10"


def test_title_is_truncated_to_255_characters():
    scraper = SparScraper()
    result = make_result(5)
    result["promotion"]["promoDescription"] = "x" * 400
    item = scraper._parse_results([result])[0]
    assert len(item.title) == 255


def test_cards_without_uuid_use_fingerprint_as_external_id():
    scraper = SparScraper()
    result = make_result(6)
    result.pop("uuid")
    item = scraper._parse_results([result])[0]
    assert item.external_id == item.fingerprint


def test_deduplicate_keeps_one_card_per_uuid():
    scraper = SparScraper()
    items = scraper._parse_results([make_result(1), make_result(1)])
    assert len(scraper._deduplicate(items)) == 1


def test_image_url_prefixing():
    scraper = SparScraper()
    relative = scraper._parse_results([make_result(7)])[0]
    assert relative.image_url.startswith("https://www.mijnspar.be/content/dam/")

    result = make_result(8)
    result["promotion"]["promoAssetPath"] = "https://cdn.example.com/a.jpg"
    assert scraper._parse_results([result])[0].image_url == "https://cdn.example.com/a.jpg"

    result = make_result(9)
    result["promotion"].pop("promoAssetPath")
    assert scraper._parse_results([result])[0].image_url is None


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        ({"beforeDecimal": "10", "afterDecimal": "72", "empty": False}, 10.72),
        ({"beforeDecimal": "0", "afterDecimal": "99", "empty": False}, 0.99),
        ({"beforeDecimal": "6", "afterDecimal": "5", "empty": False}, 6.05),
        ({"beforeDecimal": "10", "afterDecimal": "72", "empty": True}, None),
        ({"beforeDecimal": None, "afterDecimal": None, "empty": True}, None),
        ({"beforeDecimal": None, "afterDecimal": "72", "empty": False}, None),
        ({"beforeDecimal": "10", "afterDecimal": "999", "empty": False}, None),
        ({"beforeDecimal": "abc", "afterDecimal": "72", "empty": False}, None),
        (None, None),
        ("10.72", None),
    ],
)
def test_parse_price_block(block, expected):
    assert parse_price_block(block) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (START_MS, "2026-09-09"),
        (END_MS, "2026-09-22"),
        (None, None),
        ("", None),
        ("not-a-number", None),
    ],
)
def test_epoch_ms_to_iso(raw, expected):
    assert epoch_ms_to_iso(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("23/9/2026", "2026-09-23"),
        ("10/09/2026", "2026-09-10"),
        ("10/9", None),  # year-less short form is unusable
        ("", None),
        (None, None),
    ],
)
def test_formatted_date_to_iso(raw, expected):
    assert formatted_date_to_iso(raw) == expected


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ([{"title": "1+1 gratis"}, {"title": "Groenten & fruit"}], "1+1 gratis"),
        ([{"title": "Groenten & fruit"}, {"title": "2+2 gratis "}], "2+2 gratis"),
        ([{"title": "-25%"}, {"title": "Groenten & fruit"}], "PROMO"),
        ([], "PROMO"),
        (None, "PROMO"),
        (["not-a-dict", {"title": "1+1 GRATIS"}], "1+1 GRATIS"),
    ],
)
def test_discount_text_from_tags(tags, expected):
    assert discount_text_from_tags(tags) == expected


class FakeResponse:
    def __init__(self, status: int = 200, payload: dict | None = None, exc: Exception | None = None):
        self.status = status
        self.payload = payload or {}
        self.exc = exc

    async def json(self, content_type=None):
        if self.exc:
            raise self.exc
        return self.payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeSession:
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
    monkeypatch.setattr("src.scrapers.spar.aiohttp.ClientSession", lambda *a, **kw: session)


async def test_fetch_promos_reads_the_model_endpoint(monkeypatch):
    scraper = SparScraper()
    session = FakeSession([FakeResponse(status=200, payload={"results": [make_result(1)]})])
    _patch_session(monkeypatch, session)

    items = await scraper.fetch_promos()
    assert len(items) == 1
    assert session.urls == [scraper.url]
    assert "filter_list_store_sp.model.json" in scraper.url


async def test_http_500_returns_empty_list(monkeypatch):
    scraper = SparScraper()
    _patch_session(monkeypatch, FakeSession([FakeResponse(status=500)]))
    assert await scraper.fetch_promos() == []


async def test_timeout_returns_empty_list(monkeypatch):
    scraper = SparScraper()
    _patch_session(monkeypatch, FakeSession([FakeResponse(exc=asyncio.TimeoutError())]))
    assert await scraper.fetch_promos() == []


async def test_malformed_payload_returns_empty_list(monkeypatch):
    scraper = SparScraper()
    _patch_session(monkeypatch, FakeSession([FakeResponse(status=200, payload=["not", "a", "dict"])]))
    assert await scraper.fetch_promos() == []

    _patch_session(
        monkeypatch,
        FakeSession([FakeResponse(status=200, payload={"results": ["not-a-card", {"promotion": "not-a-dict"}]})]),
    )
    assert await scraper.fetch_promos() == []


async def test_connection_error_returns_empty_list(monkeypatch):
    scraper = SparScraper()

    class ExplodingSession:
        def get(self, url, timeout=None):
            raise aiohttp.ClientError("connection reset")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

    _patch_session(monkeypatch, ExplodingSession())
    assert await scraper.fetch_promos() == []
