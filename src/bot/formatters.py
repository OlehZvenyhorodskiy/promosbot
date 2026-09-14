from typing import Dict, Any, Optional
from src.core.constants import SUPERMARKETS, CATEGORIES
from src.i18n.translations import get_text, get_category_name, localize_discount_text

def format_price(val: Optional[float]) -> str:
    if val is None:
        return ""
    return f"€{val:.2f}"

def format_promo_card(promo: Dict[str, Any], lang: str = "en", is_fav: bool = False) -> str:
    store_id = promo.get("store_id", "generic")
    store_info = SUPERMARKETS.get(store_id, {"name": store_id.title(), "emoji": "🏪"})
    store_name = store_info.get("name", store_id.title())
    store_emoji = store_info.get("emoji", "🏪")

    category_id = promo.get("category_id", "pantry")
    cat_emoji = CATEGORIES.get(category_id, {}).get("emoji", "🏷️")
    cat_name = get_category_name(category_id, lang)

    title = promo.get("title", "Promotion")
    description = promo.get("description") or ""
    orig_price = promo.get("original_price")
    promo_price = promo.get("promo_price")
    discount_text = promo.get("discount_text") or ""
    unit_info = promo.get("unit_info") or ""
    valid_until = promo.get("valid_until") or ""
    image_url = promo.get("image_url")

    badge = get_text("discount_badge", lang)
    lines = []

    # Instant zero-width photo preview link (renders image instantly without slow edit_media)
    if image_url and image_url.startswith("http"):
        lines.append(f'<a href="{image_url}">&#8205;</a>')

    lines.append(f"{store_emoji} <b>{store_name}</b> • {cat_emoji} <i>{cat_name}</i>")
    lines.append("")
    lines.append(f"🏷️ <b>{title}</b>")

    if description:
        localized_desc = localize_discount_text(description, lang)
        clean_desc = localized_desc[:180] + ("..." if len(localized_desc) > 180 else "")
        lines.append(f"<i>{clean_desc}</i>")

    lines.append("")

    price_parts = []
    if orig_price is not None and promo_price is not None and orig_price > promo_price:
        price_parts.append(f"<s>{format_price(orig_price)}</s> ➔ <b>{format_price(promo_price)}</b>")
    elif promo_price is not None:
        price_parts.append(f"<b>{format_price(promo_price)}</b>")
    elif orig_price is not None:
        price_parts.append(f"<b>{format_price(orig_price)}</b>")

    if unit_info:
        price_parts.append(f"({unit_info})")

    if price_parts:
        lines.append(f"💰 {' '.join(price_parts)}")

    # Format and translate discount badge intelligently to eliminate vague 'Акція PROMO'
    clean_discount = localize_discount_text(discount_text, lang)
    is_generic_promo = clean_discount.upper() in ["", "PROMO", "ACTIE", "PROMOTIE", "DISCOUNT"]

    if orig_price is not None and promo_price is not None and orig_price > promo_price:
        saving = orig_price - promo_price
        percent = int(round((saving / orig_price) * 100))
        if not is_generic_promo:
            lines.append(f"🔥 <b>{clean_discount} (-{percent}%)</b>")
        else:
            if lang == "uk":
                lines.append(f"🔥 <b>Знижка -{percent}% (Економія €{saving:.2f})</b>")
            elif lang == "nl":
                lines.append(f"🔥 <b>-{percent}% Korting (Bespaar €{saving:.2f})</b>")
            elif lang == "fr":
                lines.append(f"🔥 <b>-{percent}% Réduction (Économisez €{saving:.2f})</b>")
            else:
                lines.append(f"🔥 <b>-{percent}% Off (Save €{saving:.2f})</b>")
    elif not is_generic_promo:
        lines.append(f"🔥 <b>{clean_discount}</b>")
    elif is_generic_promo and promo_price is not None:
        if lang == "uk":
            lines.append("🔥 <b>Акційна пропозиція</b>")
        elif lang == "nl":
            lines.append("🔥 <b>Promotieaanbieding</b>")
        elif lang == "fr":
            lines.append("🔥 <b>Offre promotionnelle</b>")
        else:
                lines.append("🔥 <b>Promo Price</b>")

    loyalty_card = promo.get("loyalty_card")
    if loyalty_card:
        card_label = {
            "uk": f"💳 <i>З карткою {loyalty_card}</i>",
            "nl": f"💳 <i>Met {loyalty_card}</i>",
            "fr": f"💳 <i>Avec la carte {loyalty_card}</i>",
            "en": f"💳 <i>With {loyalty_card}</i>",
        }.get(lang, f"💳 <i>With {loyalty_card}</i>")
        lines.append(card_label)

    if valid_until:
        until_label = get_text("valid_until", lang)
        lines.append(f"📅 {until_label}: <code>{valid_until}</code>")

    if is_fav:
        lines.append("\n⭐ <i>Saved in your bookmarks</i>")

    return "\n".join(lines)

def format_digest_header(count: int, lang: str = "en") -> str:
    texts = {
        "en": f"🌅 <b>Good morning! Here is your Belgian Promo Digest</b> ({count} deals today):",
        "uk": f"🌅 <b>Доброго ранку! Ваш щоденний дайджест знижок Бельгії</b> ({count} акцій):",
        "nl": f"🌅 <b>Goedemorgen! Jouw Belgische Promo Overzicht</b> ({count} aanbiedingen):",
        "fr": f"🌅 <b>Bonjour ! Voici votre récapitulatif promo belge</b> ({count} offres du jour) :",
    }
    return texts.get(lang, texts["en"])
