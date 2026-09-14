import pytest
import uuid
from src.core.config import settings
from src.db.database import init_db
from src.db.repository import Repository
from src.services.price_comparator import PriceComparator


@pytest.mark.asyncio
async def test_cart_functionality():
    test_db = f"data/test_cart_{uuid.uuid4().hex[:8]}.db"
    settings.DB_PATH = test_db
    try:
        await init_db()
        user_id = 998877
        await Repository.get_or_create_user(user_id, "testuser", "Tester")

        # Save two promo deals with original prices and discounts
        deal1 = {
            "store_id": "colruyt",
            "title": "Jupiler Pils 24x33cl",
            "original_price": 20.00,
            "promo_price": 15.00,
            "discount_text": "-25%",
            "category_id": "drinks",
        }
        deal2 = {
            "store_id": "action",
            "title": "Ariel Pods 40 stuks",
            "original_price": 10.00,
            "promo_price": 6.00,
            "discount_text": "-40%",
            "category_id": "household",
        }
        id1, _ = await Repository.save_promo(deal1)
        id2, _ = await Repository.save_promo(deal2)

        # Initially cart is empty
        assert await Repository.is_in_cart(user_id, id1) is False
        cart_empty = await Repository.get_user_cart(user_id)
        assert len(cart_empty) == 0

        # Toggle item 1 into cart
        added1 = await Repository.toggle_cart(user_id, id1)
        assert added1 is True
        assert await Repository.is_in_cart(user_id, id1) is True

        # Toggle item 2 into cart
        added2 = await Repository.toggle_cart(user_id, id2)
        assert added2 is True
        assert await Repository.is_in_cart(user_id, id2) is True

        cart_items = await Repository.get_user_cart(user_id)
        assert len(cart_items) == 2

        # Check cart totals & savings calculation
        totals = await Repository.get_cart_totals(user_id)
        assert totals["count"] == 2
        assert totals["total_promo"] == 21.00 # 15 + 6
        assert totals["total_regular"] == 30.00 # 20 + 10
        assert totals["savings"] == 9.00 # 30 - 21
        assert totals["saving_percent"] == 30.0

        # Toggle item 1 off
        removed1 = await Repository.toggle_cart(user_id, id1)
        assert removed1 is False
        assert await Repository.is_in_cart(user_id, id1) is False
        assert len(await Repository.get_user_cart(user_id)) == 1

        # Clear cart
        cleared = await Repository.clear_user_cart(user_id)
        assert cleared == 1
        assert len(await Repository.get_user_cart(user_id)) == 0
    finally:
        pass


def test_price_comparator_keyword_extraction():
    keywords1 = PriceComparator.extract_core_keywords("Jupiler Pils 24x33cl Bak")
    assert "Jupiler" in keywords1
    assert "Pils" in keywords1
    assert "24x33cl" not in keywords1

    keywords2 = PriceComparator.extract_core_keywords("Nutella Chocopasta 750g 1+1 GRATIS")
    assert "Nutella" in keywords2
    assert "Chocopasta" in keywords2
    assert "750g" not in keywords2
    assert "gratis" not in [k.lower() for k in keywords2]


@pytest.mark.asyncio
async def test_price_comparator_competitor_search():
    test_db = f"data/test_cmp_{uuid.uuid4().hex[:8]}.db"
    settings.DB_PATH = test_db
    try:
        await init_db()

        # Colruyt deal: Jupiler 14.99
        p1 = {
            "store_id": "colruyt",
            "title": "Jupiler Pils 24x33cl",
            "promo_price": 14.99,
            "original_price": 19.99,
            "discount_text": "-25%",
        }
        # Carrefour deal: Jupiler 17.50
        p2 = {
            "store_id": "carrefour",
            "title": "Jupiler Pils 24x33cl Krat",
            "promo_price": 17.50,
            "original_price": 19.99,
            "discount_text": "-12%",
        }
        # Aldi deal: Jupiler 18.00
        p3 = {
            "store_id": "aldi",
            "title": "Jupiler Pils Blond Bier 24x33cl",
            "promo_price": 18.00,
            "original_price": 19.99,
            "discount_text": "Aanbieding",
        }
        await Repository.save_promo(p1)
        await Repository.save_promo(p2)
        await Repository.save_promo(p3)

        competitors = await PriceComparator.find_competitor_prices(p1)
        assert len(competitors) == 2
        comp_stores = {c["store_id"] for c in competitors}
        assert "colruyt" not in comp_stores
        assert "carrefour" in comp_stores
        assert "aldi" in comp_stores

        # Verification of message formatting
        msg_uk = PriceComparator.format_comparison_message(p1, competitors, lang="uk")
        assert "Порівняння цін" in msg_uk
        assert "Colruyt" in msg_uk
        assert "Carrefour" in msg_uk
        assert "Найкраща ціна" in msg_uk

        competitors_p2 = await PriceComparator.find_competitor_prices(p2)
        msg_en = PriceComparator.format_comparison_message(p2, competitors_p2, lang="en")
        assert "Price Comparison" in msg_en
        assert "Tip:" in msg_en
        assert "Colruyt" in msg_en
    finally:
        pass
