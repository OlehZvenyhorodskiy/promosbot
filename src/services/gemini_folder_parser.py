import os
import asyncio
import json
import logging
import ssl
import certifi
import aiohttp
from typing import List, Dict, Any, Optional
from src.scrapers.models import PromoItem
from src.scrapers.base import infer_category

logger = logging.getLogger(__name__)

class GeminiFolderParser:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = "gemini-2.5-flash"
        self.delay_between_pages = 3.5 # Rate limit: 1 page every 3.5 seconds

    async def parse_flyer_page(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        store_id: str = "colruyt",
        page_num: int = 1,
    ) -> List[PromoItem]:
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set. Gemini flyer parsing is in mock/standby mode.")
            return []

        import base64
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        prompt = (
            "You are a structured parser for Belgian supermarket promo flyers. "
            "Analyze this flyer page and extract all promotional products. "
            "Return ONLY a JSON array where each object has: "
            "title (product name), original_price (number or null), promo_price (number), "
            "discount_text (e.g. '1+1 GRATIS', '2+2 GRATUIT', '-50%', '2 voor €5'), "
            "unit_info (e.g. '500g', '2x75cl'), valid_until (date or null). "
            "Do not include markdown code block markers, return raw JSON array."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        }

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        items: List[PromoItem] = []
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error(f"Gemini API error {resp.status}: {err_text[:200]}")
                        return items

                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return items

                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        for idx, entry in enumerate(parsed):
                            name = entry.get("title")
                            if not name:
                                continue
                            promo_p = entry.get("promo_price")
                            orig_p = entry.get("original_price")
                            disc = entry.get("discount_text", "")
                            unit = entry.get("unit_info", "")
                            valid_u = entry.get("valid_until")

                            cat_id = infer_category(name)
                            items.append(
                                PromoItem(
                                    store_id=store_id,
                                    external_id=f"folder_{store_id}_p{page_num}_{idx}",
                                    title=name,
                                    original_price=float(orig_p) if orig_p is not None else None,
                                    promo_price=float(promo_p) if promo_p is not None else None,
                                    discount_text=disc,
                                    unit_info=unit,
                                    valid_until=valid_u,
                                    category_id=cat_id,
                                )
                            )
        except Exception as e:
            logger.error(f"Failed to parse flyer page with Gemini: {e}")

        # Polite rate-limiting between pages
        await asyncio.sleep(self.delay_between_pages)
        return items
