import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List
from aiogram import Bot
from src.core.config import settings
from src.db.repository import Repository
from src.bot.formatters import format_promo_card, format_digest_header
from src.bot.keyboards import get_promo_card_keyboard, get_new_promos_keyboard
from src.i18n.translations import get_text
from src.core.constants import SUPERMARKETS
from src.scrapers.engine import ScraperEngine

logger = logging.getLogger(__name__)

class NotificationDispatcher:
    def __init__(self, bot: Bot):
        self.bot = bot
        self._pending_promos: Dict[str, Dict[str, Any]] = {}

    def queue_new_promo(self, promo: Dict[str, Any]) -> None:
        """Collect new records; one digest is sent instead of one message per item."""
        promo_id = promo.get("id")
        if promo_id:
            self._pending_promos[promo_id] = promo

    async def flush_pending_alerts(self) -> int:
        if not self.bot or not self._pending_promos:
            return 0

        pending = list(self._pending_promos.values())
        users = await Repository.get_users_for_alert_batch()
        eligible_by_user = []
        for user in users:
            stores = await Repository.get_user_store_filters(user["user_id"])
            categories = await Repository.get_user_category_filters(user["user_id"])
            eligible = [
                promo for promo in pending
                if promo.get("store_id") in stores and promo.get("category_id") in categories
            ]
            if eligible:
                eligible_by_user.append((user, eligible))

        # No subscribed users: discard the batch without producing noise.
        if not eligible_by_user:
            self._pending_promos.clear()
            return 0

        batch_id = await Repository.create_alert_batch(pending)
        delivered = 0
        try:
            for user, eligible in eligible_by_user:
                store_counts: Dict[str, int] = {}
                for promo in eligible:
                    store_id = promo.get("store_id", "generic")
                    store_counts[store_id] = store_counts.get(store_id, 0) + 1
                labels = ", ".join(
                    f"{SUPERMARKETS.get(store_id, {}).get('name', store_id)}: {count}"
                    for store_id, count in store_counts.items()
                )
                lang = user.get("language", "en")
                text = get_text("new_promos_summary", lang, total=len(eligible))
                text = f"{text}\n\n<code>{labels}</code>"
                await self.bot.send_message(
                    chat_id=user["user_id"],
                    text=text,
                    reply_markup=get_new_promos_keyboard(store_counts, batch_id, lang),
                    parse_mode="HTML",
                )
                delivered += 1
        except Exception as exc:
            logger.warning("Failed to deliver grouped promotion alerts: %s", exc)
            return 0

        self._pending_promos.clear()
        await Repository.cleanup_alert_batches()
        logger.info("Delivered grouped promotion alert batch %s to %s users (%s promos).", batch_id, delivered, len(pending))
        return len(pending)

    async def dispatch_instant_alert(self, promo: Dict[str, Any]):
        promo_id = promo.get("id")
        store_id = promo.get("store_id")
        category_id = promo.get("category_id")

        if not promo_id or not store_id or not category_id:
            return

        users = await Repository.get_users_for_instant_alert(store_id, category_id)
        if not users:
            return

        image_url = promo.get("image_url")
        deal_url = promo.get("deal_url")

        for u in users:
            user_id = u["user_id"]
            if await Repository.has_notification_been_sent(user_id, promo_id):
                continue

            lang = u.get("language", "en")
            card_text = f"⚡ <b>NEW PROMOTION ALERT!</b>\n\n{format_promo_card(promo, lang=lang)}"
            reply_markup = get_promo_card_keyboard(
                promo_id=promo_id,
                deal_url=deal_url,
                is_fav=False,
                current_index=0,
                total_count=1,
                lang=lang,
                nav_prefix="alert",
            )

            try:
                sent = False
                if image_url and image_url.startswith("http"):
                    try:
                        await self.bot.send_photo(
                            chat_id=user_id,
                            photo=image_url,
                            caption=card_text,
                            reply_markup=reply_markup,
                            parse_mode="HTML",
                        )
                        sent = True
                    except Exception:
                        pass

                if not sent:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=card_text,
                        reply_markup=reply_markup,
                        parse_mode="HTML",
                    )
                await Repository.record_notification_sent(user_id, promo_id)
            except Exception as e:
                logger.warning(f"Failed to send instant alert to user {user_id}: {e}")

    async def dispatch_digest_for_hour(self, current_hour: int):
        users = await Repository.get_users_for_digest(current_hour)
        if not users:
            return

        for u in users:
            user_id = u["user_id"]
            lang = u.get("language", "en")
            stores = list(await Repository.get_user_store_filters(user_id))
            cats = list(await Repository.get_user_category_filters(user_id))

            deals = await Repository.get_promos(store_ids=stores, category_ids=cats, limit=5)
            if not deals:
                continue

            header = format_digest_header(len(deals), lang=lang)
            try:
                await self.bot.send_message(chat_id=user_id, text=header, parse_mode="HTML")
                for d in deals:
                    card_text = format_promo_card(d, lang=lang)
                    markup = get_promo_card_keyboard(
                        promo_id=d["id"],
                        deal_url=d.get("deal_url"),
                        is_fav=False,
                        current_index=0,
                        total_count=1,
                        lang=lang,
                        nav_prefix="digest",
                        image_url=d.get("image_url"),
                    )
                    img = d.get("image_url")
                    sent_item = False
                    if img and img.startswith("http"):
                        try:
                            await self.bot.send_photo(chat_id=user_id, photo=img, caption=card_text, reply_markup=markup, parse_mode="HTML")
                            sent_item = True
                        except Exception:
                            pass
                    if not sent_item:
                        await self.bot.send_message(chat_id=user_id, text=card_text, reply_markup=markup, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Failed to send digest to user {user_id}: {e}")

async def scraper_loop(engine: ScraperEngine, interval_minutes: int):
    # Let Telegram polling become responsive before the first network-heavy
    # baseline scrape. This also prevents the initial catalog from generating
    # a false "new promotion" storm.
    await asyncio.sleep(30)
    while True:
        try:
            logger.info("Executing scheduled scraper cycle...")
            await engine.run_all_scrapers()
        except Exception as e:
            logger.error(f"Error during scheduled scraper cycle: {e}")
        await asyncio.sleep(interval_minutes * 60)

async def alert_batch_loop(dispatcher: NotificationDispatcher, interval_minutes: int = 10):
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            await dispatcher.flush_pending_alerts()
        except Exception as exc:
            logger.error("Error delivering grouped promotion alerts: %s", exc)

async def digest_loop(dispatcher: NotificationDispatcher):
    last_sent_hour = -1
    while True:
        now = datetime.now()
        current_hour = now.hour
        # Check every hour once
        if current_hour != last_sent_hour:
            logger.info(f"Checking scheduled morning digests for hour {current_hour}...")
            try:
                await dispatcher.dispatch_digest_for_hour(current_hour)
                last_sent_hour = current_hour
            except Exception as e:
                logger.error(f"Error dispatching morning digest: {e}")
        await asyncio.sleep(60)

async def keep_alive_loop(url: str):
    if not url:
        return
    import aiohttp
    logger.info(f"Keep-alive loop active for {url}")
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    logger.debug(f"Keep-alive ping to {url}: status {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")
        await asyncio.sleep(300) # Ping every 5 minutes
