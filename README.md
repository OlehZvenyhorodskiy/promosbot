# Belgium Promo's Telegram Bot (@belgiumpromos_bot)

An automated promotions and discount tracker for Belgian supermarkets built with Python, aiogram 3, and aiohttp.

## Features

- **10 Major Belgian Supermarkets**: Colruyt, Carrefour, Delhaize, Aldi, Lidl, Albert Heijn, Jumbo, Spar, Cora, and Intermarché.
- **10 Product Categories**: Fruits & Vegetables, Dairy & Cheese, Meat & Fish, Bakery, Drinks, Snacks & Sweets, Pantry, Household, Care & Baby, Bio / Organic.
- **Multilingual Support**: English, Ukrainian, Dutch, and French. (Russian is excluded per specification).
- **Personalized Filters**: Interactive inline checkmarks (`[✅ / ⬜]`) to toggle stores and categories individually or in bulk.
- **Flexible Alerts**: Choose between Instant Alerts (live upon discovery) and a Daily Morning Digest (configurable hour), or silent mode.
- **Multi-Source Ingestion**:
  - Live scrapers (including Aldi Belgium Algolia state extraction with 200+ active items).
  - Inbound newsletter webhook (`/api/v1/inbound-newsletter`) for parsing forwarded store emails.
  - Realistic built-in Belgian promo seed engine.
- **Interactive UI**:
  - Browse deals with photo cards, strikethrough price comparisons, and store links.
  - In-chat keyword search (type product names like "kaas", "beer", "pain", "melk").
  - Bookmark favorite discounts for quick access.
  - Test command (`/test_promo`) for immediate verification.
- **Google Cloud Ready**: Includes Dockerfile, docker-compose, aiohttp health check server, and keep-alive ping loop for zero-sleep deployment on free tiers.

---

## Getting Started

### Prerequisites
- Python 3.12+ (tested with Python 3.14)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Installation
```bash
git clone <repository_url>
cd "Promos tg bot"

# Install dependencies
python -m venv .venv
.venv\Scripts\activate  # On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt # or: uv pip install -e .
```

### Running Locally
```bash
python -m src.main
```

The bot will start long-polling Telegram while simultaneously running a web server on `http://localhost:8080`.

---

## Bot Commands

- `/start`: Open main menu and select language.
- `/promos`: Browse current promotions matching your store and category filters.
- `/search`: Search active discounts by product name.
- `/stores`: Toggle tracking for individual Belgian supermarkets.
- `/categories`: Filter deals by grocery categories.
- `/favorites`: View your bookmarked discounts.
- `/settings`: Change language or notification delivery mode.
- `/test_promo`: Instantly push a sample promotion card to verify layout and alerts.
- `/help`: Detailed user guide and instructions.

---

## API Endpoints

- `GET /health`: Health status endpoint.
- `GET /ping`: Keep-alive ping endpoint.
- `POST /api/v1/inbound-promo`: Ingest single promo object via JSON.
- `POST /api/v1/inbound-newsletter`: Ingest raw HTML newsletter for automatic deal extraction.

---

## Deployment

Refer to [DEPLOYMENT.md](DEPLOYMENT.md) for Google Cloud Run and Google Compute Engine deployment instructions.

## Project maintenance

- [GitHub workflow](docs/GITHUB_WORKFLOW.md) — branches, reviews, secrets, and deployment boundaries.
- [AI scraper analysis prompt](docs/AI_SCRAPER_ANALYSIS_PROMPT.md) — evidence-based audit blueprint for expanding retailer and brochure coverage.

Never commit `.env`, bot tokens, database files, browser caches, or production exports. Use `.env.example` for local configuration shape and a managed secret for production.
