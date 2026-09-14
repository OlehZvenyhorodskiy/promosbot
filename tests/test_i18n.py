import pytest
from src.core.constants import SUPPORTED_LANGUAGES, CATEGORIES
from src.i18n.translations import TRANSLATIONS, get_text, get_category_name

def test_language_support():
    assert set(SUPPORTED_LANGUAGES.keys()) == {"en", "uk", "nl", "fr"}
    assert "ru" not in SUPPORTED_LANGUAGES

def test_translation_keys_consistency():
    en_keys = set(TRANSLATIONS["en"].keys())
    for lang in ["uk", "nl", "fr"]:
        lang_keys = set(TRANSLATIONS[lang].keys())
        diff = en_keys - lang_keys
        assert not diff, f"Language {lang} is missing keys: {diff}"

def test_get_text():
    assert "Belgium Promo's" in get_text("welcome_title", "en")
    assert "Ласкаво просимо" in get_text("welcome_title", "uk")
    assert "Welkom" in get_text("welcome_title", "nl")
    assert "Bienvenue" in get_text("welcome_title", "fr")

def test_categories_localized():
    for cat_id in CATEGORIES.keys():
        name_en = get_category_name(cat_id, "en")
        name_uk = get_category_name(cat_id, "uk")
        name_nl = get_category_name(cat_id, "nl")
        name_fr = get_category_name(cat_id, "fr")
        assert name_en and name_uk and name_nl and name_fr
