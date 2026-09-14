import pytest
import os
import uuid
from pathlib import Path
from src.core.config import settings
from src.core.constants import SUPERMARKETS
from src.db.database import init_db
from src.db.repository import Repository

@pytest.mark.asyncio
async def test_user_and_filters():
    test_db = f"data/test_{uuid.uuid4().hex[:8]}.db"
    settings.DB_PATH = test_db
    try:
        await init_db()

        # Create user
        user = await Repository.get_or_create_user(12345, "testuser", "Tester")
        assert user["user_id"] == 12345
        assert user["language"] == "en"

        # Check default store filters (all stores enabled)
        stores = await Repository.get_user_store_filters(12345)
        assert len(stores) == len(SUPERMARKETS)
        assert "colruyt" in stores
        assert "action" in stores
        assert "kruidvat" in stores

        # Toggle store
        new_state = await Repository.toggle_user_store_filter(12345, "colruyt")
        assert new_state is False
        stores_after = await Repository.get_user_store_filters(12345)
        assert "colruyt" not in stores_after

        # Save promo
        promo_data = {
            "store_id": "colruyt",
            "title": "Gouda Kaas 2+2",
            "description": "Belgian young gouda cheese slices",
            "original_price": 9.98,
            "promo_price": 4.99,
            "discount_text": "2+2 GRATIS",
            "category_id": "dairy_cheese",
            "image_url": "https://example.com/gouda.jpg",
            "deal_url": "https://colruyt.be/deals/1",
            "loyalty_card": "Xtra",
        }
        promo_id, is_new = await Repository.save_promo(promo_data)
        assert is_new is True

        promos = await Repository.get_promos(store_ids=["colruyt"])
        assert len(promos) == 1
        assert promos[0]["title"] == "Gouda Kaas 2+2"
        assert promos[0]["loyalty_card"] == "Xtra"

        # Toggle favorite
        fav_state = await Repository.toggle_favorite(12345, promo_id)
        assert fav_state is True
        favs = await Repository.get_user_favorites(12345)
        assert len(favs) == 1
        assert favs[0]["id"] == promo_id

        # Saving identical promo again should NOT be marked as new (fingerprint deduplication)
        promo_id_again, is_new_again = await Repository.save_promo(promo_data)
        assert promo_id_again == promo_id
        assert is_new_again is False

        # Bulk save deduplication
        bulk_data = [
            promo_data, # existing
            {
                "store_id": "aldi",
                "title": "Verse Melk 1L",
                "promo_price": 0.89,
                "category_id": "dairy_cheese",
            }, # new
        ]
        results = await Repository.save_promos_bulk(bulk_data)
        assert len(results) == 2
        assert results[0][1] is False # existing
        assert results[1][1] is True # new
    finally:
        try:
            if os.path.exists(test_db):
                os.remove(test_db)
        except Exception:
            pass
