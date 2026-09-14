import asyncio
import logging
from typing import List, Dict, Any
from src.scrapers.models import PromoItem
from src.scrapers.leaflets.publitas import PublitasLeafletExtractor
from src.scrapers.leaflets.tiendeo import TiendeoAggregator
from src.scrapers.leaflets.pdf_extractor import PDFLeafletExtractor
from src.db.repository import Repository

logger = logging.getLogger(__name__)

class LeafletOrchestrator:
    """
    Coordinates multi-channel extraction of supermarket brochures and digital flyers.
    """

    def __init__(self):
        self.publitas_extractors: Dict[str, PublitasLeafletExtractor] = {
            "albert_heijn": PublitasLeafletExtractor("albert_heijn", "albert-heijn-belgie"),
            "aldi": PublitasLeafletExtractor("aldi", "aldi-belgie"),
            "jumbo": PublitasLeafletExtractor("jumbo", "jumbo-belgie"),
            "colruyt": PublitasLeafletExtractor("colruyt", "colruyt"),
            "kruidvat": PublitasLeafletExtractor("kruidvat", "kruidvat-belgie"),
            "okay": PublitasLeafletExtractor("okay", "okay"),
        }
        self.tiendeo = TiendeoAggregator()
        self.pdf_extractor = PDFLeafletExtractor()

    async def fetch_all_leaflets(self) -> List[PromoItem]:
        """Fetch all promotional items from available digital brochures and aggregators."""
        all_items: List[PromoItem] = []

        # 1. Publitas interactive flyers
        tasks = []
        for store_id, extractor in self.publitas_extractors.items():
            tasks.append(self._fetch_publitas_safe(extractor))

        publitas_results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in publitas_results:
            if isinstance(res, list):
                all_items.extend(res)

        # 2. Tiendeo aggregator deals
        tiendeo_stores = list(self.publitas_extractors.keys()) + ["action", "delhaize", "lidl", "spar", "cora", "intermarche", "bioplanet"]
        tiendeo_tasks = [
            self._fetch_tiendeo_safe(store_id)
            for store_id in set(tiendeo_stores)
        ]
        tiendeo_results = await asyncio.gather(*tiendeo_tasks, return_exceptions=True)
        for res in tiendeo_results:
            if isinstance(res, list):
                all_items.extend(res)

        logger.info(f"LeafletOrchestrator discovered {len(all_items)} deals from brochures.")
        return all_items

    async def _fetch_publitas_safe(self, extractor: PublitasLeafletExtractor) -> List[PromoItem]:
        try:
            pubs = await extractor.get_active_publications()
            items = []
            for pub in pubs[:3]:
                slug = pub.get("slug") or str(pub.get("id") or "")
                if slug:
                    extracted = await extractor.extract_from_publication_slug(slug)
                    items.extend(extracted)
            return items
        except Exception as err:
            logger.debug(f"Publitas fetch failed for {extractor.store_id}: {err}")
            return []

    async def _fetch_tiendeo_safe(self, store_id: str) -> List[PromoItem]:
        try:
            return await self.tiendeo.fetch_retailer_deals(store_id)
        except Exception as err:
            logger.debug(f"Tiendeo fetch failed for {store_id}: {err}")
            return []

    async def ingest_and_save_leaflets(self) -> int:
        """Extract and persist brochure deals with fingerprint deduplication."""
        items = await self.fetch_all_leaflets()
        if not items:
            return 0
        dicts = [item.to_dict() for item in items]
        saved = await Repository.save_promos_bulk(dicts)
        new_count = sum(1 for _, is_new in saved if is_new)
        logger.info(f"Ingested {len(items)} brochure deals ({new_count} new).")
        return new_count
