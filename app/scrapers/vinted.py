"""Scraper für Vinted via öffentliche API."""

from collections import OrderedDict
import logging
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing, _float, _int
from ..geo import geocode, haversine

logger = logging.getLogger(__name__)

API_URL = "https://www.vinted.de/api/v2/catalog/items"
BASE_URL = "https://www.vinted.de"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9",
    "Referer": "https://www.vinted.de/",
}

_DETAIL_HEAD_MAX_BYTES = 256 * 1024
_DESCRIPTION_CACHE_MAX_ITEMS = 2000
_description_cache: "OrderedDict[str, str]" = OrderedDict()


class VintedScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[float] = _float(settings.get("vinted_max_price"))
        raw = _int(settings.get("vinted_radius", "30"))
        self.radius_km: int = 30 if raw is None else raw
        self._home: Optional[tuple] = self._resolve_location(settings)
        max_age_raw = _int(settings.get("vinted_max_age_hours", "48"))
        self.max_age_hours: int = max_age_raw if max_age_raw else 0
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._authenticate()

    @staticmethod
    def _resolve_location(settings: dict) -> Optional[tuple]:
        city = settings.get("vinted_location", "").strip()
        if city:
            coords = geocode(city)
            if coords:
                return coords
            logger.warning(f"[Vinted] Stadtname '{city}' konnte nicht geocodiert werden.")
        return None

    def _authenticate(self) -> bool:
        """Holt anonym ausgestellte JWT-Cookies (access_token_web) von der Startseite."""
        try:
            resp = self.session.get(BASE_URL, timeout=15)
            if not resp.ok:
                logger.warning(f"[Vinted] Authentifizierung: HTTP {resp.status_code} – Cookies ggf. ungültig.")
                return False
            return True
        except Exception as e:
            logger.warning(f"[Vinted] Authentifizierung fehlgeschlagen: {e}")
            return False

    @staticmethod
    def _cached_description(url: str) -> Optional[str]:
        description = _description_cache.get(url)
        if description is not None:
            _description_cache.move_to_end(url)
        return description

    @staticmethod
    def _cache_description(url: str, description: str) -> None:
        _description_cache[url] = description
        _description_cache.move_to_end(url)
        while len(_description_cache) > _DESCRIPTION_CACHE_MAX_ITEMS:
            _description_cache.popitem(last=False)

    def _fetch_detail_description(self, url: str, title: str) -> str:
        """Liest nur den HTML-Kopf einer Vinted-Detailseite aus.

        Die Katalog-API liefert üblicherweise keine Beschreibung. Im
        ``meta[name=description]`` der Detailseite ist sie dagegen enthalten.
        Der Stream wird nach dem ``</head>`` geschlossen, damit nicht die bis zu
        mehrere MB große vollständige Seite geladen werden muss.
        """
        if not url.startswith(f"{BASE_URL}/items/"):
            return ""

        cached = self._cached_description(url)
        if cached is not None:
            return cached

        for attempt in range(2):
            response = None
            try:
                response = self.session.get(url, timeout=15, stream=True)
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(chunk_size=16 * 1024):
                    if not chunk:
                        continue
                    content.extend(chunk)
                    if b"</head>" in content.lower() or len(content) >= _DETAIL_HEAD_MAX_BYTES:
                        break

                encoding = response.encoding or "utf-8"
                soup = BeautifulSoup(bytes(content).decode(encoding, errors="replace"), "lxml")
                meta = soup.find("meta", attrs={"name": "description"})
                raw = (meta.get("content", "") if meta else "").strip()
                prefix = f"{title.strip()} - "
                description = raw[len(prefix):].strip() if raw.startswith(prefix) else raw
                if description and description != title.strip():
                    self._cache_description(url, description)
                    return description
            except Exception as e:
                logger.debug(
                    f"[Vinted] Detailbeschreibung für '{title}' nicht geladen "
                    f"(Versuch {attempt + 1}/2): {e}"
                )
            finally:
                if response is not None:
                    response.close()
            if attempt == 0:
                time.sleep(0.25)
        return ""

    def enrich_listing(self, listing: Listing) -> Listing:
        description = self._fetch_detail_description(listing.url, listing.title)
        if description:
            listing.description = description
        return listing

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        logger.info(f"[Vinted] '{term}'")
        params: dict = {
            "search_text": term,
            "per_page": max_results,
            "order": "newest_first",
        }
        if self.max_price is not None:
            params["price_to"] = self.max_price
        try:
            r = self.session.get(API_URL, params=params, timeout=15)
            if r.status_code == 401:
                logger.info("[Vinted] 401 – hole neuen Session-Cookie...")
                self._authenticate()
                r = self.session.get(API_URL, params=params, timeout=15)
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:
            logger.error(f"[Vinted] Fehler bei '{term}': {e}")
            return []

        cutoff_ts = (time.time() - self.max_age_hours * 3600) if self.max_age_hours > 0 else None

        results = []
        for item in items:
            if cutoff_ts is not None:
                created_ts = item.get("created_at_ts")
                if created_ts is not None and float(created_ts) < cutoff_ts:
                    continue
            listing = self._parse(item, term)
            if not listing:
                continue
            if self._home and self.radius_km > 0:
                city = (item.get("user") or {}).get("city", "")
                if city:
                    coords = geocode(city)
                    if coords and haversine(self._home[0], self._home[1], coords[0], coords[1]) > self.radius_km:
                        continue
            results.append(listing)
        logger.info(f"[Vinted] {len(results)} Treffer für '{term}'.")
        return results

    def _parse(self, item: dict, term: str) -> Optional[Listing]:
        try:
            item_id = str(item.get("id", ""))

            raw_price = item.get("price")
            if isinstance(raw_price, dict):
                raw_price = raw_price.get("amount")
            if raw_price is None:
                raw_price = (item.get("total_item_price") or {}).get("amount")
            try:
                price_str = f"{float(raw_price):.2f} €" if raw_price not in (None, "") else "k.A."
            except (ValueError, TypeError):
                price_str = "k.A."

            user = item.get("user") or {}
            location = user.get("city", "")

            photo = item.get("photo") or {}
            image_url = photo.get("url", "")
            image_url_large = photo.get("full_size_url") or image_url

            return Listing(
                platform="Vinted",
                title=item.get("title", "Unbekannt"),
                price=price_str,
                location=location,
                url=item.get("url", f"https://www.vinted.de/items/{item_id}"),
                listing_id=f"vt_{item_id}",
                search_term=term,
                description=item.get("description", ""),
                image_url=image_url,
                image_url_large=image_url_large,
            )
        except Exception as e:
            logger.debug(f"[Vinted] Parse-Fehler: {e}")
            return None
