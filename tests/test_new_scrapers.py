import json
import pytest
from src.scrapers.store_config import StoreConfig
from src.scrapers.action import ActionScraper
from src.scrapers.kruidvat import KruidvatScraper
from src.scrapers.delhaize import DelhaizeScraper
from src.scrapers.lidl import LidlScraper
from src.scrapers.okay import OkayScraper
from src.bot.formatters import format_promo_card


def test_store_config_definitions():
    stores = StoreConfig.get_all()
    assert len(stores) >= 14
    store_ids = {s.id for s in stores}
    assert "action" in store_ids
    assert "kruidvat" in store_ids
    assert "okay" in store_ids
    assert "bioplanet" in store_ids
    assert "colruyt" in store_ids

    action = StoreConfig.get("action")
    assert action is not None
    assert action.name == "Action"
    assert action.loyalty_card == "Action Club"

    colruyt = StoreConfig.get("colruyt")
    assert colruyt is not None
    assert colruyt.loyalty_card == "Xtra"


def test_action_scraper_html_parsing():
    scraper = ActionScraper()
    mock_html = """
    <html>
      <body>
        <div class="product-card">
          <h3 class="product-card__title">Ariel All-in-1 Pods 40 stuks</h3>
          <div class="price-current">€ 8,95</div>
          <div class="price-strike">€ 14,99</div>
          <span class="badge">Weekactie</span>
          <a href="/nl-be/p/ariel-pods/">Link</a>
          <img src="/media/ariel.jpg" />
        </div>
      </body>
    </html>
    """
    items = scraper.parse_html(mock_html)
    assert len(items) == 1
    item = items[0]
    assert item.store_id == "action"
    assert "Ariel All-in-1 Pods" in item.title
    assert item.promo_price == 8.95
    assert item.original_price == 14.99
    assert item.loyalty_card == "Action Club"
    assert item.calculate_discount_percentage() == 40.3


def test_action_scraper_next_data_parsing():
    scraper = ActionScraper()
    payload = {
        "props": {
            "pageProps": {
                "products": [
                    {
                        "id": "act-101",
                        "title": "Haribo Goudberen Snoep 500g",
                        "price": "2.49",
                        "oldPrice": "3.29",
                        "discountBadge": "-24%",
                        "category": "snacks",
                    }
                ]
            }
        }
    }
    mock_html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></html>'
    items = scraper.parse_html(mock_html)
    assert len(items) == 1
    item = items[0]
    assert item.title == "Haribo Goudberen Snoep 500g"
    assert item.promo_price == 2.49
    assert item.original_price == 3.29
    assert item.category_id == "snacks_sweets"


def test_kruidvat_scraper_hybris_api():
    scraper = KruidvatScraper()
    mock_api_data = {
        "products": [
            {
                "code": "56789",
                "name": "Nivea Q10 Anti-Rimpel Dagcrème 50ml",
                "summary": "Verstevigende dagcrème SPF 15",
                "price": {"value": 11.49, "formattedValue": "€ 11,49"},
                "potentialPromotions": [{"description": "1+1 gratis"}],
                "images": [{"format": "product", "url": "/medias/nivea.jpg"}],
                "url": "/nl/nivea-q10/p/56789",
            }
        ]
    }
    items = scraper.parse_json_api(mock_api_data)
    assert len(items) == 1
    item = items[0]
    assert item.store_id == "kruidvat"
    assert "Nivea Q10" in item.title
    assert item.promo_price == 11.49
    assert item.discount_text == "1+1 gratis"
    assert item.loyalty_card == "Kruidvat Club"
    assert item.deal_url == "https://www.kruidvat.be/nl/nivea-q10/p/56789"


def test_delhaize_scraper_loyalty_card():
    scraper = DelhaizeScraper()
    mock_html = """
    <html>
      <body>
        <div class="product-card">
          <h3 class="title">Verse Belgische Aardbeien 500g</h3>
          <div class="price">3 euro 99 cent</div>
          <span class="promo">1+1 GRATIS</span>
          <a href="/nl/aardbeien">Link</a>
        </div>
      </body>
    </html>
    """
    items = scraper.parse_html(mock_html)
    assert len(items) == 1
    item = items[0]
    assert item.store_id == "delhaize"
    assert "Aardbeien" in item.title
    assert item.promo_price == 3.99
    assert item.loyalty_card == "SuperPlus"


def test_okay_scraper_parsing():
    scraper = OkayScraper()
    mock_html = """
    <html>
      <body>
        <div class="promo-card">
          <h3 class="name">Danone Activia Yoghurt 4x125g</h3>
          <div class="price">€ 2,19</div>
          <span class="badge">-33% vanaf 2 verpakkingen</span>
          <a href="/nl/activia">Link</a>
        </div>
      </body>
    </html>
    """
    items = scraper.parse_html(mock_html)
    assert len(items) == 1
    item = items[0]
    assert item.store_id == "okay"
    assert "Danone Activia" in item.title
    assert item.promo_price == 2.19
    assert item.loyalty_card == "Xtra"


def test_format_promo_card_loyalty():
    promo_xtra = {
        "store_id": "colruyt",
        "title": "Jupiler Pils 24x33cl",
        "promo_price": 14.99,
        "original_price": 19.99,
        "discount_text": "-25%",
        "loyalty_card": "Xtra",
        "category_id": "drinks",
    }
    card_en = format_promo_card(promo_xtra, lang="en")
    assert "With Xtra" in card_en
    assert "Colruyt" in card_en

    card_uk = format_promo_card(promo_xtra, lang="uk")
    assert "З карткою Xtra" in card_uk
