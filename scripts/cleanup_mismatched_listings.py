"""Prüft bestehende Anzeigen auf zwei Kriterien und löscht optional nicht passende:

  1. AND-Filter: Alle Wörter des Suchbegriffs müssen in Titel + Beschreibung stehen.
  2. Sprachfilter: Anzeigensprache muss in der konfigurierten Erlaubt-Liste sein
     (nur wenn crawler_lang_filter_enabled = 1 in der DB).

Aufruf:
    python scripts/cleanup_mismatched_listings.py           # nur Bericht
    python scripts/cleanup_mismatched_listings.py --delete  # löschen
    DATA_DIR=./data python scripts/cleanup_mismatched_listings.py --delete
"""

import argparse
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "baby_crawler.db"

_LANG_FILTER_DESCRIPTION_MIN_CHARS = 40
_LANG_FILTER_TEXT_MIN_LETTERS = 6
_LANG_FILTER_DESCRIPTION_CONFIDENCE = 0.60
_LANG_FILTER_SHORT_TEXT_CONFIDENCE = 0.85

try:
    from langdetect import DetectorFactory
    DetectorFactory.seed = 0
    _langdetect_available = True
except ImportError:
    _langdetect_available = False


def _matches_all_words(title: str, description: str, term: str) -> bool:
    words = term.lower().split()
    if len(words) <= 1:
        return True
    text = f"{title or ''} {description or ''}".lower()
    return all(bool(re.search(r"\b" + re.escape(w) + r"\b", text)) for w in words)


def _is_lang_allowed(title: str, description: str, allowed_langs: list) -> bool:
    normalized_allowed = {str(lang).strip().lower() for lang in allowed_langs if str(lang).strip()}
    if not normalized_allowed or not _langdetect_available:
        return True
    try:
        from langdetect import detect_langs

        desc = (description or "").strip()
        if len(desc) >= _LANG_FILTER_DESCRIPTION_MIN_CHARS:
            text = desc
            confidence_threshold = _LANG_FILTER_DESCRIPTION_CONFIDENCE
        else:
            text = f"{title or ''} {desc}".strip()
            if sum(char.isalpha() for char in text) < _LANG_FILTER_TEXT_MIN_LETTERS:
                return True
            confidence_threshold = _LANG_FILTER_SHORT_TEXT_CONFIDENCE

        results = detect_langs(text)
        if not results:
            return True
        best = max(results, key=lambda result: result.prob)
        if best.prob < confidence_threshold:
            return True
        return best.lang.lower() in normalized_allowed
    except Exception:
        return True


def _get_setting(conn, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--delete", action="store_true", help="Nicht passende Anzeigen löschen")
    parser.add_argument("--lang", metavar="de,en", help="Sprachfilter erzwingen (überschreibt DB-Einstellung)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Datenbank nicht gefunden: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    if args.lang:
        lang_filter_enabled = True
        allowed_langs = [l.strip() for l in args.lang.split(",") if l.strip()]
    else:
        lang_filter_enabled = _get_setting(conn, "crawler_lang_filter_enabled", "0") == "1"
        allowed_langs = [
            l.strip()
            for l in _get_setting(conn, "crawler_lang_filter_langs", "de").split(",")
            if l.strip()
        ]

    rows = conn.execute(
        "SELECT id, listing_id, title, description, search_term, platform FROM listings"
    ).fetchall()

    total = len(rows)
    word_mismatches = []
    lang_mismatches = []

    for r in rows:
        title = r["title"] or ""
        desc = r["description"] or ""
        term = r["search_term"] or ""

        if term and not _matches_all_words(title, desc, term):
            word_mismatches.append(r)
        elif lang_filter_enabled and not _is_lang_allowed(title, desc, allowed_langs):
            lang_mismatches.append(r)

    bad = len(word_mismatches) + len(lang_mismatches)
    print(f"Gesamt: {total} Anzeigen")
    print(f"  AND-Filter (Suchbegriff-Mismatch): {len(word_mismatches)}")
    if lang_filter_enabled:
        print(f"  Sprachfilter ({', '.join(allowed_langs)}):       {len(lang_mismatches)}")
    else:
        print(f"  Sprachfilter: deaktiviert (crawler_lang_filter_enabled = 0)")
    print(f"  Gesamt zu bereinigen: {bad}")

    if not bad:
        print("\nAlles in Ordnung – keine Anzeigen zu bereinigen.")
        conn.close()
        return

    if word_mismatches:
        print("\n── AND-Filter-Mismatches ──────────────────────────────")
        by_term: dict = defaultdict(list)
        for r in word_mismatches:
            by_term[r["search_term"]].append(r)
        for term, listings in sorted(by_term.items()):
            print(f"  [{term}]  →  {len(listings)} nicht passend")
            for r in listings[:3]:
                print(f"      • [{r['platform']}] {(r['title'] or '')[:70]}")
            if len(listings) > 3:
                print(f"      … und {len(listings) - 3} weitere")

    if lang_mismatches:
        print("\n── Sprachfilter-Mismatches ────────────────────────────")
        by_platform: dict = defaultdict(list)
        for r in lang_mismatches:
            by_platform[r["platform"]].append(r)
        for platform, listings in sorted(by_platform.items()):
            print(f"  [{platform}]  →  {len(listings)} fremdsprachig")
            for r in listings[:3]:
                print(f"      • {(r['title'] or '')[:70]}")
            if len(listings) > 3:
                print(f"      … und {len(listings) - 3} weitere")

    if not args.delete:
        print(f"\nHinweis: Zum Löschen --delete übergeben.")
        conn.close()
        return

    all_bad = word_mismatches + lang_mismatches
    ids = [r["id"] for r in all_bad]
    listing_ids = [r["listing_id"] for r in all_bad]

    conn.execute("BEGIN")
    conn.executemany(
        "INSERT OR IGNORE INTO dismissed_listings (listing_id, dismissed_at) VALUES (?, datetime('now'))",
        [(lid,) for lid in listing_ids],
    )
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM listings WHERE id IN ({placeholders})", ids)
    conn.execute("COMMIT")

    print(f"\n{bad} Anzeigen gelöscht und als dismissed eingetragen.")
    conn.close()


if __name__ == "__main__":
    main()
