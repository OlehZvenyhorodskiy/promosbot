import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions
from aiogram.filters import Command
from src.db.repository import Repository
from src.i18n.translations import get_text
from src.core.constants import SUPERMARKETS
from src.bot.formatters import format_promo_card
from src.bot.keyboards import (
    get_promo_card_keyboard,
    get_store_drilldown_keyboard,
    get_store_detail_keyboard,
)
from src.bot.message_manager import (
    delete_incoming_message,
    send_top_level_message,
    remember_bot_message,
    clear_last_bot_messages,
    safe_edit_text,
    safe_edit_reply_markup,
)

logger = logging.getLogger(__name__)
router = Router()

PROMOS_BUTTON_TEXTS = ["🔍 Browse Deals", "🔍 Переглянути акції", "🔍 Bekijk Promo's", "🔍 Découvrir les Promos"]
SEARCH_BUTTON_TEXTS = ["🔎 Search Product", "🔎 Пошук товару", "🔎 Zoek Product", "🔎 Rechercher un Produit"]
FAVS_BUTTON_TEXTS = ["⭐ Saved Deals", "⭐ Збережені знижки", "⭐ Bewaarde Promo's", "⭐ Promos Enregistrées"]
FOLDERS_BUTTON_TEXTS = ["📰 Folders & Leaflets", "📰 Буклети та брошури", "📰 Folders & Folders", "📰 Dépliants & Catalogues"]
STORES_BUTTON_TEXTS = ["🏪 Supermarkets", "🏪 Супермаркети", "🏪 Supermarkten", "🏪 Supermarchés"]
CATEGORIES_BUTTON_TEXTS = ["🏷️ Categories", "🏷️ Категорії", "🏷️ Categorieën", "🏷️ Catégories"]
SETTINGS_BUTTON_TEXTS = ["⚙️ Settings", "⚙️ Налаштування", "⚙️ Instellingen", "⚙️ Paramètres"]
TEST_BUTTON_TEXTS = ["🧪 Test Promo Card", "🧪 Тестова картка", "🧪 Test Promokaart", "🧪 Carte Promo Test"]
HELP_BUTTON_TEXTS = ["ℹ️ Help", "ℹ️ Допомога", "ℹ️ Hulp", "ℹ️ Aide"]

ALL_MENU_BUTTONS = (
    PROMOS_BUTTON_TEXTS
    + SEARCH_BUTTON_TEXTS
    + FAVS_BUTTON_TEXTS
    + FOLDERS_BUTTON_TEXTS
    + STORES_BUTTON_TEXTS
    + CATEGORIES_BUTTON_TEXTS
    + SETTINGS_BUTTON_TEXTS
    + TEST_BUTTON_TEXTS
    + HELP_BUTTON_TEXTS
)
async def send_or_edit_promo_message(
    target: Message | CallbackQuery,
    promo: dict,
    current_index: int,
    total_count: int,
    lang: str,
    nav_code: str,
    store_id: str = None,
):
    user_id = target.from_user.id
    promo_id = promo["id"]
    is_fav = await Repository.is_favorite(user_id, promo_id)
    store_id = store_id or promo.get("store_id")
    deal_url = promo.get("deal_url")
    image_url = promo.get("image_url")
    card_promo = promo

    reply_markup = get_promo_card_keyboard(
        promo_id=promo_id,
        deal_url=deal_url,
        is_fav=is_fav,
        current_index=current_index,
        total_count=total_count,
        lang=lang,
        nav_code=nav_code,
        store_id=store_id,
        image_url=image_url,
    )
    if image_url and image_url.startswith("http"):
        preview_opts = LinkPreviewOptions(
            is_disabled=False,
            prefer_large_media=True,
            show_above_text=True,
            url=image_url,
        )
    else:
        preview_opts = LinkPreviewOptions(is_disabled=True)
    if isinstance(target, CallbackQuery):
        await safe_edit_text(
            target,
            format_promo_card(card_promo, lang=lang, is_fav=is_fav),
            reply_markup=reply_markup,
            parse_mode="HTML",
            link_preview_options=preview_opts,
        )
    else:
        await delete_incoming_message(target)
        await clear_last_bot_messages(target.bot, target.chat.id)
        sent = await target.answer(
            format_promo_card(card_promo, lang=lang, is_fav=is_fav),
            reply_markup=reply_markup,
            parse_mode="HTML",
            link_preview_options=preview_opts,
        )
        remember_bot_message(sent)

# --- 1. Browse by Supermarket Drilldown ---
@router.message(Command("promos"))
@router.message(F.text.in_(PROMOS_BUTTON_TEXTS))
async def handle_browse_promos(message: Message):
    user_id = message.from_user.id
    user = await Repository.get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")

    counts = await Repository.get_promo_counts_by_store()
    total = sum(counts.values())

    await delete_incoming_message(message)
    await send_top_level_message(
        message,
        get_text("store_drilldown_title", lang),
        reply_markup=get_store_drilldown_keyboard(counts, total, lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "nav:browse_stores")
async def handle_nav_browse_stores(callback: CallbackQuery):
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"
    counts = await Repository.get_promo_counts_by_store()
    total = sum(counts.values())

    await callback.answer()
    await safe_edit_text(
        callback,
        get_text("store_drilldown_title", lang),
        reply_markup=get_store_drilldown_keyboard(counts, total, lang),
        parse_mode="HTML",
    )

# --- 2. Store Overview ---
@router.callback_query(F.data.startswith("st:"))
async def handle_store_view(callback: CallbackQuery):
    store_id = callback.data.split(":")[1]
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"

    s_info = SUPERMARKETS.get(store_id, {"name": store_id.title(), "emoji": "🏪"})
    store_name = s_info.get("name", store_id)
    store_emoji = s_info.get("emoji", "🏪")
    folder_url = s_info.get("folder_url")

    counts = await Repository.get_promo_counts_by_store()
    store_promo_count = counts.get(store_id, 0)
    cat_counts = await Repository.get_promo_counts_by_category(store_id)

    title_text = get_text(
        "store_overview_title",
        lang,
        emoji=store_emoji,
        name=store_name,
        count=store_promo_count,
    )

    markup = get_store_detail_keyboard(
        store_id=store_id,
        promo_count=store_promo_count,
        folder_url=folder_url,
        cat_counts=cat_counts,
        lang=lang,
    )

    await callback.answer()
    await safe_edit_text(callback, title_text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data.startswith("new:"))
async def handle_new_store_promos(callback: CallbackQuery):
    _, batch_id_raw, store_id = callback.data.split(":", 2)
    batch_id = int(batch_id_raw)
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"
    promos = await Repository.get_alert_batch_promos(batch_id, store_id)
    await callback.answer()
    if not promos:
        await safe_edit_text(callback, get_text("no_promos_found", lang), parse_mode="HTML")
        return
    await send_or_edit_promo_message(
        target=callback,
        promo=promos[0],
        current_index=0,
        total_count=len(promos),
        lang=lang,
        nav_code=f"new:{batch_id}:{store_id}",
        store_id=store_id,
    )

# --- 3. Paging through deals (Compact callback format) ---
@router.callback_query(F.data.startswith("p:"))
async def handle_promo_paging(callback: CallbackQuery):
    parts = callback.data.split(":")
    mode = parts[1]

    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"

    if mode == "all":
        idx = int(parts[2])
        promos = await Repository.get_promos(limit=1000)
        nav_code = "all"
        store_id = None
    elif mode == "s":
        store_id = parts[2]
        idx = int(parts[3])
        promos = await Repository.get_promos(store_ids=[store_id], limit=1000)
        nav_code = f"s:{store_id}"
    elif mode == "sc":
        store_id = parts[2]
        cat_id = parts[3]
        idx = int(parts[4])
        promos = await Repository.get_promos(store_ids=[store_id], category_ids=[cat_id], limit=500)
        nav_code = f"sc:{store_id}:{cat_id}"
    elif mode == "srch":
        query = parts[2]
        idx = int(parts[3])
        promos = await Repository.get_promos(search_query=query, limit=100)
        nav_code = f"srch:{query}"
        store_id = None
    elif mode == "fav":
        idx = int(parts[2])
        promos = await Repository.get_user_favorites(callback.from_user.id)
        nav_code = "fav"
        store_id = None
    elif mode == "new":
        batch_id = int(parts[2])
        store_id = parts[3]
        idx = int(parts[4])
        promos = await Repository.get_alert_batch_promos(batch_id, store_id)
        nav_code = f"new:{batch_id}:{store_id}"
    else:
        await callback.answer()
        return

    if not promos:
        await callback.answer(get_text("no_promos_found", lang))
        return

    safe_idx = max(0, min(idx, len(promos) - 1))
    await callback.answer()
    await send_or_edit_promo_message(
        target=callback,
        promo=promos[safe_idx],
        current_index=safe_idx,
        total_count=len(promos),
        lang=lang,
        nav_code=nav_code,
        store_id=store_id,
    )

# --- 4. Favorite Toggle ---
@router.callback_query(F.data.startswith("fav:"))
async def handle_fav_toggle(callback: CallbackQuery):
    promo_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    user = await Repository.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    is_now_fav = await Repository.toggle_favorite(user_id, promo_id)
    alert_text = get_text("fav_saved" if is_now_fav else "fav_removed", lang)
    await callback.answer(alert_text)

    # In-place refresh of button label
    promo = await Repository.get_promo_by_id(promo_id)
    if promo:
        deal_url = promo.get("deal_url")
        reply_markup = get_promo_card_keyboard(
            promo_id=promo_id,
            deal_url=deal_url,
            is_fav=is_now_fav,
            current_index=0,
            total_count=1,
            lang=lang,
            nav_code="all",
        )
        await safe_edit_reply_markup(callback, reply_markup=reply_markup)

# --- 5. Favorites View ---
@router.message(Command("favorites"))
@router.message(F.text.in_(FAVS_BUTTON_TEXTS))
async def handle_favorites(message: Message):
    user_id = message.from_user.id
    user = await Repository.get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")
    favs = await Repository.get_user_favorites(user_id)

    await delete_incoming_message(message)

    if not favs:
        await send_top_level_message(message, get_text("fav_empty", lang), parse_mode="HTML")
        return

    await send_or_edit_promo_message(
        target=message,
        promo=favs[0],
        current_index=0,
        total_count=len(favs),
        lang=lang,
        nav_code="fav",
    )

@router.callback_query(F.data == "nav:favs")
async def handle_nav_favs(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await Repository.get_user(user_id)
    lang = user.get("language", "en") if user else "en"
    favs = await Repository.get_user_favorites(user_id)

    await callback.answer()
    if not favs:
        await safe_edit_text(callback, get_text("fav_empty", lang), parse_mode="HTML")
        return

    await send_or_edit_promo_message(
        target=callback,
        promo=favs[0],
        current_index=0,
        total_count=len(favs),
        lang=lang,
        nav_code="fav",
    )

# --- 6. Search Prompt ---
@router.message(Command("search"))
@router.message(F.text.in_(SEARCH_BUTTON_TEXTS))
async def handle_search_prompt(message: Message):
    user = await Repository.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")
    await delete_incoming_message(message)
    await send_top_level_message(message, get_text("search_prompt", lang), parse_mode="HTML")

# --- 7. Multilingual Text Search ---
@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_search(message: Message):
    query = message.text.strip()
    if query in ALL_MENU_BUTTONS:
        return

    user_id = message.from_user.id
    user = await Repository.get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")

    promos = await Repository.get_promos(search_query=query, limit=50)

    await delete_incoming_message(message)

    if not promos:
        await send_top_level_message(
            message,
            f"{get_text('no_promos_found', lang)}\n\n💡 <i>Try searching 'молоко', 'сир', 'пиво', 'kaas', or 'chips'.</i>",
            parse_mode="HTML",
        )
        return

    await send_or_edit_promo_message(
        target=message,
        promo=promos[0],
        current_index=0,
        total_count=len(promos),
        lang=lang,
        nav_code=f"srch:{query[:10]}",
    )
