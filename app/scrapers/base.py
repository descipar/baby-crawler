"""Gemeinsame Datenstruktur, Hilfsfunktionen und Basis-Klasse für alle Scraper."""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Listing:
    platform: str
    title: str
    price: str
    location: str
    url: str
    listing_id: str
    search_term: str = ""
    description: str = ""
    image_url: str = ""
    image_url_large: str = ""
    is_free: bool = False
    distance_km: Optional[float] = None


def _large_image_url(url: str) -> str:
    """Leitet aus einer CDN-Thumbnail-URL die hochauflösende Variante ab."""
    if not url:
        return url
    if "i.ebayimg.com" in url:
        url = url.replace("/thumbs/images/", "/images/")
        url = re.sub(r"/s-l\d+\.", "/s-l1600.", url)
        return url
    if "img.kleinanzeigen.de" in url:
        url = re.sub(r"\$_\d+\.JPG", "$_2.JPG", url)
        return url
    return url


# ── Gemeinsame Hilfsfunktionen ───────────────────────────────

def _int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class BaseScraper(ABC):
    """Erzwingt das search()-Interface für alle Plattform-Scraper."""

    def __init__(self, settings: dict):
        self.settings = settings

    @abstractmethod
    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        """Sucht nach `term` und gibt maximal `max_results` Listings zurück."""

    def enrich_listing(self, listing: Listing) -> Listing:
        """Lädt bei Bedarf zusätzliche Detaildaten für ein Suchergebnis."""
        return listing


def price_within_limit(price_str: str, max_price: Optional[float]) -> bool:
    """Gibt True zurück wenn price_str <= max_price (oder kein Limit gesetzt)."""
    if max_price is None:
        return True
    m = re.search(r"(\d[\d.]*)", price_str.replace(".", "").replace(",", "."))
    if m:
        try:
            return float(m.group(1)) <= max_price
        except ValueError:
            pass
    return True
