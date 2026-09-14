import pytest

from src.core.config import settings
from src.db.database import init_db, get_db_connection
from src.db.repository import Repository
from src.services.search_service import expand_search_terms


async def _like_search_ids(terms):
    """Reference implementation of the previous LIKE-based search."""
    terms = [t for t in terms if t.strip()]
    async with get_db_connection() as conn:
        clauses = []
        params = []
        for term in terms:
            clauses.append("(title LIKE ? OR description LIKE ?)")
            like = f"%{term}%"
            params.extend([like, like])
        sql = "SELECT id FROM promos WHERE " + " OR ".join(clauses)
        async with conn.execute(sql, params) as cursor:
            return {row["id"] for row in await cursor.fetchall()}


@pytest.mark.asyncio
async def test_fts_search_basic(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "fts_basic.db"))
    await init_db()

    await Repository.save_promo({
        "store_id": "colruyt",
        "title": "Côte d'Or Chocolade Melk 200g",
        "promo_price": 1.99,
        "category_id": "snacks_sweets",
    })
    await Repository.save_promo({
        "store_id": "aldi",
        "title": "Multi-Vitamines Bruistabletten 20",
        "promo_price": 3.49,
        "category_id": "care_baby",
    })
    await Repository.save_promo({
        "store_id": "lidl",
        "title": "3e HALVE PRIJS",
        "promo_price": 0.99,
        "category_id": "pantry",
    })

    async def titles(search_query):
        return {p["title"] for p in await Repository.get_promos(search_query=search_query)}

    assert "Côte d'Or Chocolade Melk 200g" in await titles("chocolade")
    assert "Côte d'Or Chocolade Melk 200g" in await titles("cote d'or")
    # unicode61 strips apostrophes from tokens, so the no-apostrophe spelling
    # matches too; this is the observed (and fixed-in-test) behaviour.
    assert "Côte d'Or Chocolade Melk 200g" in await titles("cote d or")
    assert "Multi-Vitamines Bruistabletten 20" in await titles("multi")
    assert "Multi-Vitamines Bruistabletten 20" in await titles("vitamines")
    assert "3e HALVE PRIJS" in await titles("3e")


@pytest.mark.asyncio
async def test_fts_upsert_no_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "fts_upsert.db"))
    await init_db()

    promo = {
        "store_id": "delhaize",
        "title": "Milsani Verse Volle Melk 1L",
        "promo_price": 0.89,
        "category_id": "dairy_cheese",
    }
    await Repository.save_promo(promo)
    await Repository.save_promo({**promo, "promo_price": 0.79})

    results = await Repository.get_promos(search_query="melk")
    assert len(results) == 1
    assert results[0]["title"] == "Milsani Verse Volle Melk 1L"
    assert results[0]["promo_price"] == 0.79


@pytest.mark.asyncio
async def test_fts_synonym_dedup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "fts_synonyms.db"))
    await init_db()

    await Repository.save_promo({
        "store_id": "aldi",
        "title": "Milsani Verse Volle Melk 1L",
        "promo_price": 0.89,
        "category_id": "dairy_cheese",
    })
    await Repository.save_promo({
        "store_id": "carrefour",
        "title": "Lait Demi Écrémé 1L",
        "promo_price": 0.95,
        "category_id": "dairy_cheese",
    })

    results = await Repository.get_promos(search_query="молоко")
    titles = {p["title"] for p in results}
    assert titles == {
        "Milsani Verse Volle Melk 1L",
        "Lait Demi Écrémé 1L",
    }


@pytest.mark.asyncio
async def test_fts_matches_like_for_dictionary_terms(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "fts_compare.db"))
    await init_db()

    dataset = [
        {"store_id": "aldi", "title": "Milsani Verse Volle Melk 1L", "promo_price": 0.89, "category_id": "dairy_cheese"},
        {"store_id": "carrefour", "title": "Lait Demi Écrémé 1L", "promo_price": 0.95, "category_id": "dairy_cheese"},
        {"store_id": "colruyt", "title": "Gouda Kaas Jong 500g", "promo_price": 4.29, "category_id": "dairy_cheese"},
        {"store_id": "delhaize", "title": "Jupiler Blond 24x25cl", "promo_price": 12.99, "category_id": "drinks"},
        {"store_id": "okay", "title": "Huile d'Olive Extra Vierge 1L", "promo_price": 5.49, "category_id": "pantry"},
        {"store_id": "lidl", "title": "Sucre Fin Cristallisé 1kg", "promo_price": 1.19, "category_id": "pantry"},
    ]
    for promo in dataset:
        await Repository.save_promo(promo)

    for query in ["молоко", "сир", "пиво", "олія", "цукор"]:
        fts_ids = {p["id"] for p in await Repository.get_promos(search_query=query)}
        like_ids = await _like_search_ids(expand_search_terms(query))
        assert fts_ids == like_ids, f"FTS/LIKE mismatch for {query!r}"
