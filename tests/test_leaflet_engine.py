import pytest
import uuid
import os
from unittest.mock import AsyncMock, patch
from src.core.config import settings
from src.db.database import init_db
from src.db.repository import Repository
from src.scrapers.leaflets.publitas import PublitasLeafletExtractor
from src.scrapers.leaflets.tiendeo import TiendeoAggregator
from src.scrapers.leaflets.pdf_extractor import PDFLeafletExtractor
from src.scrapers.leaflets.orchestrator import LeafletOrchestrator

def test_publitas_hotspots_parsing():
    extractor = PublitasLeafletExtractor(store_id="albert_heijn", retailer_group="albert-heijn-belgie")
    sample_hotspots = [
        {
            "id": "hp_101",
            "title": "Chiquita Bananen 1kg",
            "description": "Verse bananen uit Costa Rica",
            "price": {"current": 1.49, "original": 1.99},
            "discount_label": "-25%",
            "page": 2,
            "image_url": "https://example.com/banana.jpg",
            "bounds": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
        },
        {
            "id": "hp_102",
            "title": "Alpro Havermelk",
            "description": "Plantaardige melk € 1,89 per fles",
            "page": 3,
        }
    ]

    items = extractor.parse_hotspots_data(sample_hotspots, publication_id="week_37")
    assert len(items) == 2

    # Check item 1
    assert items[0].store_id == "albert_heijn"
    assert items[0].title == "Chiquita Bananen 1kg"
    assert items[0].promo_price == 1.49
    assert items[0].original_price == 1.99
    assert items[0].discount_text == "-25%"
    assert items[0].page_number == 2
    assert items[0].source_type == "leaflet"
    assert items[0].fingerprint is not None

    # Check item 2 fallback price parsing from description
    assert items[1].promo_price == 1.89
    assert items[1].page_number == 3
    assert items[1].source_type == "leaflet"

def test_tiendeo_deal_parsing():
    aggregator = TiendeoAggregator()

    # Retailer slug mapping
    assert aggregator.map_store_id("carrefour-market") == "carrefour"
    assert aggregator.map_store_id("ad-delhaize") == "delhaize"
    assert aggregator.map_store_id("albert-heijn") == "albert_heijn"

    sample_deal = {
        "id": "td_999",
        "title": "Stella Artois Bak 24x33cl",
        "retailer": "colruyt",
        "price": "€ 14,99",
        "original_price": "€ 18,99",
        "discount": "1+1 GRATIS",
        "description": "Belgisch pils bier",
        "page": 5,
        "valid_until": "2026-09-30",
    }

    item = aggregator.parse_deal(sample_deal)
    assert item is not None
    assert item.store_id == "colruyt"
    assert item.title == "Stella Artois Bak 24x33cl"
    assert item.promo_price == 14.99
    assert item.original_price == 18.99
    assert item.discount_text == "1+1 GRATIS"
    assert item.source_type == "aggregator"
    assert item.category_id == "drinks"

def test_pdf_vector_text_parsing():
    extractor = PDFLeafletExtractor(store_id="aldi")

    sample_page_text = """
    ALDI WEEKFOLDER - GELDIG VANAF MAANDAG

    Gouda Jong Belegen
    500g blok
    € 3,49
    -20% KORTING

    Verse Belgische Aardbeien
    500g schaaltje
    € 2,99
    """

    items = extractor.parse_page_text(sample_page_text, page_num=1)
    assert len(items) >= 2
    titles = [it.title for it in items]
    assert any("Gouda" in t for t in titles)
    assert any("Aardbeien" in t for t in titles)
    assert any(it.promo_price == 3.49 for it in items)

def test_pdf_extract_from_bytes():
    import io
    from pypdf import PdfWriter
    extractor = PDFLeafletExtractor(store_id="aldi")

    # Corrupt / invalid bytes returns [] safely
    assert extractor.extract_from_pdf_bytes(b"invalid pdf data") == []

    # Valid in-memory PDF
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    items = extractor.extract_from_pdf_bytes(buf.getvalue())
    assert isinstance(items, list)

@pytest.mark.asyncio
async def test_leaflet_orchestrator_save():
    test_db = f"data/test_{uuid.uuid4().hex[:8]}.db"
    settings.DB_PATH = test_db
    try:
        await init_db()
        orchestrator = LeafletOrchestrator()

        mock_item = PublitasLeafletExtractor("jumbo").parse_hotspots_data([
            {
                "id": "hp_jumbo_1",
                "title": "Jumbo Croissants 4 stuks",
                "price": {"current": 1.25},
                "discount_label": "Super Deal",
                "page": 1,
            }
        ], publication_id="jumbo_w37")[0]

        with patch.object(orchestrator, "fetch_all_leaflets", new=AsyncMock(return_value=[mock_item])):
            new_count = await orchestrator.ingest_and_save_leaflets()
            assert new_count == 1

            # Ingesting again should result in 0 new items due to fingerprint deduplication
            new_count_dup = await orchestrator.ingest_and_save_leaflets()
            assert new_count_dup == 0

            promos = await Repository.get_promos(store_ids=["jumbo"])
            assert len(promos) == 1
            assert promos[0]["source_type"] == "leaflet"
            assert promos[0]["title"] == "Jumbo Croissants 4 stuks"
    finally:
        try:
            if os.path.exists(test_db):
                os.remove(test_db)
        except Exception:
            pass
