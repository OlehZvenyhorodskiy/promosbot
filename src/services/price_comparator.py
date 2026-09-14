"""Smart price comparison service across Belgian supermarkets."""

import re
from typing import Dict, Any, List, Optional
from src.core.constants import SUPERMARKETS
from src.db.repository import Repository
from src.scrapers.base import normalize_title

PACK_SIZE_PATTERN = re.compile(
    r"\b(?:\d+\s*[xX]\s*)?\d+(?:[.,]\d+)?\s*(?:kg|g|l|cl|ml|stuks|st|pcs|can|blik|fles|bouteille|pack)\b",
    re.IGNORECASE,
)


class PriceComparator:
    @staticmethod
    def extract_core_keywords(title: str) -> List[str]:
        """Extract searchable brand and product nouns from title, stripping sizes and promos."""
        # 1. Strip pack sizes
        cleaned = PACK_SIZE_PATTERN.sub(" ", title)
        # 2. Normalize and strip non-alphanumeric
        cleaned = re.sub(r"[^\w\s-]", " ", cleaned)
        tokens = [t.strip() for t in cleaned.split() if len(t.strip()) >= 3]
        # 3. Filter out generic stop words
        stop_words = {
            "gratis", "free", "korting", "promo", "action", "actie", "aanbieding",
            "met", "voor", "van", "vanaf", "pack", "maxi", "bio", "verse", "vers",
            "frais", "avec", "pour", "reductions", "deal", "super",
        }
        core_tokens = [t for t in tokens if t.lower() not in stop_words]
        return core_tokens[:3]

    @classmethod
    async def find_competitor_prices(
        cls, promo: Dict[str, Any], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for the same or equivalent product in other supermarkets."""
        current_store = promo.get("store_id")
        title = promo.get("title", "")
        keywords = cls.extract_core_keywords(title)
        if not keywords:
            return []

        # Query matches for core keywords to allow cross-store title variations
        seen_match_ids = set()
        raw_matches = []
        for kw in keywords:
            matches = await Repository.get_promos(search_query=kw, limit=30)
            for m in matches:
                if m["id"] not in seen_match_ids:
                    seen_match_ids.add(m["id"])
                    raw_matches.append(m)

        # Filter out current store and invalid prices
        competitors = []
        seen_stores = set()
        if current_store:
            seen_stores.add(current_store)

        for match in raw_matches:
            match_store = match.get("store_id")
            if match_store in seen_stores:
                continue

            price = match.get("promo_price") or match.get("original_price")
            if price is None or price <= 0:
                continue

            seen_stores.add(match_store)
            store_info = SUPERMARKETS.get(match_store, {"name": match_store.title(), "emoji": "🏪"})
            competitors.append({
                "store_id": match_store,
                "store_name": store_info.get("name", match_store.title()),
                "store_emoji": store_info.get("emoji", "🏪"),
                "title": match.get("title"),
                "promo_price": match.get("promo_price"),
                "original_price": match.get("original_price"),
                "discount_text": match.get("discount_text"),
                "loyalty_card": match.get("loyalty_card"),
                "deal_url": match.get("deal_url"),
            })
            if len(competitors) >= limit:
                break

        # Sort competitors by promo_price ascending
        competitors.sort(key=lambda x: x.get("promo_price") or 999999.0)
        return competitors

    @classmethod
    def format_comparison_message(
        cls, current_promo: Dict[str, Any], competitors: List[Dict[str, Any]], lang: str = "en"
    ) -> str:
        """Render a clean Telegram markdown message comparing prices across stores."""
        cur_store_id = current_promo.get("store_id", "")
        cur_info = SUPERMARKETS.get(cur_store_id, {"name": cur_store_id.title(), "emoji": "🏪"})
        cur_name = cur_info.get("name", cur_store_id.title())
        cur_emoji = cur_info.get("emoji", "🏪")
        cur_price = current_promo.get("promo_price") or current_promo.get("original_price") or 0.0

        headers = {
            "en": f"⚖️ <b>Price Comparison for:</b> <i>{current_promo.get('title')}</i>\n",
            "uk": f"⚖️ <b>Порівняння цін для:</b> <i>{current_promo.get('title')}</i>\n",
            "nl": f"⚖️ <b>Prijsvergelijking voor:</b> <i>{current_promo.get('title')}</i>\n",
            "fr": f"⚖️ <b>Comparatif de prix pour :</b> <i>{current_promo.get('title')}</i>\n",
        }

        lines = [headers.get(lang, headers["en"])]
        current_label = {
            "uk": "(поточний)",
            "nl": "(huidig)",
            "fr": "(actuel)",
            "en": "(current)",
        }.get(lang, "(current)")
        lines.append(f"• {cur_emoji} <b>{cur_name}</b> {current_label}: <b>€{cur_price:.2f}</b>")

        cheapest_store = cur_name
        cheapest_price = cur_price

        for comp in competitors:
            c_price = comp.get("promo_price") or comp.get("original_price") or 0.0
            c_emoji = comp.get("store_emoji", "🏪")
            c_name = comp.get("store_name", "")
            c_disc = comp.get("discount_text") or ""
            disc_str = f" ({c_disc})" if c_disc and c_disc != "PROMO" else ""
            lines.append(f"• {c_emoji} <b>{c_name}</b>: €{c_price:.2f}{disc_str}")

            if c_price < cheapest_price:
                cheapest_price = c_price
                cheapest_store = c_name

        lines.append("")
        if cheapest_store == cur_name:
            verdict = {
                "en": f"🏆 <b>Best deal!</b> {cur_name} currently has the lowest promo price.",
                "uk": f"🏆 <b>Найкраща ціна!</b> У {cur_name} зараз найдешевша пропозиція.",
                "nl": f"🏆 <b>Beste prijs!</b> {cur_name} heeft momenteel de scherpste actieprijs.",
                "fr": f"🏆 <b>Meilleure offre !</b> {cur_name} propose actuellement le tarif le plus bas.",
            }
        else:
            diff = cur_price - cheapest_price
            verdict = {
                "en": f"💡 <b>Tip:</b> {cheapest_store} is €{diff:.2f} cheaper right now!",
                "uk": f"💡 <b>Порада:</b> У {cheapest_store} цей товар дешевший на €{diff:.2f}!",
                "nl": f"💡 <b>Tip:</b> {cheapest_store} is nu €{diff:.2f} voordeliger!",
                "fr": f"💡 <b>Astuce :</b> {cheapest_store} est moins cher de €{diff:.2f} !",
            }
        lines.append(verdict.get(lang, verdict["en"]))
        return "\n".join(lines)
