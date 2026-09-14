import pytest
from src.scrapers.base import normalize_title, generate_fingerprint
from src.scrapers.models import PromoItem

def test_normalize_title():
    # Packaging units should be stripped
    assert normalize_title("Coca-Cola Regular 1,5L") == "coca cola regular"
    assert normalize_title("Jupiler Pils 6x33cl") == "jupiler pils"
    assert normalize_title("Gouda Jonge Kaas 500g") == "gouda jonge kaas"
    assert normalize_title("Appels Jonagold (Bio) 1kg") == "appels jonagold"
    assert normalize_title("  Lay's   Chips Paprika  200 g  ") == "lay s chips paprika"

def test_generate_fingerprint_determinism():
    # Same product with minor variations in title casing or spacing produces the identical fingerprint
    fp1 = generate_fingerprint("colruyt", "Coca-Cola Regular 1.5L", 1.99, "2026-09-01", "2026-09-15")
    fp2 = generate_fingerprint("colruyt", "coca-cola regular 1,5L", 1.99, "2026-09-01", "2026-09-15")
    assert fp1 == fp2
    assert len(fp1) == 24

def test_generate_fingerprint_uniqueness():
    fp_colruyt = generate_fingerprint("colruyt", "Heineken 6x33cl", 5.99)
    fp_carrefour = generate_fingerprint("carrefour", "Heineken 6x33cl", 5.99)
    fp_diff_price = generate_fingerprint("colruyt", "Heineken 6x33cl", 4.99)

    assert fp_colruyt != fp_carrefour
    assert fp_colruyt != fp_diff_price

def test_promo_item_discount_calculation():
    item = PromoItem(
        store_id="aldi",
        title="Boter",
        original_price=2.00,
        promo_price=1.50,
    )
    assert item.calculate_discount_percentage() == 25.0

    no_discount_item = PromoItem(
        store_id="aldi",
        title="Boter",
        promo_price=1.50,
    )
    assert no_discount_item.calculate_discount_percentage() is None
