from typing import Optional, List, Dict, Any, Set, Tuple
import hashlib
from src.db.database import get_db_connection
from src.core.constants import SUPERMARKETS, CATEGORIES, DEFAULT_LANGUAGE
from src.services.search_service import expand_search_terms
from src.scrapers.base import generate_fingerprint


def _fts_phrase(term: str) -> str:
    """Build an FTS5 phrase query for a single search term.

    Terms are wrapped in double quotes so spaces, apostrophes and hyphens are
    treated literally. A double quote inside a term is escaped by doubling it,
    per the FTS5 phrase syntax.
    """
    escaped = term.replace('"', '""')
    # Short terms and terms containing non-letter characters (spaces,
    # apostrophes, hyphens, digits) use a phrase-prefix query so they keep
    # matching substrings that the previous LIKE search found (e.g. "cote d'or",
    # "lay's", "3e"). Plain words rely on token + porter stemming matching.
    if len(term) <= 3 or not term.isalpha():
        return f'"{escaped}"*'
    return f'"{escaped}"'


def _fts_match_expression(terms: List[str]) -> str:
    """Combine expanded search terms into one FTS5 MATCH expression."""
    return " OR ".join(_fts_phrase(term) for term in terms)


PROMO_UPSERT_SQL = """
INSERT INTO promos (
    id, store_id, external_id, fingerprint, title, description, original_price, promo_price,
    discount_text, unit_info, image_url, deal_url, category_id, valid_from, valid_until,
    source_type, leaflet_id, page_number, loyalty_card, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(id) DO UPDATE SET
    fingerprint = COALESCE(excluded.fingerprint, promos.fingerprint),
    title = excluded.title,
    description = excluded.description,
    original_price = excluded.original_price,
    promo_price = excluded.promo_price,
    discount_text = excluded.discount_text,
    unit_info = excluded.unit_info,
    image_url = excluded.image_url,
    deal_url = excluded.deal_url,
    category_id = excluded.category_id,
    valid_from = excluded.valid_from,
    valid_until = excluded.valid_until,
    source_type = COALESCE(excluded.source_type, promos.source_type),
    leaflet_id = COALESCE(excluded.leaflet_id, promos.leaflet_id),
    page_number = COALESCE(excluded.page_number, promos.page_number),
    loyalty_card = COALESCE(excluded.loyalty_card, promos.loyalty_card),
    updated_at = CURRENT_TIMESTAMP
"""

class Repository:
    @staticmethod
    async def get_or_create_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> Dict[str, Any]:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            # Insert new user
            await conn.execute(
                "INSERT INTO users (user_id, username, first_name, language, language_selected, notif_mode, digest_hour) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, first_name, DEFAULT_LANGUAGE, 0, "off", 8),
            )
            for store_id in SUPERMARKETS.keys():
                await conn.execute(
                    "INSERT OR IGNORE INTO user_store_filters (user_id, store_id, enabled) VALUES (?, ?, 1)",
                    (user_id, store_id),
                )
            for cat_id in CATEGORIES.keys():
                await conn.execute(
                    "INSERT OR IGNORE INTO user_category_filters (user_id, category_id, enabled) VALUES (?, ?, 1)",
                    (user_id, cat_id),
                )
            await conn.commit()

            async with conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {}

    @staticmethod
    async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def update_user_language(user_id: int, language: str) -> None:
        async with get_db_connection() as conn:
            await conn.execute(
                "UPDATE users SET language = ?, language_selected = 1 WHERE user_id = ?",
                (language, user_id),
            )
            await conn.commit()

    @staticmethod
    async def update_user_notif_mode(user_id: int, notif_mode: str, digest_hour: Optional[int] = None) -> None:
        async with get_db_connection() as conn:
            if digest_hour is not None:
                await conn.execute(
                    "UPDATE users SET notif_mode = ?, digest_hour = ? WHERE user_id = ?",
                    (notif_mode, digest_hour, user_id),
                )
            else:
                await conn.execute(
                    "UPDATE users SET notif_mode = ? WHERE user_id = ?",
                    (notif_mode, user_id),
                )
            await conn.commit()

    @staticmethod
    async def get_user_store_filters(user_id: int) -> Set[str]:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT store_id FROM user_store_filters WHERE user_id = ? AND enabled = 1",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return {r["store_id"] for r in rows}

    @staticmethod
    async def toggle_user_store_filter(user_id: int, store_id: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT enabled FROM user_store_filters WHERE user_id = ? AND store_id = ?",
                (user_id, store_id),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    new_val = 0 if row["enabled"] == 1 else 1
                    await conn.execute(
                        "UPDATE user_store_filters SET enabled = ? WHERE user_id = ? AND store_id = ?",
                        (new_val, user_id, store_id),
                    )
                else:
                    new_val = 0
                    await conn.execute(
                        "INSERT INTO user_store_filters (user_id, store_id, enabled) VALUES (?, ?, ?)",
                        (user_id, store_id, new_val),
                    )
            await conn.commit()
            return new_val == 1

    @staticmethod
    async def set_all_user_stores(user_id: int, enabled: bool) -> None:
        val = 1 if enabled else 0
        async with get_db_connection() as conn:
            for store_id in SUPERMARKETS.keys():
                await conn.execute(
                    """INSERT INTO user_store_filters (user_id, store_id, enabled) 
                       VALUES (?, ?, ?) 
                       ON CONFLICT(user_id, store_id) DO UPDATE SET enabled = excluded.enabled""",
                    (user_id, store_id, val),
                )
            await conn.commit()

    @staticmethod
    async def get_user_category_filters(user_id: int) -> Set[str]:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT category_id FROM user_category_filters WHERE user_id = ? AND enabled = 1",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return {r["category_id"] for r in rows}

    @staticmethod
    async def toggle_user_category_filter(user_id: int, category_id: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT enabled FROM user_category_filters WHERE user_id = ? AND category_id = ?",
                (user_id, category_id),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    new_val = 0 if row["enabled"] == 1 else 1
                    await conn.execute(
                        "UPDATE user_category_filters SET enabled = ? WHERE user_id = ? AND category_id = ?",
                        (new_val, user_id, category_id),
                    )
                else:
                    new_val = 0
                    await conn.execute(
                        "INSERT INTO user_category_filters (user_id, category_id, enabled) VALUES (?, ?, ?)",
                        (user_id, category_id, new_val),
                    )
            await conn.commit()
            return new_val == 1

    @staticmethod
    async def set_all_user_categories(user_id: int, enabled: bool) -> None:
        val = 1 if enabled else 0
        async with get_db_connection() as conn:
            for cat_id in CATEGORIES.keys():
                await conn.execute(
                    """INSERT INTO user_category_filters (user_id, category_id, enabled) 
                       VALUES (?, ?, ?) 
                       ON CONFLICT(user_id, category_id) DO UPDATE SET enabled = excluded.enabled""",
                    (user_id, cat_id, val),
                )
            await conn.commit()

    @staticmethod
    def generate_promo_id(store_id: str, title: str, external_id: Optional[str] = None) -> str:
        key = f"{store_id}:{external_id or title.strip().lower()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    @classmethod
    async def save_promo(cls, promo_data: Dict[str, Any]) -> Tuple[str, bool]:
        store_id = promo_data.get("store_id", "generic")
        title = promo_data.get("title", "")
        ext_id = promo_data.get("external_id")
        fingerprint = promo_data.get("fingerprint") or generate_fingerprint(
            store_id,
            title,
            promo_data.get("promo_price"),
            promo_data.get("valid_from"),
            promo_data.get("valid_until"),
        )
        promo_data["fingerprint"] = fingerprint

        async with get_db_connection() as conn:
            # Check if deal already exists by fingerprint first, then by id
            existing_id = None
            if fingerprint:
                async with conn.execute(
                    "SELECT id FROM promos WHERE fingerprint = ?", (fingerprint,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        existing_id = row["id"]

            if not existing_id:
                candidate_id = promo_data.get("id") or cls.generate_promo_id(store_id, title, ext_id)
                async with conn.execute("SELECT id FROM promos WHERE id = ?", (candidate_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        existing_id = row["id"]

            is_new = existing_id is None
            promo_id = existing_id or promo_data.get("id") or cls.generate_promo_id(store_id, title, fingerprint)

            await conn.execute(
                PROMO_UPSERT_SQL,
                (
                    promo_id,
                    store_id,
                    ext_id,
                    fingerprint,
                    title,
                    promo_data.get("description", ""),
                    promo_data.get("original_price"),
                    promo_data.get("promo_price"),
                    promo_data.get("discount_text", ""),
                    promo_data.get("unit_info", ""),
                    promo_data.get("image_url", ""),
                    promo_data.get("deal_url", ""),
                    promo_data.get("category_id", "pantry"),
                    promo_data.get("valid_from", ""),
                    promo_data.get("valid_until", ""),
                    promo_data.get("source_type", "web"),
                    promo_data.get("leaflet_id"),
                    promo_data.get("page_number"),
                    promo_data.get("loyalty_card"),
                ),
            )
            await conn.commit()
            return promo_id, is_new

    @classmethod
    async def save_promos_bulk(cls, promos: List[Dict[str, Any]]) -> List[Tuple[str, bool]]:
        """Upsert one scraper response in a single transaction with fingerprint deduplication."""
        if not promos:
            return []

        prepared_meta = []
        for promo_data in promos:
            store_id = promo_data.get("store_id", "generic")
            title = promo_data.get("title", "")
            ext_id = promo_data.get("external_id")
            fingerprint = promo_data.get("fingerprint") or generate_fingerprint(
                store_id,
                title,
                promo_data.get("promo_price"),
                promo_data.get("valid_from"),
                promo_data.get("valid_until"),
            )
            promo_data["fingerprint"] = fingerprint
            prepared_meta.append({
                "store_id": store_id,
                "title": title,
                "ext_id": ext_id,
                "fingerprint": fingerprint,
                "data": promo_data,
            })

        async with get_db_connection() as conn:
            # Query existing promos by fingerprints
            fps = [m["fingerprint"] for m in prepared_meta if m["fingerprint"]]
            fp_to_id = {}
            if fps:
                fp_placeholders = ",".join("?" for _ in fps)
                async with conn.execute(
                    f"SELECT id, fingerprint FROM promos WHERE fingerprint IN ({fp_placeholders})",
                    fps,
                ) as cursor:
                    for row in await cursor.fetchall():
                        fp_to_id[row["fingerprint"]] = row["id"]

            upsert_rows = []
            results = []
            for meta in prepared_meta:
                fp = meta["fingerprint"]
                data = meta["data"]
                existing_id = fp_to_id.get(fp)
                is_new = existing_id is None
                promo_id = existing_id or data.get("id") or cls.generate_promo_id(meta["store_id"], meta["title"], fp)
                results.append((promo_id, is_new))
                upsert_rows.append(
                    (
                        promo_id,
                        meta["store_id"],
                        meta["ext_id"],
                        fp,
                        meta["title"],
                        data.get("description", ""),
                        data.get("original_price"),
                        data.get("promo_price"),
                        data.get("discount_text", ""),
                        data.get("unit_info", ""),
                        data.get("image_url", ""),
                        data.get("deal_url", ""),
                        data.get("category_id", "pantry"),
                        data.get("valid_from", ""),
                        data.get("valid_until", ""),
                        data.get("source_type", "web"),
                        data.get("leaflet_id"),
                        data.get("page_number"),
                        data.get("loyalty_card"),
                    )
                )

            await conn.executemany(PROMO_UPSERT_SQL, upsert_rows)
            await conn.commit()
            return results

    @staticmethod
    async def get_promos(
        store_ids: Optional[List[str]] = None,
        category_ids: Optional[List[str]] = None,
        search_query: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            query = "SELECT * FROM promos WHERE 1=1"
            params: List[Any] = []

            if store_ids:
                placeholders = ",".join("?" for _ in store_ids)
                query += f" AND store_id IN ({placeholders})"
                params.extend(store_ids)

            if category_ids:
                placeholders = ",".join("?" for _ in category_ids)
                query += f" AND category_id IN ({placeholders})"
                params.extend(category_ids)

            if search_query:
                # Multilingual search term expansion
                terms = [t for t in expand_search_terms(search_query) if t.strip()]
                if terms:
                    query += (
                        " AND rowid IN ("
                        "SELECT rowid FROM promos_fts WHERE promos_fts MATCH ?"
                        ")"
                    )
                    params.append(_fts_match_expression(terms))

            query += " ORDER BY updated_at DESC, created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    @staticmethod
    async def count_promos(
        store_ids: Optional[List[str]] = None,
        category_ids: Optional[List[str]] = None,
        search_query: Optional[str] = None,
    ) -> int:
        async with get_db_connection() as conn:
            query = "SELECT COUNT(*) as cnt FROM promos WHERE 1=1"
            params: List[Any] = []

            if store_ids:
                placeholders = ",".join("?" for _ in store_ids)
                query += f" AND store_id IN ({placeholders})"
                params.extend(store_ids)

            if category_ids:
                placeholders = ",".join("?" for _ in category_ids)
                query += f" AND category_id IN ({placeholders})"
                params.extend(category_ids)

            if search_query:
                terms = [t for t in expand_search_terms(search_query) if t.strip()]
                if terms:
                    query += (
                        " AND rowid IN ("
                        "SELECT rowid FROM promos_fts WHERE promos_fts MATCH ?"
                        ")"
                    )
                    params.append(_fts_match_expression(terms))

            async with conn.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return row["cnt"] if row else 0

    @staticmethod
    async def cleanup_invalid_promos() -> int:
        """Remove navigation/placeholder cards accidentally parsed as promos."""
        async with get_db_connection() as conn:
            cursor = await conn.execute(
                """
                DELETE FROM promos
                WHERE lower(trim(title)) IN (
                    'mydelhaize', 'delhaize', 'promoties', 'promotions',
                    'filteren', 'filters', 'aanmelden', 'inloggen'
                )
                OR (
                    COALESCE(promo_price, 0) <= 0
                    AND COALESCE(original_price, 0) <= 0
                    AND lower(trim(COALESCE(discount_text, ''))) IN
                        ('', 'promo', 'actie', 'promotie', 'promotion', 'discount')
                )
                """
            )
            await conn.commit()
            return cursor.rowcount

    @staticmethod
    async def get_promo_counts_by_store() -> Dict[str, int]:
        async with get_db_connection() as conn:
            counts = {s_id: 0 for s_id in SUPERMARKETS.keys()}
            async with conn.execute("SELECT store_id, COUNT(*) as cnt FROM promos GROUP BY store_id") as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    counts[r["store_id"]] = r["cnt"]
            return counts

    @staticmethod
    async def get_promo_counts_by_category(store_id: Optional[str] = None) -> Dict[str, int]:
        async with get_db_connection() as conn:
            counts = {c_id: 0 for c_id in CATEGORIES.keys()}
            if store_id:
                q = "SELECT category_id, COUNT(*) as cnt FROM promos WHERE store_id = ? GROUP BY category_id"
                p = (store_id,)
            else:
                q = "SELECT category_id, COUNT(*) as cnt FROM promos GROUP BY category_id"
                p = ()
            async with conn.execute(q, p) as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    if r["category_id"] in counts:
                        counts[r["category_id"]] = r["cnt"]
            return counts

    @staticmethod
    async def get_promo_by_id(promo_id: str) -> Optional[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT * FROM promos WHERE id = ?", (promo_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def toggle_favorite(user_id: int, promo_id: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT 1 FROM user_favorites WHERE user_id = ? AND promo_id = ?",
                (user_id, promo_id),
            ) as cursor:
                exists = await cursor.fetchone()

            if exists:
                await conn.execute(
                    "DELETE FROM user_favorites WHERE user_id = ? AND promo_id = ?",
                    (user_id, promo_id),
                )
                await conn.commit()
                return False
            else:
                await conn.execute(
                    "INSERT INTO user_favorites (user_id, promo_id) VALUES (?, ?)",
                    (user_id, promo_id),
                )
                await conn.commit()
                return True

    @staticmethod
    async def is_favorite(user_id: int, promo_id: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT 1 FROM user_favorites WHERE user_id = ? AND promo_id = ?",
                (user_id, promo_id),
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None

    @staticmethod
    async def get_user_favorites(user_id: int) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.execute(
                """SELECT p.* FROM promos p
                   INNER JOIN user_favorites f ON p.id = f.promo_id
                   WHERE f.user_id = ?
                   ORDER BY f.saved_at DESC""",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    @staticmethod
    async def toggle_cart(user_id: int, promo_id: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT 1 FROM user_cart WHERE user_id = ? AND promo_id = ?",
                (user_id, promo_id),
            ) as cursor:
                exists = await cursor.fetchone()

            if exists:
                await conn.execute(
                    "DELETE FROM user_cart WHERE user_id = ? AND promo_id = ?",
                    (user_id, promo_id),
                )
                await conn.commit()
                return False
            else:
                await conn.execute(
                    "INSERT INTO user_cart (user_id, promo_id) VALUES (?, ?)",
                    (user_id, promo_id),
                )
                await conn.commit()
                return True

    @staticmethod
    async def is_in_cart(user_id: int, promo_id: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT 1 FROM user_cart WHERE user_id = ? AND promo_id = ?",
                (user_id, promo_id),
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None

    @staticmethod
    async def get_user_cart(user_id: int) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.execute(
                """SELECT p.* FROM promos p
                   INNER JOIN user_cart c ON p.id = c.promo_id
                   WHERE c.user_id = ?
                   ORDER BY c.added_at DESC""",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    @staticmethod
    async def clear_user_cart(user_id: int) -> int:
        async with get_db_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM user_cart WHERE user_id = ?",
                (user_id,),
            )
            await conn.commit()
            return cursor.rowcount

    @staticmethod
    async def get_cart_totals(user_id: int) -> Dict[str, float]:
        cart_items = await Repository.get_user_cart(user_id)
        total_promo = 0.0
        total_regular = 0.0
        for item in cart_items:
            promo_p = item.get("promo_price") or item.get("original_price") or 0.0
            orig_p = item.get("original_price") or promo_p
            total_promo += promo_p
            total_regular += orig_p
        savings = max(0.0, total_regular - total_promo)
        percent = round((savings / total_regular * 100), 1) if total_regular > 0 else 0.0
        return {
            "total_promo": round(total_promo, 2),
            "total_regular": round(total_regular, 2),
            "savings": round(savings, 2),
            "saving_percent": percent,
            "count": len(cart_items),
        }

    @staticmethod
    async def get_users_for_instant_alert(store_id: str, category_id: str) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.execute(
                """SELECT u.* FROM users u
                   INNER JOIN user_store_filters sf ON u.user_id = sf.user_id AND sf.store_id = ? AND sf.enabled = 1
                   INNER JOIN user_category_filters cf ON u.user_id = cf.user_id AND cf.category_id = ? AND cf.enabled = 1
                   WHERE u.notif_mode = 'instant'""",
                (store_id, category_id),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    @staticmethod
    async def get_users_for_digest(hour: int) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT * FROM users WHERE notif_mode = 'digest' AND digest_hour = ?",
                (hour,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    @staticmethod
    async def get_users_for_alert_batch() -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT * FROM users WHERE notif_mode != 'off'") as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    @staticmethod
    async def create_alert_batch(promos: List[Dict[str, Any]]) -> int:
        async with get_db_connection() as conn:
            cursor = await conn.execute("INSERT INTO alert_batches DEFAULT VALUES")
            batch_id = cursor.lastrowid
            await conn.executemany(
                "INSERT OR IGNORE INTO alert_batch_items (batch_id, promo_id, store_id) VALUES (?, ?, ?)",
                [(batch_id, p["id"], p.get("store_id", "generic")) for p in promos],
            )
            await conn.commit()
            return int(batch_id)

    @staticmethod
    async def get_alert_batch_promos(batch_id: int, store_id: str) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.execute(
                """SELECT p.* FROM promos p
                   INNER JOIN alert_batch_items i ON i.promo_id = p.id
                   WHERE i.batch_id = ? AND i.store_id = ?
                   ORDER BY p.updated_at DESC, p.created_at DESC""",
                (batch_id, store_id),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    @staticmethod
    async def cleanup_alert_batches(keep_days: int = 14) -> None:
        async with get_db_connection() as conn:
            await conn.execute(
                "DELETE FROM alert_batches WHERE created_at < datetime('now', ?)",
                (f"-{keep_days} days",),
            )
            await conn.commit()

    @staticmethod
    async def record_notification_sent(user_id: int, promo_id: str) -> None:
        async with get_db_connection() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO sent_notifications (user_id, promo_id) VALUES (?, ?)",
                (user_id, promo_id),
            )
            await conn.commit()

    @staticmethod
    async def has_notification_been_sent(user_id: int, promo_id: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT 1 FROM sent_notifications WHERE user_id = ? AND promo_id = ?",
                (user_id, promo_id),
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
