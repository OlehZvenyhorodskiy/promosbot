import asyncio
import logging
from typing import List, Optional, Callable, Dict, Any
from src.scrapers.models import PromoItem
from src.scrapers.base import BaseScraper
from src.scrapers.aldi import AldiScraper
from src.scrapers.colruyt import ColruytScraper
from src.scrapers.carrefour import CarrefourScraper
from src.scrapers.generic import GenericRetailerScraper
from src.scrapers.browser import BrowserRetailerScraper
from src.core.constants import SUPERMARKETS
from src.scrapers.newsletter import NewsletterParser
from src.scrapers.seed_data import DEMO_PROMOS
from src.db.repository import Repository
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException
from src.scrapers.leaflets.orchestrator import LeafletOrchestrator

logger = logging.getLogger(__name__)

class ScraperEngine:
    def __init__(self, on_new_promo_callback: Optional[Callable[[Dict[str, Any]], Any]] = None):
        self.scrapers: List[BaseScraper] = [
            AldiScraper(),
            ColruytScraper(),
            CarrefourScraper(),
            GenericRetailerScraper("delhaize", "Delhaize", SUPERMARKETS["delhaize"]["url"]),
            GenericRetailerScraper("lidl", "Lidl", SUPERMARKETS["lidl"]["url"], ssl_verify=False),
            GenericRetailerScraper("albert_heijn", "Albert Heijn", SUPERMARKETS["albert_heijn"]["url"]),
            GenericRetailerScraper("jumbo", "Jumbo", SUPERMARKETS["jumbo"]["url"]),
            GenericRetailerScraper("spar", "Spar", SUPERMARKETS["spar"]["url"]),
            GenericRetailerScraper("cora", "Cora", SUPERMARKETS["cora"]["url"]),
            GenericRetailerScraper("intermarche", "Intermarché", SUPERMARKETS["intermarche"]["url"]),
        ]
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            s.store_id: CircuitBreaker(name=s.name, failure_threshold=3, recovery_timeout=300.0)
            for s in self.scrapers
        }
        self.leaflet_orchestrator = LeafletOrchestrator()
        # Some retailers return a shell or a protected page to aiohttp. Keep
        # the fast HTTP adapters, then use one shared Chromium runtime only
        # for sources that produced no usable products.
        self.browser_fallbacks = {
            store_id: BrowserRetailerScraper(
                store_id,
                SUPERMARKETS[store_id]["name"],
                SUPERMARKETS[store_id]["url"],
                ssl_verify=False,
            )
            for store_id in SUPERMARKETS
        }
        self.on_new_promo_callback = on_new_promo_callback
        self._baseline_complete = False

    async def seed_data_if_empty(self) -> int:
        removed = await Repository.cleanup_invalid_promos()
        if removed:
            logger.info("Removed %s invalid placeholder promotions from the catalog.", removed)
        total = await Repository.count_promos()
        if total == 0:
            logger.info("Database empty, seeding realistic Belgian supermarket promo deals...")
            count = 0
            for promo in DEMO_PROMOS:
                promo_id, is_new = await Repository.save_promo(promo.to_dict())
                if is_new:
                    count += 1
            logger.info(f"Seeded {count} Belgian supermarket promo deals successfully.")
            return count
        return total

    async def run_all_scrapers(self) -> int:
        logger.info("Starting live supermarket scrapers run...")
        tasks = [
            self.circuit_breakers[s.store_id].call(s.fetch_promos)
            for s in self.scrapers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        new_count = 0
        for i, res in enumerate(results):
            scraper_name = self.scrapers[i].name
            store_id = self.scrapers[i].store_id
            if isinstance(res, CircuitBreakerOpenException):
                logger.warning(f"Scraper {scraper_name} skipped (CircuitBreaker is OPEN).")
                continue
            if isinstance(res, Exception):
                logger.error(f"Scraper {scraper_name} encountered an error: {res}")
                continue
            if isinstance(res, list):
                if not res and store_id in self.browser_fallbacks:
                    fallback = self.browser_fallbacks[store_id]
                    res = await fallback.fetch_promos()
                logger.info(f"Scraper {scraper_name} fetched {len(res)} items")
                promo_dicts = [item.to_dict() for item in res]
                saved = await Repository.save_promos_bulk(promo_dicts)
                for promo_dict, (promo_id, is_new) in zip(promo_dicts, saved):
                    if is_new:
                        new_count += 1
                        promo_dict["id"] = promo_id
                        # The first live scrape establishes a baseline. Those
                        # products are not necessarily new at the retailer.
                        if self._baseline_complete and self.on_new_promo_callback:
                            try:
                                await self.on_new_promo_callback(promo_dict)
                            except Exception as alert_err:
                                logger.error(f"Error dispatching promo alert: {alert_err}")

        # Ingest digital brochures and leaflets
        try:
            leaflet_new = await self.run_leaflet_scrapers()
            new_count += leaflet_new
        except Exception as lf_err:
            logger.error(f"Error during leaflet ingestion: {lf_err}")

        if not self._baseline_complete:
            logger.info(
                "Initial live scrape established the baseline; %s existing retailer items were not alerted.",
                new_count,
            )
            self._baseline_complete = True
        else:
            logger.info(f"Scraping cycle complete. Added {new_count} new promotional deals.")
        return new_count

    async def run_leaflet_scrapers(self) -> int:
        """Fetch and persist deals from digital supermarket brochures."""
        items = await self.leaflet_orchestrator.fetch_all_leaflets()
        if not items:
            return 0
        new_count = 0
        promo_dicts = [item.to_dict() for item in items]
        saved = await Repository.save_promos_bulk(promo_dicts)
        for promo_dict, (promo_id, is_new) in zip(promo_dicts, saved):
            if is_new:
                new_count += 1
                promo_dict["id"] = promo_id
                if self._baseline_complete and self.on_new_promo_callback:
                    try:
                        await self.on_new_promo_callback(promo_dict)
                    except Exception as alert_err:
                        logger.error(f"Error dispatching leaflet promo alert: {alert_err}")
        return new_count

    async def ingest_newsletter(
        self,
        html_content: str,
        sender: str = "",
        subject: str = "",
        deal_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        items = NewsletterParser.parse_newsletter_html(html_content, sender, subject, deal_url)
        saved_items = []
        promo_dicts = [item.to_dict() for item in items]
        saved = await Repository.save_promos_bulk(promo_dicts)
        for promo_dict, (promo_id, is_new) in zip(promo_dicts, saved):
            promo_dict["id"] = promo_id
            saved_items.append(promo_dict)
            if is_new and self.on_new_promo_callback:
                try:
                    await self.on_new_promo_callback(promo_dict)
                except Exception as alert_err:
                    logger.error(f"Error dispatching newsletter promo alert: {alert_err}")
        return saved_items
