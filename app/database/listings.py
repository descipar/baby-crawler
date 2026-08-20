"""Listing-Operationen (CRUD, Filtern, Sortieren, Notify)."""

import re
import sqlite3
from typing import Any, Dict, List, Optional

from .core import _db, utcnow

# Preisausdruck für SQL-Sortierung (deutsches Format: `.` = Tausender, `,` = Dezimal)
_PRICE_EXPR = (
    "CASE WHEN price GLOB '*[0-9]*' "
    "THEN CAST(REPLACE(REPLACE(REPLACE(price,' €',''),'.',''),',','.') AS REAL) "
    "ELSE NULL END"
)

_SORT_MAP: Dict[str, str] = {
    "date_desc":    "is_free DESC, found_at DESC",
    "date_asc":     "found_at ASC",
    "price_asc":    f"({_PRICE_EXPR} IS NULL), {_PRICE_EXPR} ASC",
    "price_desc":   f"({_PRICE_EXPR} IS NULL), {_PRICE_EXPR} DESC",
    "distance_asc": "(distance_km IS NULL), distance_km ASC",
}


def is_dismissed(listing_id: str) -> bool:
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM dismissed_listings WHERE listing_id=?", (listing_id,)
        ).fetchone()
    return row is not None


def is_known_listing(listing_id: str) -> bool:
    """Prüft schnell, ob eine Anzeige gespeichert oder dauerhaft ausgeblendet ist."""
    if not listing_id:
        return False
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM listings WHERE listing_id=? "
            "UNION ALL "
            "SELECT 1 FROM dismissed_listings WHERE listing_id=? "
            "LIMIT 1",
            (listing_id, listing_id),
        ).fetchone()
    return row is not None


def dismiss_listing(db_id: int):
    with _db() as conn:
        row = conn.execute("SELECT listing_id FROM listings WHERE id=?", (db_id,)).fetchone()
        if row:
            conn.execute(
                "INSERT OR IGNORE INTO dismissed_listings(listing_id) VALUES(?)", (row["listing_id"],)
            )
            conn.execute("DELETE FROM listings WHERE id=?", (db_id,))
            conn.commit()


def save_listing(listing: "Listing") -> bool:
    """Gibt True zurück wenn die Anzeige neu gespeichert wurde.

    A2-Fix: dismissed-Check, INSERT und Duplikat-Erkennung laufen in einer
    einzigen DB-Verbindung/Transaktion, sodass kein konkurrierender Thread
    dazwischenfunken kann.
    """
    try:
        with _db() as conn:
            if conn.execute(
                "SELECT 1 FROM dismissed_listings WHERE listing_id=?",
                (listing.listing_id,),
            ).fetchone():
                return False

            conn.execute(
                """INSERT INTO listings
                   (listing_id,platform,title,price,location,url,image_url,image_url_large,
                    description,search_term,is_free)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (listing.listing_id, listing.platform, listing.title, listing.price,
                 listing.location, listing.url, listing.image_url,
                 getattr(listing, "image_url_large", ""),
                 listing.description, listing.search_term,
                 int(getattr(listing, "is_free", False))),
            )

            # Duplikat-Erkennung direkt im selben Statement / Connection
            normalized = listing.title.lower().strip()[:50] if listing.title else ""
            dup_platform = None
            if len(normalized) >= 5:
                dup_row = conn.execute(
                    "SELECT platform FROM listings "
                    "WHERE platform != ? "
                    "AND found_at >= datetime('now', '-30 days') "
                    "AND LOWER(SUBSTR(title,1,50)) = ? "
                    "LIMIT 1",
                    (listing.platform, normalized),
                ).fetchone()
                if dup_row:
                    dup_platform = dup_row["platform"]

            if dup_platform:
                conn.execute(
                    "UPDATE listings SET potential_duplicate=? WHERE listing_id=?",
                    (dup_platform, listing.listing_id),
                )

            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def update_listing_distance(listing_id: str, distance_km: float):
    with _db() as conn:
        conn.execute(
            "UPDATE listings SET distance_km=? WHERE listing_id=?",
            (round(distance_km, 1), listing_id),
        )
        conn.commit()


def toggle_favorite(listing_id: int):
    with _db() as conn:
        conn.execute(
            "UPDATE listings SET is_favorite = CASE WHEN is_favorite=1 THEN 0 ELSE 1 END WHERE id=?",
            (listing_id,),
        )
        conn.commit()


def update_listing_note(db_id: int, note: str):
    with _db() as conn:
        conn.execute("UPDATE listings SET notes=? WHERE id=?", (note.strip() or None, db_id))
        conn.commit()


def find_duplicate_platform(title: str, platform: str) -> Optional[str]:
    normalized = title.lower().strip()[:50] if title else ""
    if len(normalized) < 5:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT platform FROM listings "
            "WHERE platform != ? "
            "AND found_at >= datetime('now', '-30 days') "
            "AND LOWER(SUBSTR(title,1,50)) = ? "
            "LIMIT 1",
            (platform, normalized),
        ).fetchone()
    return row["platform"] if row else None


def get_distinct_platforms() -> List[str]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT platform FROM listings ORDER BY platform"
        ).fetchall()
    return [r["platform"] for r in rows if r["platform"]]


def get_platform_counts() -> Dict[str, int]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT platform, COUNT(*) as count FROM listings GROUP BY platform"
        ).fetchall()
    return {r["platform"]: r["count"] for r in rows if r["platform"]}


def get_listings(limit: int = 100, offset: int = 0,
                 search_terms: Optional[List[str]] = None,
                 platform: Optional[str] = None, only_favorites: bool = False,
                 only_free: bool = False, max_age_hours: int = 0,
                 platform_max_ages: Optional[Dict[str, int]] = None,
                 max_distance_km: Optional[float] = None,
                 sort_by: str = "date_desc", exclude_text: Optional[str] = None,
                 since_datetime: Optional[str] = None) -> List[Dict]:
    conditions: List[str] = []
    params: List[Any] = []

    if search_terms:
        if len(search_terms) == 1:
            conditions.append("search_term = ?")
            params.append(search_terms[0])
        else:
            placeholders = ",".join("?" * len(search_terms))
            conditions.append(f"search_term IN ({placeholders})")
            params.extend(search_terms)
    if platform:
        conditions.append("platform = ?")
        params.append(platform)
    if only_favorites:
        conditions.append("is_favorite = 1")
    if only_free:
        conditions.append("is_free = 1")
    if max_age_hours and max_age_hours > 0:
        conditions.append("found_at >= datetime('now', ? || ' hours')")
        params.append(f"-{max_age_hours}")
    elif platform_max_ages:
        exclusions = [(p, h) for p, h in platform_max_ages.items() if h and h > 0]
        if exclusions:
            parts = ["(platform = ? AND found_at < datetime('now', ? || ' hours'))"] * len(exclusions)
            conditions.append("NOT (" + " OR ".join(parts) + ")")
            for p, h in exclusions:
                params.extend([p, f"-{h}"])
    if max_distance_km is not None:
        conditions.append("(distance_km IS NULL OR distance_km <= ?)")
        params.append(max_distance_km)
    if exclude_text:
        like = f"%{exclude_text}%"
        conditions.append("title NOT LIKE ? AND COALESCE(description,'') NOT LIKE ?")
        params.extend([like, like])
    if since_datetime:
        conditions.append("found_at > ?")
        params.append(since_datetime)

    order = _SORT_MAP.get(sort_by, _SORT_MAP["date_desc"])
    query = "SELECT * FROM listings"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" ORDER BY is_favorite DESC, {order} LIMIT ? OFFSET ?"
    params.append(limit)
    params.append(offset)

    with _db() as conn:
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    return rows


def get_listing_count() -> int:
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]


def get_listing_by_id(db_id: int) -> Optional[Dict]:
    with _db() as conn:
        row = conn.execute("SELECT * FROM listings WHERE id=?", (db_id,)).fetchone()
    return dict(row) if row else None


def get_listings_today() -> List[Dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE found_at >= date('now') ORDER BY found_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_unnotified_listings() -> List[Dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE notified_at IS NULL "
            "ORDER BY platform, search_term, found_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def claim_unnotified_listings() -> List[Dict]:
    """Holt und markiert unbenachrichtigte Anzeigen atomar in einer Transaktion.

    B5-Fix: Verhindert doppelten Versand bei gleichzeitigem Aufruf, da SELECT
    und UPDATE in einer einzigen Verbindung/Transaktion erfolgen.
    """
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE notified_at IS NULL "
            "ORDER BY platform, search_term, found_at DESC"
        ).fetchall()
        if not rows:
            return []
        ids = [r["listing_id"] for r in rows]
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            placeholders = ",".join("?" * len(chunk))
            conn.execute(
                f"UPDATE listings SET notified_at=datetime('now') "
                f"WHERE listing_id IN ({placeholders}) AND notified_at IS NULL",
                chunk,
            )
        conn.commit()
    return [dict(r) for r in rows]


def mark_listings_notified(listing_ids: List[str]):
    if not listing_ids:
        return
    with _db() as conn:
        for i in range(0, len(listing_ids), 500):
            chunk = listing_ids[i:i + 500]
            placeholders = ",".join("?" * len(chunk))
            conn.execute(
                f"UPDATE listings SET notified_at=datetime('now') WHERE listing_id IN ({placeholders})",
                chunk,
            )
        conn.commit()


def clear_old_listings(days: int = 30):
    with _db() as conn:
        rows = conn.execute(
            "SELECT listing_id FROM listings "
            "WHERE is_favorite = 0 AND found_at < datetime('now', ? || ' days')",
            (f"-{days}",),
        ).fetchall()
        if rows:
            ids = [r["listing_id"] for r in rows]
            conn.executemany(
                "INSERT OR IGNORE INTO dismissed_listings(listing_id) VALUES(?)",
                [(lid,) for lid in ids],
            )
            conn.execute(
                "DELETE FROM listings WHERE is_favorite = 0 AND found_at < datetime('now', ? || ' days')",
                (f"-{days}",),
            )
        conn.commit()


def clear_listings_older_than(hours: int) -> int:
    with _db() as conn:
        rows = conn.execute(
            "SELECT listing_id FROM listings "
            "WHERE is_favorite = 0 AND found_at < datetime('now', ? || ' hours')",
            (f"-{hours}",),
        ).fetchall()
        if not rows:
            return 0
        ids = [r["listing_id"] for r in rows]
        conn.executemany(
            "INSERT OR IGNORE INTO dismissed_listings(listing_id) VALUES(?)",
            [(lid,) for lid in ids],
        )
        conn.execute(
            "DELETE FROM listings WHERE is_favorite = 0 AND found_at < datetime('now', ? || ' hours')",
            (f"-{hours}",),
        )
        conn.commit()
    return len(ids)


def clear_listings_by_platform(platform: str) -> int:
    with _db() as conn:
        rows = conn.execute(
            "SELECT listing_id FROM listings WHERE platform=? AND is_favorite=0",
            (platform,),
        ).fetchall()
        if not rows:
            return 0
        ids = [r["listing_id"] for r in rows]
        conn.executemany(
            "INSERT OR IGNORE INTO dismissed_listings(listing_id) VALUES(?)",
            [(lid,) for lid in ids],
        )
        conn.execute(
            "DELETE FROM listings WHERE platform=? AND is_favorite=0",
            (platform,),
        )
        conn.commit()
    return len(ids)


def clear_all_listings():
    with _db() as conn:
        conn.execute("DELETE FROM listings WHERE is_favorite = 0")
        conn.execute("DELETE FROM geocache")
        conn.commit()


def get_all_listing_urls(min_age_minutes: int = 0,
                         recheck_hours: int = 0) -> List[Dict]:
    conditions = []
    params: List[Any] = []
    if min_age_minutes > 0:
        conditions.append("found_at <= datetime('now', ? || ' minutes')")
        params.append(f"-{min_age_minutes}")
    if recheck_hours > 0:
        conditions.append(
            "(availability_checked_at IS NULL "
            "OR availability_checked_at < datetime('now', ? || ' hours'))"
        )
        params.append(f"-{recheck_hours}")
    query = "SELECT listing_id, url, title FROM listings"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY COALESCE(availability_checked_at, '1970-01-01') ASC"
    with _db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def mark_listings_availability_checked(listing_ids: List[str]):
    if not listing_ids:
        return
    now = utcnow().isoformat(timespec="seconds")
    with _db() as conn:
        for i in range(0, len(listing_ids), 500):
            chunk = listing_ids[i:i + 500]
            placeholders = ",".join("?" * len(chunk))
            conn.execute(
                f"UPDATE listings SET availability_checked_at = ? WHERE listing_id IN ({placeholders})",
                [now, *chunk],
            )
        conn.commit()


def delete_listing_by_listing_id(listing_id: str):
    with _db() as conn:
        conn.execute("DELETE FROM listings WHERE listing_id = ?", (listing_id,))
        conn.commit()


def cleanup_mismatched_listings() -> int:
    """Löscht Anzeigen, deren Titel+Beschreibung nicht alle Wörter des Suchbegriffs enthalten.

    Gibt die Anzahl gelöschter Anzeigen zurück. Gelöschte Einträge werden in
    dismissed_listings eingetragen, damit sie beim nächsten Crawl nicht erneut
    gespeichert werden.
    """
    def _matches(title: str, desc: str, term: str) -> bool:
        words = (term or "").lower().split()
        if len(words) <= 1:
            return True
        text = f"{title or ''} {desc or ''}".lower()
        return all(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words)

    with _db() as conn:
        rows = conn.execute(
            "SELECT id, listing_id, title, description, search_term FROM listings"
        ).fetchall()
        mismatches = [
            r for r in rows
            if r["search_term"] and not _matches(r["title"] or "", r["description"] or "", r["search_term"])
        ]
        if not mismatches:
            return 0
        listing_ids = [r["listing_id"] for r in mismatches]
        db_ids = [r["id"] for r in mismatches]
        conn.executemany(
            "INSERT OR IGNORE INTO dismissed_listings(listing_id, dismissed_at) VALUES(?, datetime('now'))",
            [(lid,) for lid in listing_ids],
        )
        placeholders = ",".join("?" * len(db_ids))
        conn.execute(f"DELETE FROM listings WHERE id IN ({placeholders})", db_ids)
        conn.commit()
    return len(mismatches)
