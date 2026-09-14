import pytest
from src.services.search_service import expand_search_terms
from src.db.repository import Repository
from src.core.config import settings
from src.db.database import init_db

def test_multilingual_expansion():
    terms = expand_search_terms("молоко")
    assert "melk" in terms
    assert "lait" in terms
    assert "milk" in terms

    cheese_terms = expand_search_terms("сир")
    assert "kaas" in cheese_terms
    assert "fromage" in cheese_terms

    beer_terms = expand_search_terms("пиво")
    assert "bier" in beer_terms
    assert "jupiler" in beer_terms

    oil_terms = expand_search_terms("олія")
    assert "olie" in oil_terms
    assert "huile" in oil_terms

@pytest.mark.asyncio
async def test_multilingual_db_search():
    settings.DB_PATH = "data/test_search.db"
    await init_db()

    # Save a Dutch deal from Aldi/Colruyt: 'Verse Volle Melk'
    await Repository.save_promo({
        "store_id": "aldi",
        "title": "Milsani Verse Volle Melk 1L",
        "promo_price": 0.89,
        "discount_text": "-20%",
        "category_id": "dairy_cheese",
    })

    # Search in Ukrainian: 'молоко'
    results = await Repository.get_promos(search_query="молоко")
    assert len(results) >= 1
    assert "Melk" in results[0]["title"]

    import os
    if os.path.exists(settings.DB_PATH):
        os.remove(settings.DB_PATH)
