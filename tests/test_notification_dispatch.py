import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from aiogram.exceptions import TelegramRetryAfter

from src.db.repository import Repository
from src.services import scheduler
from src.services.scheduler import NotificationDispatcher, _current_brussels_hour


class FakeBot:
    def __init__(self):
        self.send_message = AsyncMock()
        self.send_photo = AsyncMock()


def _mock_repository_for_flush(monkeypatch, users):
    monkeypatch.setattr(Repository, "get_users_for_alert_batch", AsyncMock(return_value=users))
    monkeypatch.setattr(Repository, "get_user_store_filters", AsyncMock(return_value={"colruyt"}))
    monkeypatch.setattr(Repository, "get_user_category_filters", AsyncMock(return_value={"drinks"}))
    monkeypatch.setattr(Repository, "create_alert_batch", AsyncMock(return_value=42))
    monkeypatch.setattr(Repository, "cleanup_alert_batches", AsyncMock(return_value=None))


@pytest.mark.asyncio
async def test_retry_after_once_then_success(monkeypatch):
    dispatcher = NotificationDispatcher(FakeBot())
    dispatcher.queue_new_promo({"id": "p1", "store_id": "colruyt", "category_id": "drinks"})

    users = [{"user_id": 1, "language": "en"}]
    _mock_repository_for_flush(monkeypatch, users)

    bot = dispatcher.bot
    bot.send_message.side_effect = [
        TelegramRetryAfter(None, "flood control", 5),
        {"message_id": 11},
    ]

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    result = await dispatcher.flush_pending_alerts()

    assert result == 1
    assert bot.send_message.await_count == 2
    assert 5 in sleep_calls
    assert bot.send_message.await_args_list[0].kwargs["chat_id"] == 1


@pytest.mark.asyncio
async def test_retry_after_twice_skips_user_others_still_get(monkeypatch):
    dispatcher = NotificationDispatcher(FakeBot())
    dispatcher.queue_new_promo({"id": "p1", "store_id": "colruyt", "category_id": "drinks"})

    users = [{"user_id": 1, "language": "en"}, {"user_id": 2, "language": "en"}]
    _mock_repository_for_flush(monkeypatch, users)

    bot = dispatcher.bot
    bot.send_message.side_effect = [
        TelegramRetryAfter(None, "flood control", 5),  # user 1 first attempt
        TelegramRetryAfter(None, "flood control", 5),  # user 1 single retry
        {"message_id": 22},  # user 2 first attempt
    ]

    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    result = await dispatcher.flush_pending_alerts()

    assert result == 1
    assert bot.send_message.await_count == 3
    delivered_chats = [c.kwargs["chat_id"] for c in bot.send_message.await_args_list]
    assert 2 in delivered_chats


@pytest.mark.asyncio
async def test_normal_exception_isolates_user(monkeypatch):
    dispatcher = NotificationDispatcher(FakeBot())
    dispatcher.queue_new_promo({"id": "p1", "store_id": "colruyt", "category_id": "drinks"})

    users = [{"user_id": 1, "language": "en"}, {"user_id": 2, "language": "en"}]
    _mock_repository_for_flush(monkeypatch, users)

    bot = dispatcher.bot
    bot.send_message.side_effect = [
        RuntimeError("chat not found"),  # user 1
        {"message_id": 22},  # user 2
    ]

    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    result = await dispatcher.flush_pending_alerts()

    assert result == 1
    assert bot.send_message.await_count == 2
    delivered_chats = [c.kwargs["chat_id"] for c in bot.send_message.await_args_list]
    assert delivered_chats == [1, 2]


@pytest.mark.asyncio
async def test_retry_after_backoff_is_capped(monkeypatch):
    send = AsyncMock(side_effect=[TelegramRetryAfter(None, "flood control", 120), None])

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    result = await scheduler._send_telegram_with_retry(send)

    assert result is True
    assert send.await_count == 2
    assert 60 in sleep_calls
    assert 120 not in sleep_calls


def test_current_brussels_hour_midnight_rollover():
    # UTC 22:00 on a CEST day -> 00:00 the next day in Brussels.
    now = datetime(2026, 9, 14, 22, 0, tzinfo=timezone.utc)
    assert _current_brussels_hour(now) == 0


def test_current_brussels_hour_cest_morning():
    # UTC 06:30 -> 08:30 in Brussels (CEST, UTC+2); only the hour matters.
    now = datetime(2026, 9, 14, 6, 30, tzinfo=timezone.utc)
    assert _current_brussels_hour(now) == 8
