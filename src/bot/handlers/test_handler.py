from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions
from aiogram.filters import Command
from src.db.repository import Repository
from src.i18n.translations import get_text
from src.bot.formatters import format_promo_card
from src.bot.keyboards import get_promo_card_keyboard
from src.bot.message_manager import delete_incoming_message, send_top_level_message
from src.scrapers.seed_data import DEMO_PROMOS

router = Router()

TEST_BUTTON_TEXTS = ["🧪 Test Promo Card", "🧪 Тестова картка", "🧪 Test Promokaart", "🧪 Carte Promo Test"]

@router.message(Command("test_promo"))
@router.message(F.text.in_(TEST_BUTTON_TEXTS))
async def handle_test_promo(message: Message):
    user_id = message.from_user.id
    user = await Repository.get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language", "en")

    await delete_incoming_message(message)

    # Pick the classic 2+2 Gouda cheese demo deal from Colruyt
    sample_deal = DEMO_PROMOS[0].to_dict()
    sample_deal["id"] = sample_deal.get("external_id")

    image_url = sample_deal.get("image_url")
    card_text = format_promo_card(sample_deal, lang=lang, is_fav=False)

    reply_markup = get_promo_card_keyboard(
        promo_id=sample_deal["id"],
        deal_url=sample_deal.get("deal_url"),
        is_fav=False,
        current_index=0,
        total_count=1,
        lang=lang,
        nav_code="test",
        image_url=image_url,
    )

    await send_top_level_message(
        message,
        card_text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
