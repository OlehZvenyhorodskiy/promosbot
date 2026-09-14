import pytest
import tempfile
from pathlib import Path
from src.core.config import settings
from src.db.database import init_db
from src.db.repository import Repository
from src.scrapers.engine import ScraperEngine
from src.scrapers.newsletter import NewsletterParser

@pytest.mark.asyncio
async def test_seed_and_engine():
    db_file = "data/test_engine.db"
    settings.DB_PATH = db_file
    try:
        await init_db()
        engine = ScraperEngine()
        seeded = await engine.seed_data_if_empty()
        assert seeded >= 10

        promos = await Repository.get_promos(limit=50)
        assert len(promos) >= 10

        # Verify Colruyt, Carrefour, Delhaize, Aldi, etc. are present
        stores_present = {p["store_id"] for p in promos}
        assert "colruyt" in stores_present
        assert "carrefour" in stores_present
        assert "delhaize" in stores_present
        assert "aldi" in stores_present
    finally:
        import os
        if os.path.exists(db_file):
            os.remove(db_file)

def test_newsletter_parser():
    sample_html = """
    <html>
      <body>
        <div>Colruyt Laagste Prijzen</div>
        <table>
          <tr>
            <td>
              <h3>Brugge Oud Kaas Sneden</h3>
              <p>2+2 GRATIS op alle sneetjes</p>
              <p>Nu voor € 4,50 (was € 9,00)</p>
              <img src="https://example.com/brugge_kaas.jpg" />
              <a href="https://colruyt.be/deal/brugge">Bekijk deal</a>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    items = NewsletterParser.parse_newsletter_html(sample_html, sender="promo@colruyt.be", subject="Wekelijkse Rode Prijzen")
    assert len(items) >= 1
    item = items[0]
    assert item.store_id == "colruyt"
    assert "Brugge Oud Kaas" in item.title
    assert "2+2 GRATIS" in item.discount_text
    assert item.category_id == "dairy_cheese"
    assert item.promo_price == 4.50
