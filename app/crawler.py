"""Orchestriert einen Crawl-Durchlauf pro Plattform."""

import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import List

from . import database as db
from .geo import distance_to_home
from .logbuffer import clear as clear_log
from .notifier import notify
from .scrapers import KleinanzeigenScraper, ShpockScraper, FacebookScraper, VintedScraper, EbayScraper, WillhabenScraper, MarktdeScraper
from .scrapers.base import Listing, price_within_limit

logger = logging.getLogger(__name__)

PLATFORM_SCRAPER_MAP = {
    "kleinanzeigen": KleinanzeigenScraper,
    "shpock": ShpockScraper,
    "facebook": FacebookScraper,
    "vinted": VintedScraper,
    "ebay": EbayScraper,
    "willhaben": WillhabenScraper,
    "marktde": MarktdeScraper,
}

# Standardintervalle (Minuten) – Fallback wenn kein DB-Wert vorhanden
DEFAULT_INTERVALS = {
    "kleinanzeigen": 15,
    "shpock": 30,
    "facebook": 60,
    "vinted": 30,
    "ebay": 60,
    "willhaben": 30,
    "marktde": 60,
}

_running: set = set()  # Menge der gerade laufenden Plattform-Namen
_lock = threading.Lock()

_FREE_PRICE_RE = re.compile(
    r"^\s*(0\s*€?|0,00\s*€?|€\s*0([.,]0+)?|kostenlos|gratis|umsonst|zu\s+verschenken|verschenken|free)\s*$",
    re.IGNORECASE,
)
_FREE_TEXT_RE = re.compile(
    r"\b(zu\s+verschenken|verschenke|kostenlos|gratis|umsonst|zu\s+vergeben)\b",
    re.IGNORECASE,
)
_POSITIVE_PRICE_RE = re.compile(r"\b[1-9]\d*([.,]\d+)?\s*€|€\s*[1-9]\d*([.,]\d+)?")


def is_running(platform: str = None) -> bool:
    with _lock:
        return (platform in _running) if platform else bool(_running)


def _is_free(listing: Listing) -> bool:
    if _FREE_PRICE_RE.match(listing.price or ""):
        return True
    if _POSITIVE_PRICE_RE.search(listing.price or ""):
        return False
    if _FREE_TEXT_RE.search(listing.title or ""):
        return True
    if _FREE_TEXT_RE.search(listing.description or ""):
        return True
    return False


def _is_blacklisted(listing: Listing, blacklist: List[str]) -> bool:
    if not blacklist:
        return False
    text = f"{listing.title} {listing.description}".lower()
    return any(term.lower() in text for term in blacklist)


def _matches_all_words(listing: Listing, term: str) -> bool:
    """Prüft via Wortgrenzen, ob alle Wörter des Suchbegriffs in Titel oder Beschreibung stehen.

    Wortgrenzen (\b) verhindern False-Positives wie "werder" → "Schwerder" oder
    "56" → "1956" / "56m²". Gilt auch für Einwort-Begriffe, weil Plattformen wie
    markt.de Substring-Suche verwenden.
    """
    words = term.lower().split()
    if not words:
        return True
    text = f"{listing.title or ''} {listing.description or ''}".lower()
    return all(bool(re.search(r"\b" + re.escape(w) + r"\b", text)) for w in words)


_LANG_FILTER_MIN_LETTERS = 12
_LANG_FILTER_CONFIDENCE = 0.95

try:
    from langdetect import DetectorFactory as _DetectorFactory
    _DetectorFactory.seed = 0  # deterministische Ergebnisse bei gleichem Text
except ImportError:
    pass


def _is_lang_allowed(listing: Listing, allowed_langs: List[str]) -> bool:
    """Gibt True wenn die Sprache erlaubt ist oder nicht sicher erkannt werden kann.

    Ausschließlich natürliche Beschreibungstexte werden analysiert. Kurze oder
    fehlende Beschreibungen werden durchgelassen, weil Sprachmodelle bei
    Produkttiteln regelmäßig deutsche Anzeigen falsch klassifizieren.
    """
    normalized_allowed = {str(lang).strip().lower() for lang in allowed_langs if str(lang).strip()}
    if not normalized_allowed:
        return True
    try:
        from langdetect import detect_langs

        desc = (listing.description or "").strip()
        if sum(char.isalpha() for char in desc) < _LANG_FILTER_MIN_LETTERS:
            return True

        results = detect_langs(desc)
        if not results:
            return True
        best = max(results, key=lambda result: result.prob)
        if best.prob < _LANG_FILTER_CONFIDENCE:
            return True
        return best.lang.lower() in normalized_allowed
    except Exception:
        return True


def run_crawl(platform: str, manual: bool = False) -> dict:
    with _lock:
        if platform in _running:
            logger.warning(f"[{platform}] Crawl läuft bereits – übersprungen.")
            return {"status": "already_running", "new": 0}
        _running.add(platform)
        is_first = len(_running) == 1

    _started_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    _term_count = 0
    stats = {
        "new": 0,
        "total": 0,
        "errors": 0,
        "skipped_blacklist": 0,
        "skipped_lang": 0,
        "free": 0,
    }
    try:
        if is_first:
            clear_log()
            db.set_setting("crawl_status", "running")
        db.set_setting("last_crawl_start", _started_at)

        settings = db.get_settings()

        if settings.get(f"{platform}_enabled") != "1":
            logger.warning(f"[{platform}] Plattform nicht aktiviert – übersprungen.")
            return {"status": "no_platforms", "new": 0}

        _base_cls = PLATFORM_SCRAPER_MAP.get(platform)
        # globals()-Lookup erlaubt Test-Patching der Klassennamen
        scraper_cls = globals().get(_base_cls.__name__) if _base_cls else None
        if not scraper_cls:
            logger.error(f"[{platform}] Unbekannte Plattform.")
            return {"status": "unknown_platform", "new": 0}

        search_terms = db.get_search_terms(enabled_only=True)
        if not search_terms:
            logger.warning("Keine aktiven Suchbegriffe.")
            return {"status": "no_terms", "new": 0}
        _term_count = len(search_terms)

        delay = float(settings.get("crawler_delay", 2))
        max_results = int(settings.get("crawler_max_results", 20))
        raw_blacklist = settings.get("crawler_blacklist", "")
        blacklist = [w.strip() for w in re.split(r"[\n,]", raw_blacklist) if w.strip()]
        lang_filter = settings.get("crawler_lang_filter_enabled") == "1"
        allowed_langs = [l.strip() for l in settings.get("crawler_lang_filter_langs", "de").split(",") if l.strip()]

        # Verspätungs-Warnung
        last_end = settings.get(f"{platform}_last_crawl_end")
        interval_min = int(settings.get(f"{platform}_interval", DEFAULT_INTERVALS.get(platform, 30)))
        if last_end and not manual:
            try:
                elapsed_min = (datetime.now(timezone.utc).replace(tzinfo=None) - datetime.fromisoformat(last_end)).total_seconds() / 60
                if elapsed_min > interval_min * 1.5:
                    logger.warning(
                        f"⚠️ [{platform}] Crawl-Verzögerung: letzter Lauf vor {elapsed_min:.0f} Min. "
                        f"(Intervall: {interval_min} Min.)"
                    )
            except (ValueError, TypeError):
                pass

        scraper = scraper_cls(settings)
        logger.info(f"[{platform}] Crawl startet: {len(search_terms)} Suchbegriff(e)")

        new_listings: List[Listing] = []
        for term_row in search_terms:
            term = term_row["term"]
            term_max_price = term_row.get("max_price")
            try:
                listings = scraper.search(term, max_results=max_results)
                stats["total"] += len(listings)

                for listing in listings:
                    if db.is_known_listing(listing.listing_id):
                        continue

                    if not _matches_all_words(listing, term):
                        logger.debug(f"Suchbegriff-Mismatch (nicht alle Wörter): '{listing.title}'")
                        continue

                    if _is_blacklisted(listing, blacklist):
                        stats["skipped_blacklist"] += 1
                        logger.debug(f"Blacklist: '{listing.title}'")
                        continue

                    if lang_filter:
                        if sum(char.isalpha() for char in (listing.description or "")) < _LANG_FILTER_MIN_LETTERS:
                            listing = scraper.enrich_listing(listing)
                        if not _is_lang_allowed(listing, allowed_langs):
                            stats["skipped_lang"] += 1
                            logger.debug(f"Sprachfilter: '{listing.title}'")
                            continue

                    if term_max_price is not None:
                        if not price_within_limit(listing.price or "", float(term_max_price)):
                            continue

                    listing.is_free = _is_free(listing)
                    if listing.is_free:
                        stats["free"] += 1

                    if db.save_listing(listing):
                        stats["new"] += 1
                        new_listings.append(listing)

                        if listing.location:
                            try:
                                dist = distance_to_home(listing.location, settings)
                                if dist is not None:
                                    db.update_listing_distance(listing.listing_id, dist)
                                    listing.distance_km = round(dist, 1)
                            except Exception as e:
                                logger.warning(f"Entfernungsberechnung für '{listing.location}' fehlgeschlagen: {e}")

            except Exception as e:
                logger.error(f"[{platform}] Fehler bei '{term}': {e}")
                stats["errors"] += 1
            time.sleep(delay)

        db.clear_old_listings(days=30)

        if new_listings and manual:
            notify(new_listings, settings, force=True)

        logger.info(
            f"[{platform}] Crawl beendet: {stats['new']} neu / {stats['total']} gesamt / "
            f"{stats['skipped_blacklist']} Blacklist / {stats['skipped_lang']} Sprache / "
            f"{stats['free']} gratis / "
            f"{stats['errors']} Fehler"
        )

    except Exception as e:
        logger.error(f"[{platform}] Unerwarteter Crawl-Fehler: {e}", exc_info=True)
        stats["errors"] += 1
    finally:
        now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
        with _lock:
            _running.discard(platform)
            is_last = not _running
        if is_last:
            db.set_setting("crawl_status", "idle")
        duration_s = (
            datetime.fromisoformat(now_str) - datetime.fromisoformat(_started_at)
        ).total_seconds()
        db.set_setting(f"{platform}_last_crawl_end", now_str)
        db.set_setting(f"{platform}_last_crawl_found", str(stats["new"]))
        db.set_setting(f"{platform}_last_crawl_duration", str(int(round(duration_s, 0))))
        db.set_setting("last_crawl_end", now_str)
        db.log_crawl_run(platform, _started_at, now_str, round(duration_s, 1),
                         stats["new"], _term_count)

    return {"status": "ok", **stats}


def run_crawl_async(platform: str, manual: bool = False) -> threading.Thread:
    t = threading.Thread(
        target=run_crawl, args=(platform,), kwargs={"manual": manual},
        daemon=True, name=f"crawler-{platform}",
    )
    t.start()
    return t
