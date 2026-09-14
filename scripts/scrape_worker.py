"""Standalone scraping worker for Cloud Run Jobs, cron tasks, and CLI triggers."""

import argparse
import asyncio
import logging
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.db.database import init_db
from src.scrapers.engine import ScraperEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scrape_worker")


async def main():
    parser = argparse.ArgumentParser(description="Belgium Promos Scraping Worker")
    parser.add_argument("--store", type=str, default=None, help="Target store ID to scrape (default: all)")
    parser.add_argument("--leaflets-only", action="store_true", help="Only run digital brochure/leaflet engine")
    args = parser.parse_args()

    logger.info("Initializing database connection...")
    await init_db()

    engine = ScraperEngine()
    start_time = time.time()

    if args.leaflets_only:
        logger.info("Running leaflet/brochure scrapers only...")
        count = await engine.run_leaflet_scrapers()
    elif args.store:
        logger.info(f"Running scraper for store: {args.store}...")
        count = await engine.run_store_scraper(args.store)
    else:
        logger.info("Running all supermarket and leaflet scrapers...")
        count = await engine.run_all_scrapers()

    elapsed = time.time() - start_time
    logger.info(f"Scraping run completed in {elapsed:.2f}s. New deals ingested: {count}")

    # Log health of all scrapers
    health = engine.get_health_status()
    for h in health:
        cb = h["circuit_breaker_state"]
        logger.info(f"Store {h['name']} ({h['store_id']}): CB={cb}, Failures={h['failure_count']}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
