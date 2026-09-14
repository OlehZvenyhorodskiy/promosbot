from typing import List, Set
import re

SYNONYM_DICTIONARY = {
    # Dairy / Cheese
    "молоко": ["melk", "lait", "milk", "lactel", "campina"],
    "milk": ["melk", "lait", "молоко"],
    "melk": ["melk", "lait", "milk", "молоко"],
    "lait": ["melk", "lait", "milk", "молоко"],
    "сир": ["kaas", "fromage", "cheese", "gouda", "brie", "camembert", "mozzarella", "cheddar", "parmezaan"],
    "cheese": ["kaas", "fromage", "сир", "gouda", "brie"],
    "kaas": ["kaas", "fromage", "cheese", "сир"],
    "fromage": ["kaas", "fromage", "cheese", "сир"],
    "масло": ["boter", "beurre", "butter"],
    "butter": ["boter", "beurre", "масло"],
    "boter": ["boter", "beurre", "butter", "масло"],
    "beurre": ["boter", "beurre", "butter", "масло"],
    "йогурт": ["yoghurt", "yaourt", "yogurt", "danone"],
    "yoghurt": ["yoghurt", "yaourt", "yogurt", "йогурт"],
    "yaourt": ["yoghurt", "yaourt", "yogurt", "йогурт"],
    "сметана": ["zure room", "crème fraîche", "sour cream"],
    "вершки": ["room", "crème", "cream"],

    # Meat / Fish
    "м'ясо": ["vlees", "viande", "meat", "kip", "rund", "varken", "porc", "boeuf", "poulet"],
    "мясо": ["vlees", "viande", "meat", "kip", "rund", "varken", "porc", "boeuf", "poulet"],
    "meat": ["vlees", "viande", "meat"],
    "vlees": ["vlees", "viande", "meat", "м'ясо"],
    "viande": ["vlees", "viande", "meat", "м'ясо"],
    "курка": ["kip", "poulet", "chicken"],
    "курча": ["kip", "poulet", "chicken"],
    "курятина": ["kip", "poulet", "chicken"],
    "chicken": ["kip", "poulet", "курка"],
    "kip": ["kip", "poulet", "chicken", "курка"],
    "poulet": ["kip", "poulet", "chicken", "курка"],
    "яловичина": ["rundsvlees", "rund", "boeuf", "beef"],
    "свинина": ["varkensvlees", "varken", "porc", "pork"],
    "ковбаса": ["worst", "saucisse", "sausage", "charcuterie"],
    "сосиски": ["worstjes", "saucisses", "knack"],
    "шинка": ["ham", "jambon"],
    "ham": ["ham", "jambon", "шинка"],
    "jambon": ["ham", "jambon", "шинка"],
    "риба": ["vis", "poisson", "fish", "zalm", "tonijn", "kabeljauw"],
    "fish": ["vis", "poisson", "риба"],
    "vis": ["vis", "poisson", "fish", "риба"],
    "poisson": ["vis", "poisson", "fish", "риба"],
    "лосось": ["zalm", "saumon", "salmon"],
    "сьомга": ["zalm", "saumon", "salmon"],
    "salmon": ["zalm", "saumon", "лосось"],
    "zalm": ["zalm", "saumon", "salmon", "лосось"],
    "saumon": ["zalm", "saumon", "salmon", "лосось"],
    "креветки": ["garnalen", "crevettes", "shrimps", "scampi"],

    # Bakery / Grains
    "хліб": ["brood", "pain", "bread"],
    "хлеб": ["brood", "pain", "bread"],
    "bread": ["brood", "pain", "хліб"],
    "brood": ["brood", "pain", "bread", "хліб"],
    "pain": ["brood", "pain", "bread", "хліб"],
    "круасан": ["croissant", "croissants"],
    "круасани": ["croissant", "croissants"],
    "croissant": ["croissant", "croissants", "круасан"],
    "булка": ["broodje", "pistolet", "petit pain"],
    "булочки": ["broodjes", "pistolets", "petits pains"],
    "печиво": ["koekjes", "biscuits", "cookies"],
    "cookies": ["koekjes", "biscuits", "печиво"],
    "вафлі": ["wafels", "gaufres", "waffles"],
    "макарони": ["pasta", "spaghetti", "penne", "macaroni", "pâtes"],
    "паста": ["pasta", "spaghetti", "penne", "pâtes"],
    "pasta": ["pasta", "spaghetti", "penne", "паста"],
    "рис": ["rijst", "riz", "rice"],
    "борошно": ["bloem", "farine", "flour"],

    # Fruits & Vegetables
    "яблука": ["appels", "appel", "pommes", "pomme", "apples", "apple"],
    "яблуко": ["appel", "pomme", "apple", "яблуко"],
    "apples": ["appels", "appel", "pommes", "яблука"],
    "appel": ["appel", "appels", "pomme", "pommes", "яблука"],
    "pomme": ["pomme", "pommes", "appel", "appels", "яблука"],
    "банани": ["bananen", "bananes", "bananas"],
    "банан": ["banaan", "banane", "banana"],
    "полуниця": ["aardbeien", "fraises", "strawberries"],
    "клубніка": ["aardbeien", "fraises", "strawberries"],
    "картопля": ["aardappelen", "pommes de terre", "potatoes", "frietjes"],
    "помідори": ["tomaten", "tomates", "tomatoes"],
    "томати": ["tomaten", "tomates", "tomatoes"],
    "огірки": ["komkommers", "concombres", "cucumbers"],
    "цибуля": ["uien", "oignons", "onions"],
    "морква": ["wortelen", "carottes", "carrots"],
    "салат": ["sla", "salade", "lettuce"],

    # Drinks / Alcohol
    "пиво": ["bier", "biere", "beer", "jupiler", "stella", "leffe", "duvel", "cara", "carlsberg"],
    "beer": ["bier", "biere", "пиво", "jupiler", "stella"],
    "bier": ["bier", "biere", "beer", "пиво"],
    "biere": ["bier", "biere", "beer", "пиво"],
    "вино": ["wijn", "vin", "wine"],
    "wine": ["wijn", "vin", "вино"],
    "wijn": ["wijn", "vin", "wine", "вино"],
    "vin": ["wijn", "vin", "wine", "вино"],
    "вода": ["water", "eau"],
    "water": ["water", "eau", "вода", "spa", "evian"],
    "сік": ["sap", "jus", "juice"],
    "кава": ["koffie", "cafe", "coffee"],
    "coffee": ["koffie", "cafe", "кава"],
    "koffie": ["koffie", "cafe", "coffee", "кава"],
    "чай": ["thee", "the", "tea"],

    # Sweets & Snacks
    "шоколад": ["chocolade", "chocolat", "chocolate", "cote d'or", "milka", "kinder"],
    "chocolate": ["chocolade", "chocolat", "шоколад"],
    "чіпси": ["chips", "crisps", "lay's", "doritos", "pringles"],
    "чипси": ["chips", "crisps", "lay's", "doritos", "pringles"],
    "chips": ["chips", "crisps", "чіпси"],
    "цукерки": ["snoep", "bonbons", "candy"],
    "морозиво": ["ijs", "glace", "ice cream"],

    # Pantry & Household
    "олія": ["olie", "huile", "oil"],
    "масло олія": ["olie", "huile", "oil"],
    "oil": ["olie", "huile", "олія"],
    "olie": ["olie", "huile", "oil", "олія"],
    "huile": ["olie", "huile", "oil", "олія"],
    "цукор": ["suiker", "sucre", "sugar"],
    "сіль": ["zout", "sel", "salt"],
    "яйця": ["eieren", "oeufs", "eggs"],
    "eggs": ["eieren", "oeufs", "яйця"],
    "eieren": ["eieren", "oeufs", "eggs", "яйця"],
    "oeufs": ["eieren", "oeufs", "eggs", "яйця"],
    "туалетний папір": ["toiletpapier", "papier toilette", "toilet paper"],
    "мило": ["zeep", "savon", "soap"],
    "шампунь": ["shampoo", "shampooing"],
    "порошок": ["wasmiddel", "lessive", "detergent", "ariel", "dash"],
}

def expand_search_terms(query: str) -> List[str]:
    clean = query.strip().lower()
    terms: Set[str] = {clean}

    # Direct match in dictionary
    if clean in SYNONYM_DICTIONARY:
        terms.update(SYNONYM_DICTIONARY[clean])

    # Word-by-word expansion for multi-word queries
    words = clean.split()
    for w in words:
        if w in SYNONYM_DICTIONARY:
            terms.update(SYNONYM_DICTIONARY[w])

    return list(terms)
