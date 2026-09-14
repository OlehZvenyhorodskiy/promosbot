import pytest
import os
from aiohttp import web
from src.core.config import settings
from src.db.database import init_db
from src.scrapers.engine import ScraperEngine
from src.services.scheduler import NotificationDispatcher
from src.web.server import create_web_app

@pytest.mark.asyncio
async def test_web_server(aiohttp_client):
    db_file = "data/test_web.db"
    settings.DB_PATH = db_file
    try:
        await init_db()
        engine = ScraperEngine()
        # Mock dispatcher without real bot connection for test
        dispatcher = NotificationDispatcher(None)
        app = create_web_app(engine, dispatcher)
        client = await aiohttp_client(app)

        # Health
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"

        # Ping
        resp = await client.get("/ping")
        assert resp.status == 200
        data = await resp.json()
        assert data["pong"] is True

        # Inbound promo
        promo_payload = {
            "store_id": "lidl",
            "title": "Bio Kaas Plakken",
            "promo_price": 2.49,
            "original_price": 3.99,
            "discount_text": "-37%",
            "category_id": "dairy_cheese",
        }
        resp = await client.post("/api/v1/inbound-promo", json=promo_payload)
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True
        assert data["is_new"] is True

        # Inbound newsletter
        newsletter_payload = {
            "sender": "promo@colruyt.be",
            "subject": "Colruyt Deals",
            "html": "<div><h3>Stella Artois 24-pack</h3><p>1+1 GRATIS</p><p>€ 14,99</p></div>",
        }
        resp = await client.post("/api/v1/inbound-newsletter", json=newsletter_payload)
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True
        assert data["items_parsed"] >= 1

        # Test auth protection when API_SECRET is set
        settings.API_SECRET = "supersecret123"
        # Should fail without header
        resp_unauth = await client.post("/api/v1/inbound-promo", json=promo_payload)
        assert resp_unauth.status == 401

        # Should fail with wrong header
        resp_wrong = await client.post(
            "/api/v1/inbound-promo",
            json=promo_payload,
            headers={"X-API-Key": "wrong"},
        )
        assert resp_wrong.status == 401

        # Should succeed with correct Bearer header
        resp_auth = await client.post(
            "/api/v1/inbound-promo",
            json=promo_payload,
            headers={"Authorization": "Bearer supersecret123"},
        )
        assert resp_auth.status == 200

        # Test scraper health endpoint
        resp_health = await client.get(
            "/api/v1/health/scrapers",
            headers={"Authorization": "Bearer supersecret123"},
        )
        assert resp_health.status == 200
        health_data = await resp_health.json()
        assert health_data["status"] == "ok"
        assert health_data["total_stores"] >= 10

        # Test trigger endpoint
        resp_trigger = await client.post(
            "/api/v1/scrape/trigger?store=colruyt",
            headers={"Authorization": "Bearer supersecret123"},
        )
        assert resp_trigger.status == 200
        trigger_data = await resp_trigger.json()
        assert trigger_data["success"] is True
    finally:
        settings.API_SECRET = ""
        if os.path.exists(db_file):
            os.remove(db_file)
