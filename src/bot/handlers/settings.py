from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from src.db.repository import Repository
from src.i18n.translations import get_text
from src.bot.keyboards import (
    get_settings_keyboard,
    get_stores_keyboard,
    get_categories_keyboard,
    get_notification_keyboard,
    get_language_keyboard,
)
from src.bot.message_manager import (
    delete_incoming_message,
    send_top_level_message,
    safe_edit_text,
    safe_edit_reply_markup,
)

router = Router()

SETTINGS_BUTTON_TEXTS = ["⚙️ Settings", "⚙️ Налаштування", "⚙️ Instellingen", "⚙️ Paramètres"]
STORES_BUTTON_TEXTS = ["🏪 Supermarkets", "🏪 Супермаркети", "🏪 Supermarkten", "🏪 Supermarchés"]
CATEGORIES_BUTTON_TEXTS = ["🏷️ Categories", "🏷️ Категорії", "🏷️ Categorieën", "🏷️ Catégories"]

@router.message(Command("settings"))
@router.message(F.text.in_(SETTINGS_BUTTON_TEXTS))
async def handle_settings_command(message: Message):
    user = await Repository.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")
    await delete_incoming_message(message)
    await send_top_level_message(
        message,
        get_text("settings_title", lang),
        reply_markup=get_settings_keyboard(lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "nav:settings")
async def handle_nav_settings(callback: CallbackQuery):
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"
    await callback.answer()
    await safe_edit_text(
        callback,
        get_text("settings_title", lang),
        reply_markup=get_settings_keyboard(lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "settings:lang")
async def handle_settings_lang(callback: CallbackQuery):
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"
    await callback.answer()
    await safe_edit_text(
        callback,
        get_text("choose_language", lang),
        reply_markup=get_language_keyboard(),
        parse_mode="HTML",
    )

# --- Store Filters ---
@router.message(Command("stores"))
@router.message(F.text.in_(STORES_BUTTON_TEXTS))
async def handle_stores_command(message: Message):
    user = await Repository.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")
    stores = await Repository.get_user_store_filters(message.from_user.id)
    await delete_incoming_message(message)
    await send_top_level_message(
        message,
        get_text("stores_title", lang),
        reply_markup=get_stores_keyboard(stores, lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "nav:stores")
async def handle_nav_stores(callback: CallbackQuery):
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"
    stores = await Repository.get_user_store_filters(callback.from_user.id)
    await callback.answer()
    await safe_edit_text(
        callback,
        get_text("stores_title", lang),
        reply_markup=get_stores_keyboard(stores, lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("toggle_store:"))
async def handle_toggle_store(callback: CallbackQuery):
    store_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    user = await Repository.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    await Repository.toggle_user_store_filter(user_id, store_id)
    stores = await Repository.get_user_store_filters(user_id)
    await callback.answer()
    await safe_edit_reply_markup(callback, reply_markup=get_stores_keyboard(stores, lang))

@router.callback_query(F.data.startswith("stores_all:"))
async def handle_stores_all(callback: CallbackQuery):
    enable_all = callback.data.split(":")[1] == "1"
    user_id = callback.from_user.id
    user = await Repository.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    await Repository.set_all_user_stores(user_id, enable_all)
    stores = await Repository.get_user_store_filters(user_id)
    await callback.answer()
    await safe_edit_reply_markup(callback, reply_markup=get_stores_keyboard(stores, lang))

# --- Category Filters ---
@router.message(Command("categories"))
@router.message(F.text.in_(CATEGORIES_BUTTON_TEXTS))
async def handle_categories_command(message: Message):
    user = await Repository.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")
    cats = await Repository.get_user_category_filters(message.from_user.id)
    await delete_incoming_message(message)
    await send_top_level_message(
        message,
        get_text("categories_title", lang),
        reply_markup=get_categories_keyboard(cats, lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "nav:categories")
async def handle_nav_categories(callback: CallbackQuery):
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"
    cats = await Repository.get_user_category_filters(callback.from_user.id)
    await callback.answer()
    await safe_edit_text(
        callback,
        get_text("categories_title", lang),
        reply_markup=get_categories_keyboard(cats, lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("toggle_cat:"))
async def handle_toggle_category(callback: CallbackQuery):
    cat_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    user = await Repository.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    await Repository.toggle_user_category_filter(user_id, cat_id)
    cats = await Repository.get_user_category_filters(user_id)
    await callback.answer()
    await safe_edit_reply_markup(callback, reply_markup=get_categories_keyboard(cats, lang))

@router.callback_query(F.data.startswith("cats_all:"))
async def handle_cats_all(callback: CallbackQuery):
    enable_all = callback.data.split(":")[1] == "1"
    user_id = callback.from_user.id
    user = await Repository.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    await Repository.set_all_user_categories(user_id, enable_all)
    cats = await Repository.get_user_category_filters(user_id)
    await callback.answer()
    await safe_edit_reply_markup(callback, reply_markup=get_categories_keyboard(cats, lang))

# --- Notification Schedule ---
@router.callback_query(F.data == "settings:notif")
async def handle_settings_notif(callback: CallbackQuery):
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"
    mode = user.get("notif_mode", "instant") if user else "instant"
    hour = user.get("digest_hour", 8) if user else 8

    await callback.answer()
    await safe_edit_text(
        callback,
        get_text("notif_title", lang),
        reply_markup=get_notification_keyboard(mode, hour, lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("notif_set:"))
async def handle_notif_mode_set(callback: CallbackQuery):
    mode = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await Repository.update_user_notif_mode(user_id, mode)

    user = await Repository.get_user(user_id)
    lang = user.get("language", "en") if user else "en"
    hour = user.get("digest_hour", 8) if user else 8

    mode_label = get_text(f"notif_{mode}", lang)
    await callback.answer(get_text("notif_updated", lang, mode=mode_label))
    await safe_edit_text(
        callback,
        get_text("notif_title", lang),
        reply_markup=get_notification_keyboard(mode, hour, lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("digest_hour:"))
async def handle_digest_hour_set(callback: CallbackQuery):
    hour = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    user = await Repository.get_user(user_id)
    lang = user.get("language", "en") if user else "en"
    mode = user.get("notif_mode", "digest") if user else "digest"

    await Repository.update_user_notif_mode(user_id, mode, digest_hour=hour)
    await callback.answer(f"Digest set to {hour:02d}:00")
    await safe_edit_reply_markup(callback, reply_markup=get_notification_keyboard(mode, hour, lang))
