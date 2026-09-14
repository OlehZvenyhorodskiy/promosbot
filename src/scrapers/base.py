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

def normalize_title(title: str) -> str:
    if not title:
        return ""
    text = title.lower()
    # Remove content in parentheses e.g. (bio), (actie)
    text = re.sub(r"\(.*?\)", " ", text)
    # Remove packaging / unit indicators like 1L, 500g, 2x75cl, 6x33cl
    text = re.sub(
        r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|mg|l|cl|ml|stuks|st|pcs|pack|x\d+(?:[.,]\d+)?\s*(?:cl|ml|l|g)?)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Remove punctuation
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())

def generate_fingerprint(
    store_id: str,
    title: str,
    promo_price: Optional[float] = None,
    valid_from: Optional[str] = None,
    valid_until: Optional[str] = None,
) -> str:
    norm_title = normalize_title(title)
    price_str = f"{promo_price:.2f}" if promo_price is not None else "none"
    vf_str = (valid_from or "").strip() or "none"
    vu_str = (valid_until or "").strip() or "none"
    key = f"{store_id.lower().strip()}|{norm_title}|{price_str}|{vf_str}|{vu_str}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]

import ssl
import certifi
from typing import Optional
from src.utils.rate_limiter import PerDomainRateLimiter
from src.utils.retry import async_retry

default_rate_limiter = PerDomainRateLimiter(default_rps=2.0)

def get_ssl_context(verify: bool = True) -> ssl.SSLContext:
    """Returns a secure SSL context using certifi CA bundle, or unverified context if explicitly requested."""
    if verify:
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

class BaseScraper(ABC):
    def __init__(self, store_id: str, name: str, rate_limiter: Optional[PerDomainRateLimiter] = None):
        self.store_id = store_id
        self.name = name
        self.rate_limiter = rate_limiter or default_rate_limiter

    @staticmethod
    def stable_external_id(store_id: str, title: str, source_key: str = "") -> str:
        """Use a process-independent ID so a restart does not create fake promos."""
        if source_key:
            raw = f"{store_id}:{source_key}"
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
        return generate_fingerprint(store_id, title)

    @abstractmethod
    async def fetch_promos(self) -> List[PromoItem]:
        pass

