"""Small helpers for keeping one clean, replaceable bot UI per chat."""

import logging
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger(__name__)

# This is intentionally in-memory: it prevents clutter during the current
# process lifetime without adding a migration for a UI-only piece of state.
_last_bot_message_ids: dict[int, list[int]] = {}


async def delete_incoming_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        # Users can send commands in chats where the bot cannot delete them.
        pass


async def clear_last_bot_messages(bot: Any, chat_id: int) -> None:
    message_ids = _last_bot_message_ids.pop(chat_id, [])
    for message_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            # The message may already have been deleted or be outside the
            # bot's deletion window.
            pass


def remember_bot_message(message: Message) -> Message:
    chat_id = message.chat.id
    _last_bot_message_ids[chat_id] = _last_bot_message_ids.get(chat_id, []) + [message.message_id]
    return message


async def send_top_level_message(
    message: Message,
    *args: Any,
    clear_previous: bool = True,
    **kwargs: Any,
) -> Message:
    """Delete the prior tracked UI and send/track a replacement message."""
    if clear_previous:
        await clear_last_bot_messages(message.bot, message.chat.id)
    sent = await message.answer(*args, **kwargs)
    return remember_bot_message(sent)


async def send_bot_message(
    bot: Any,
    chat_id: int,
    *args: Any,
    clear_previous: bool = False,
    **kwargs: Any,
) -> Message:
    if clear_previous:
        await clear_last_bot_messages(bot, chat_id)
    sent = await bot.send_message(chat_id, *args, **kwargs)
    return remember_bot_message(sent)


async def safe_edit_text(callback: CallbackQuery, *args: Any, **kwargs: Any) -> bool:
    """Edit an inline UI in place; tolerate Telegram's no-op edit error."""
    try:
        await callback.message.edit_text(*args, **kwargs)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.warning("Could not edit callback message: %s", exc)
        return False


async def safe_edit_reply_markup(callback: CallbackQuery, *args: Any, **kwargs: Any) -> bool:
    try:
        await callback.message.edit_reply_markup(*args, **kwargs)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.warning("Could not edit callback markup: %s", exc)
        return False
