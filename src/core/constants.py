from typing import Dict, Any, List

SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
    "en": {"code": "en", "name": "English", "flag": "🇬🇧"},
    "uk": {"code": "uk", "name": "Українська", "flag": "🇺🇦"},
    "nl": {"code": "nl", "name": "Nederlands", "flag": "🇳🇱"},
    "fr": {"code": "fr", "name": "Français", "flag": "🇫🇷"},
}

DEFAULT_LANGUAGE = "en"

# Top 10 Belgian Supermarkets with official store URLs and digital folders
SUPERMARKETS: Dict[str, Dict[str, Any]] = {
    "colruyt": {
        "id": "colruyt",
        "name": "Colruyt",
        "emoji": "🔴",
        "url": "https://www.colruyt.be/nl/acties",
        "folder_url": "https://www.colruyt.be/nl/folders",
        "color": "#E30613",
    },
    "carrefour": {
        "id": "carrefour",
        "name": "Carrefour",
        "emoji": "🔵",
        "url": "https://www.carrefour.be/nl/promoties",
        "folder_url": "https://hyper.carrefour.be/nl/folders",
        "color": "#004E98",
    },
    "delhaize": {
        "id": "delhaize",
        "name": "Delhaize",
        "emoji": "🦁",
        "url": "https://www.delhaize.be/Promolandingpage",
        "folder_url": "https://www.delhaize.be/nl-be/folders",
        "color": "#C41230",
    },
    "aldi": {
        "id": "aldi",
        "name": "Aldi",
        "emoji": "🔷",
        "url": "https://www.aldi.be/nl/aanbiedingen.html",
        "folder_url": "https://www.aldi.be/nl/folders.html",
        "color": "#00A8E1",
    },
    "lidl": {
        "id": "lidl",
        "name": "Lidl",
        "emoji": "🟡",
        "url": "https://www.lidl.be/",
        "folder_url": "https://www.lidl.be/nl/folders",
        "color": "#0050AA",
    },
    "albert_heijn": {
        "id": "albert_heijn",
        "name": "Albert Heijn",
        "emoji": "🩵",
        "url": "https://www.ah.be/bonus",
        "folder_url": "https://www.ah.be/bonus/folder",
        "color": "#00A0E2",
    },
    "jumbo": {
        "id": "jumbo",
        "name": "Jumbo",
        "emoji": "🟡",
        "url": "https://www.jumbo.com/nl-be/aanbiedingen",
        "folder_url": "https://www.jumbo.com/nl-be/folders",
        "color": "#FFC600",
    },
    "spar": {
        "id": "spar",
        "name": "Spar",
        "emoji": "🌲",
        "url": "https://www.mijnspar.be/promoties",
        "folder_url": "https://www.mijnspar.be/promoties",
        "color": "#007A3D",
    },
    "cora": {
        "id": "cora",
        "name": "Cora",
        "emoji": "🟣",
        "url": "https://www.cora.be/fr/promotions",
        "folder_url": "https://www.cora.be/fr/catalogues",
        "color": "#7B1FA2",
    },
    "intermarche": {
        "id": "intermarche",
        "name": "Intermarché",
        "emoji": "🎯",
        "url": "https://www.intermarche.be/produits/",
        "folder_url": "https://www.intermarche.be/nl/folders/",
        "color": "#E5001A",
    },
}

CATEGORIES: Dict[str, Dict[str, Any]] = {
    "fruits_veg": {
        "id": "fruits_veg",
        "emoji": "🍏",
        "names": {
            "en": "Fruits & Vegetables",
            "uk": "Фрукти та овочі",
            "nl": "Groenten & Fruit",
            "fr": "Fruits & Légumes",
        },
    },
    "dairy_cheese": {
        "id": "dairy_cheese",
        "emoji": "🧀",
        "names": {
            "en": "Dairy & Cheese",
            "uk": "Молочні продукти та сири",
            "nl": "Zuivel & Kaas",
            "fr": "Produits laitiers & Fromage",
        },
    },
    "meat_fish": {
        "id": "meat_fish",
        "emoji": "🥩",
        "names": {
            "en": "Meat & Fish",
            "uk": "М'ясо та риба",
            "nl": "Vlees & Vis",
            "fr": "Viande & Poisson",
        },
    },
    "bakery": {
        "id": "bakery",
        "emoji": "🥖",
        "names": {
            "en": "Bakery & Breakfast",
            "uk": "Випічка та сніданки",
            "nl": "Bakkerij & Ontbijt",
            "fr": "Boulangerie & Petit-déj",
        },
    },
    "drinks": {
        "id": "drinks",
        "emoji": "🍷",
        "names": {
            "en": "Drinks & Beverages",
            "uk": "Напої",
            "nl": "Dranken",
            "fr": "Boissons",
        },
    },
    "snacks_sweets": {
        "id": "snacks_sweets",
        "emoji": "🍫",
        "names": {
            "en": "Snacks & Sweets",
            "uk": "Снеки та солодощі",
            "nl": "Snacks & Zoetigheden",
            "fr": "Snacks & Douceurs",
        },
    },
    "pantry": {
        "id": "pantry",
        "emoji": "🍝",
        "names": {
            "en": "Pantry & Meals",
            "uk": "Бакалія та готова їжа",
            "nl": "Voorraadkast & Maaltijden",
            "fr": "Épicerie & Plats",
        },
    },
    "household": {
        "id": "household",
        "emoji": "🧼",
        "names": {
            "en": "Household & Cleaning",
            "uk": "Побутова хімія",
            "nl": "Huishouden & Schoonmaak",
            "fr": "Entretien & Maison",
        },
    },
    "care_baby": {
        "id": "care_baby",
        "emoji": "👶",
        "names": {
            "en": "Care & Baby",
            "uk": "Догляд та малюки",
            "nl": "Verzorging & Baby",
            "fr": "Soins & Bébé",
        },
    },
    "bio_organic": {
        "id": "bio_organic",
        "emoji": "🌿",
        "names": {
            "en": "Bio & Organic",
            "uk": "Біо та Органіка",
            "nl": "Bio & Organisch",
            "fr": "Bio & Écologique",
        },
    },
}

NOTIFICATION_MODES = ["instant", "digest", "off"]

# Official Telegram animated stickers (available to all bots via Telegram CDN / file IDs)
STICKERS = {
    "welcome": "CAACAgIAAxkBAAIBJmX8yQ9T2o0bV9S_1F8lX9s8H9AAAgEAA8ZgGQABm4o9n7x9Hh4E", # Animated shopping duck / celebration
    "discounts": "CAACAgIAAxkBAAIBKWX8yRv7AAG4bM8h3b_99n4o4r3XAAIBAAPGYBkAAeA9aL7d8XseHgQ",
    "saved": "CAACAgIAAxkBAAIBLGX8yTF4wB81y9K34g1_4b8q2p0NAAIFAAPGYBkAAfO-bW-uG9E9HgQ",
}
