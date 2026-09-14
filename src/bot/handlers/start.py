import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from src.db.repository import Repository
from src.i18n.translations import get_text
from src.bot.keyboards import (
    get_main_reply_keyboard,
    get_unified_welcome_keyboard,
    get_main_hub_keyboard,
    get_folders_keyboard,
    get_store_drilldown_keyboard,
    get_language_keyboard,
)
from src.bot.message_manager import (
    delete_incoming_message,
    send_top_level_message,
    send_bot_message,
    safe_edit_text,
)

logger = logging.getLogger(__name__)
router = Router()

FOLDERS_BUTTON_TEXTS = ["📰 Folders & Leaflets", "📰 Буклети та брошури", "📰 Folders & Folders", "📰 Dépliants & Catalogues"]

@router.message(CommandStart())
async def handle_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Delete incoming /start command immediately to keep chat clean.
    await delete_incoming_message(message)

    user = await Repository.get_or_create_user(user_id, username, first_name)
    if not user.get("language_selected", 0):
        await send_top_level_message(
            message,
            get_text("choose_language", "en"),
            reply_markup=get_language_keyboard(),
            parse_mode="HTML",
        )
        return

    lang = user.get("language", "en")

    counts = await Repository.get_promo_counts_by_store()
    total = sum(counts.values())

    # 1. Attach the persistent bottom reply menu
    await send_top_level_message(
        message,
        get_text("welcome_title", lang),
        reply_markup=get_main_reply_keyboard(lang),
        parse_mode="HTML",
    )

    # 2. Open supermarket catalog directly with inline buttons
    await send_top_level_message(
        message,
        get_text("store_drilldown_title", lang),
        reply_markup=get_store_drilldown_keyboard(counts, total, lang),
        parse_mode="HTML",
        clear_previous=False,
    )

@router.callback_query(F.data.startswith("lang:"))
async def handle_set_language(callback: CallbackQuery):
    lang_code = callback.data.split(":")[1]
    user_id = callback.from_user.id
    previous_user = await Repository.get_user(user_id)
    first_language_selection = not previous_user or not previous_user.get("language_selected", 1)
    await Repository.update_user_language(user_id, lang_code)

    msg_text = get_text("language_updated", lang_code)
    await callback.answer(msg_text)

    counts = await Repository.get_promo_counts_by_store()
    total = sum(counts.values())
    if first_language_selection:
        await send_bot_message(
            callback.bot,
            callback.message.chat.id,
            get_text("welcome_title", lang_code),
            reply_markup=get_main_reply_keyboard(lang_code),
            parse_mode="HTML",
            clear_previous=False,
        )
    drilldown_title = get_text("store_drilldown_title", lang_code)
    markup = get_store_drilldown_keyboard(counts, total, lang_code)
    await safe_edit_text(
        callback,
        drilldown_title,
        reply_markup=markup,
        parse_mode="HTML",
    )

@router.callback_query(F.data == "nav:main")
async def handle_nav_main(callback: CallbackQuery):
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "uk") if user else "uk"
    await callback.answer()

    # Lead directly to supermarket catalog as requested by user
    counts = await Repository.get_promo_counts_by_store()
    total = sum(counts.values())
    drilldown_title = get_text("store_drilldown_title", lang)
    markup = get_store_drilldown_keyboard(counts, total, lang)
    await safe_edit_text(
        callback,
        drilldown_title,
        reply_markup=markup,
        parse_mode="HTML",
    )

@router.message(F.entities)
async def handle_custom_emoji_inspector(message: Message):
    emoji_ids = [
        e.custom_emoji_id
        for e in (message.entities or [])
        if e.type == "custom_emoji" and e.custom_emoji_id
    ]
    if emoji_ids:
        ids_str = "\n".join(f"• <code>{eid}</code>" for eid in emoji_ids)
        await message.reply(
            f"🏷️ <b>Знайдено Custom Emoji ID:</b>\n{ids_str}\n\n"
            f"<i>Цей ідентифікатор можна використати для іконки супермаркету чи товару.</i>",
            parse_mode="HTML",
        )

@router.message(Command("folders"))
@router.message(F.text.in_(FOLDERS_BUTTON_TEXTS))
async def handle_folders_command(message: Message):
    user = await Repository.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")
    await delete_incoming_message(message)
    await send_top_level_message(
        message,
        get_text("folders_title", lang),
        reply_markup=get_folders_keyboard(lang),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "nav:folders")
async def handle_nav_folders(callback: CallbackQuery):
    user = await Repository.get_user(callback.from_user.id)
    lang = user.get("language", "en") if user else "en"
    await callback.answer()
    await safe_edit_text(
        callback,
        get_text("folders_title", lang),
        reply_markup=get_folders_keyboard(lang),
        parse_mode="HTML",
    )

@router.message(Command("help"))
@router.message(F.text.in_(["ℹ️ Help", "ℹ️ Допомога", "ℹ️ Hulp", "ℹ️ Aide"]))
async def handle_help(message: Message):
    user = await Repository.get_user(message.from_user.id)
    lang = user.get("language", "en") if user else "en"
    await delete_incoming_message(message)
    await send_top_level_message(
        message,
        get_text("help_text", lang),
        parse_mode="HTML",
        reply_markup=get_main_reply_keyboard(lang),
    )

@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery):
    await callback.answer()
