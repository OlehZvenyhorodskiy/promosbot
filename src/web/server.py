import logging
from datetime import datetime
from aiohttp import web

from src.core.config import settings
from src.db.repository import Repository
from src.scrapers.engine import ScraperEngine
from src.services.scheduler import NotificationDispatcher
from src.services.gemini_folder_parser import GeminiFolderParser

logger = logging.getLogger(__name__)

@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.path.startswith("/api/v1/"):
        secret = settings.API_SECRET
        if secret:
            provided = request.headers.get("X-API-Key")
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                provided = auth_header[7:].strip()
            if not provided or provided != secret:
                return web.json_response(
                    {"error": "Unauthorized: Invalid or missing API secret key."},
                    status=401,
                )
    return await handler(request)

def create_web_app(engine: ScraperEngine, dispatcher: NotificationDispatcher) -> web.Application:
    app = web.Application(middlewares=[auth_middleware])
    gemini_parser = GeminiFolderParser()

    async def handle_root(request: web.Request) -> web.Response:
        count = await Repository.count_promos()
        return web.json_response({
            "status": "online",
            "app": "Belgium Promo's Telegram Bot",
            "bot": "@belgiumpromos_bot",
            "active_promos_count": count,
            "timestamp": datetime.now().isoformat(),
        })

    async def handle_health(request: web.Request) -> web.Response:
        return web.json_response({"status": "healthy", "uptime": "ok"})

    async def handle_ping(request: web.Request) -> web.Response:
        return web.json_response({"pong": True, "time": datetime.now().isoformat()})

    async def handle_inbound_promo(request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                return web.json_response({"error": "Payload must be a JSON object"}, status=400)

            title = payload.get("title")
            if not title:
                return web.json_response({"error": "Missing 'title'"}, status=400)

            promo_id, is_new = await Repository.save_promo(payload)
            payload["id"] = promo_id
            payload.setdefault("store_id", "generic")
            payload.setdefault("category_id", "pantry")

            if is_new and dispatcher:
                # Keep every ingestion path on the same grouped notification
                # flow as the live scrapers. The old instant path could spam
                # users and bypass the mute setting's intended UX.
                dispatcher.queue_new_promo(payload)

            return web.json_response({
                "success": True,
                "promo_id": promo_id,
                "is_new": is_new,
            })
        except Exception as e:
            logger.error(f"Error handling inbound promo: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_inbound_newsletter(request: web.Request) -> web.Response:
        try:
            if request.content_type == "application/json":
                data = await request.json()
                html = data.get("html", "")
                sender = data.get("sender", "")
                subject = data.get("subject", "")
                deal_url = data.get("deal_url")
            else:
                html = await request.text()
                sender = request.headers.get("X-Sender", "")
                subject = request.headers.get("X-Subject", "")
                deal_url = None

            if not html:
                return web.json_response({"error": "Empty HTML body"}, status=400)

            saved_items = await engine.ingest_newsletter(html, sender=sender, subject=subject, deal_url=deal_url)
            return web.json_response({
                "success": True,
                "items_parsed": len(saved_items),
                "items": [{"id": it["id"], "title": it["title"], "store": it["store_id"]} for it in saved_items],
            })
        except Exception as e:
            logger.error(f"Error ingesting newsletter: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_parse_folder(request: web.Request) -> web.Response:
        try:
            reader = await request.multipart()
            field = await reader.next()
            if not field or field.name != "image":
                return web.json_response({"error": "Missing 'image' multipart field"}, status=400)

            img_bytes = await field.read()
            store_id = request.query.get("store", "colruyt")
            page = int(request.query.get("page", "1"))

            items = await gemini_parser.parse_flyer_page(
                image_bytes=img_bytes,
                mime_type="image/jpeg",
                store_id=store_id,
                page_num=page,
            )

            saved = []
            for it in items:
                p_id, is_new = await Repository.save_promo(it.to_dict())
                item = it.to_dict()
                item["id"] = p_id
                if is_new and dispatcher:
                    dispatcher.queue_new_promo(item)
                saved.append({"id": p_id, "title": it.title, "price": it.promo_price, "is_new": is_new})

            return web.json_response({"success": True, "parsed": len(saved), "items": saved})
        except Exception as e:
            logger.error(f"Error parsing flyer: {e}")
            return web.json_response({"error": str(e)}, status=500)

    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/ping", handle_ping)
    app.router.add_post("/api/v1/inbound-promo", handle_inbound_promo)
    app.router.add_post("/api/v1/inbound-newsletter", handle_inbound_newsletter)
    app.router.add_post("/api/v1/parse-folder", handle_parse_folder)

    return app
