from abc import ABC, abstractmethod
from typing import List
import re
import hashlib
from src.scrapers.models import PromoItem

CATEGORY_KEYWORDS = {
    "fruits_veg": [
        "appel", "peer", "banaan", "druiven", "aardbei", "citroen", "sinaasappel", "tomaat", "komkommer",
        "sla", "wortel", "ui", "aardappel", "paprika", "groenten", "fruit", "pomme", "poire", "banane",
        "fraise", "tomate", "concombre", "salade", "carotte", "oignon", "legumes", "pommes de terre"
    ],
    "dairy_cheese": [
        "kaas", "melk", "yoghurt", "boter", "room", "kwark", "eieren", "fromage", "lait", "yaourt",
        "beurre", "creme", "oeufs", "gouda", "brie", "camembert", "mozzarella", "parmezaan", "cheddar"
    ],
    "meat_fish": [
        "vlees", "kip", "rund", "varken", "gehakt", "biefstuk", "spek", "worst", "ham", "vis", "zalm",
        "tonijn", "kabeljauw", "garnalen", "viande", "poulet", "boeuf", "porc", "hache", "steak",
        "jambon", "poisson", "saumon", "thon", "cabillaud", "crevettes", "scampi"
    ],
    "bakery": [
        "brood", "pistolet", "stokbrood", "croissant", "koek", "cake", "taart", "pain", "baguette",
        "brioche", "biscotte", "toast", "ontbijt", "cereales", "muesli", "granola"
    ],
    "drinks": [
        "bier", "wijn", "champagne", "cava", "water", "frisdrank", "cola", "fanta", "sprite", "sap",
        "koffie", "thee", "biere", "vin", "eau", "soda", "jus", "cafe", "the", "duvel", "leffe", "stella",
        "jupiler", "cara"
    ],
    "snacks_sweets": [
        "chips", "noten", "chocolade", "koekjes", "snoep", "wafels", "ijs", "chocolat", "biscuits",
        "bonbons", "gaufres", "glace", "popcorn", "pringles", "milka", "cote d'or", "haribo"
    ],
    "household": [
        "wasmiddel", "wasverzachter", "afwasmiddel", "allesreiniger", "toiletpapier", "keukenrol",
        "vaatwastabletten", "schoonmaak", "lessive", "adoucissant", "vaisselle", "nettoyant",
        "papier toilette", "essuie-tout", "ariel", "dash", "dreft"
    ],
    "care_baby": [
        "shampoo", "douchegel", "zeep", "tandpasta", "deo", "deodorant", "luiers", "pampers",
        "babyvoeding", "gel douche", "savon", "dentifrice", "couches", "creme", "nivea", "dove"
    ],
    "bio_organic": [
        "bio", "biologisch", "organic", "organisch", "biologique", "fairtrade", "duurzaam"
    ],
}

def infer_category(title: str, description: str = "") -> str:
    text = f"{title} {description}".lower()
    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                return cat_id
    return "pantry"

class BaseScraper(ABC):
    def __init__(self, store_id: str, name: str):
        self.store_id = store_id
        self.name = name

    @staticmethod
    def stable_external_id(store_id: str, title: str, source_key: str = "") -> str:
        """Use a process-independent ID so a restart does not create fake promos."""
        normalized = " ".join((title or "").lower().split())
        raw = f"{store_id}:{source_key or normalized}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    @abstractmethod
    async def fetch_promos(self) -> List[PromoItem]:
        pass
