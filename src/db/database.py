import os
from pathlib import Path
from contextlib import asynccontextmanager
import aiosqlite
from src.core.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    language_selected INTEGER NOT NULL DEFAULT 0,
    notif_mode TEXT NOT NULL DEFAULT 'off',
    digest_hour INTEGER NOT NULL DEFAULT 8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_store_filters (
    user_id INTEGER NOT NULL,
    store_id TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, store_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_category_filters (
    user_id INTEGER NOT NULL,
    category_id TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, category_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS promos (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    external_id TEXT,
    fingerprint TEXT,
    title TEXT NOT NULL,
    description TEXT,
    original_price REAL,
    promo_price REAL,
    discount_text TEXT,
    unit_info TEXT,
    image_url TEXT,
    deal_url TEXT,
    category_id TEXT,
    valid_from TEXT,
    valid_until TEXT,
    source_type TEXT DEFAULT 'web',
    leaflet_id TEXT,
    page_number INTEGER,
    loyalty_card TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_promos_store ON promos(store_id);
CREATE INDEX IF NOT EXISTS idx_promos_category ON promos(category_id);
CREATE INDEX IF NOT EXISTS idx_promos_valid ON promos(valid_until);
CREATE INDEX IF NOT EXISTS idx_promos_source ON promos(source_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_promos_fingerprint ON promos(fingerprint);

CREATE TABLE IF NOT EXISTS user_favorites (
    user_id INTEGER NOT NULL,
    promo_id TEXT NOT NULL,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, promo_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (promo_id) REFERENCES promos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sent_notifications (
    user_id INTEGER NOT NULL,
    promo_id TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, promo_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alert_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_batch_items (
    batch_id INTEGER NOT NULL,
    promo_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    PRIMARY KEY (batch_id, promo_id),
    FOREIGN KEY (batch_id) REFERENCES alert_batches(id) ON DELETE CASCADE,
    FOREIGN KEY (promo_id) REFERENCES promos(id) ON DELETE CASCADE
);
"""

@asynccontextmanager
async def get_db_connection():
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(db_path), timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA synchronous = NORMAL")
        await conn.execute("PRAGMA busy_timeout = 30000")
        yield conn

async def init_db():
    async with get_db_connection() as conn:
        await conn.executescript(SCHEMA_SQL)
        # Existing deployments predate the first-launch language picker. An
        # added column defaults to selected for existing users; only users
        # created after this schema change must choose a language.
        async with conn.execute("PRAGMA table_info(users)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        if "language_selected" not in columns:
            await conn.execute(
                "ALTER TABLE users ADD COLUMN language_selected INTEGER NOT NULL DEFAULT 1"
            )

        # Migration: Ensure promos table has the fingerprint and leaflet columns
        async with conn.execute("PRAGMA table_info(promos)") as cursor:
            promo_columns = {row[1] for row in await cursor.fetchall()}
        if "fingerprint" not in promo_columns:
            await conn.execute("ALTER TABLE promos ADD COLUMN fingerprint TEXT")
        if "source_type" not in promo_columns:
            await conn.execute("ALTER TABLE promos ADD COLUMN source_type TEXT DEFAULT 'web'")
        if "leaflet_id" not in promo_columns:
            await conn.execute("ALTER TABLE promos ADD COLUMN leaflet_id TEXT")
        if "page_number" not in promo_columns:
            await conn.execute("ALTER TABLE promos ADD COLUMN page_number INTEGER")
        if "loyalty_card" not in promo_columns:
            await conn.execute("ALTER TABLE promos ADD COLUMN loyalty_card TEXT")
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_promos_fingerprint ON promos(fingerprint)"
        )

        await conn.commit()
