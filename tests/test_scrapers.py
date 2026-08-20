"""Tests für VintedScraper, ShpockScraper, EbayScraper, WillhabenScraper, MarktdeScraper."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.scrapers.base import BaseScraper, Listing
from app.scrapers.ebay import EbayScraper
from app.scrapers.kleinanzeigen import KleinanzeigenScraper
from app.scrapers.shpock import ShpockScraper
from app.scrapers.vinted import VintedScraper, _description_cache
from app.scrapers.willhaben import WillhabenScraper, _attr
from app.scrapers.markt import MarktdeScraper, _city_slug


# ── BaseScraper-Vererbung ─────────────────────────────────────

class TestBaseScraperInheritance:
    """Alle Scraper müssen BaseScraper implementieren."""

    def test_vinted_ist_base_scraper(self):
        with patch("app.scrapers.vinted.VintedScraper._authenticate"):
            scraper = VintedScraper({})
        assert isinstance(scraper, BaseScraper)

    def test_shpock_ist_base_scraper(self):
        scraper = ShpockScraper({})
        assert isinstance(scraper, BaseScraper)

    def test_ebay_ist_base_scraper(self):
        scraper = EbayScraper({})
        assert isinstance(scraper, BaseScraper)

    def test_kleinanzeigen_ist_base_scraper(self):
        scraper = KleinanzeigenScraper({})
        assert isinstance(scraper, BaseScraper)

    def test_base_scraper_ist_abstrakt(self):
        """BaseScraper darf nicht direkt instanziiert werden."""
        import pytest
        with pytest.raises(TypeError):
            BaseScraper({})  # type: ignore


def _mock_response(json_data=None, text="", status=200):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    return r


def _ebay_page(items_html: str) -> str:
    return (
        f'<html><body>'
        f'<div class="srp-river-results">'
        f'<ul class="srp-results srp-list clearfix">{items_html}</ul>'
        f'</div></body></html>'
    )


# ── Vinted ────────────────────────────────────────────────────────────────────

VINTED_ITEM = {
    "id": 99,
    "title": "Babywanne Hauck",
    "price": {"amount": "15.0", "currency_code": "EUR"},
    "url": "https://www.vinted.de/items/99-babywanne",
    "description": "Top Zustand",
    "user": {"city": "Berlin"},
    "photo": {"url": "https://cdn.vinted.de/img/99.jpg"},
}


class TestVintedScraper:

    def _scraper(self, settings=None):
        return VintedScraper(settings or {})

    def test_search_gibt_listings_zurueck(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", return_value=_mock_response({"items": [VINTED_ITEM]})):
            results = scraper.search("babywanne", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Babywanne Hauck"

    def test_search_leere_antwort(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", return_value=_mock_response({"items": []})):
            assert scraper.search("babywanne") == []

    def test_search_bei_exception(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", side_effect=Exception("Netzwerkfehler")):
            assert scraper.search("babywanne") == []

    def test_parse_felder(self):
        scraper = self._scraper()
        listing = scraper._parse(VINTED_ITEM, "babywanne")
        assert listing.platform == "Vinted"
        assert listing.listing_id == "vt_99"
        assert listing.price == "15.00 €"
        assert listing.location == "Berlin"
        assert listing.url == "https://www.vinted.de/items/99-babywanne"
        assert listing.image_url == "https://cdn.vinted.de/img/99.jpg"
        assert listing.search_term == "babywanne"
        assert listing.description == "Top Zustand"

    def test_parse_fehlende_felder_kein_absturz(self):
        scraper = self._scraper()
        listing = scraper._parse({}, "test")
        assert listing is not None
        assert listing.listing_id == "vt_"

    def test_parse_ohne_foto(self):
        scraper = self._scraper()
        listing = scraper._parse({**VINTED_ITEM, "photo": None}, "test")
        assert listing.image_url == ""

    def test_parse_preis_in_nested_struktur(self):
        scraper = self._scraper()
        item = {**VINTED_ITEM, "price": None, "total_item_price": {"amount": "20"}}
        listing = scraper._parse(item, "test")
        assert listing.price == "20.00 €"

    def test_parse_kein_preis_ergibt_ka(self):
        scraper = self._scraper()
        listing = scraper._parse({**VINTED_ITEM, "price": None}, "test")
        assert listing.price == "k.A."

    def test_max_price_wird_gesetzt(self):
        scraper = VintedScraper({"vinted_max_price": "30"})
        assert scraper.max_price == 30.0

    def test_max_price_ungueltig_wird_ignoriert(self):
        scraper = VintedScraper({"vinted_max_price": "abc"})
        assert scraper.max_price is None

    def test_search_sendet_max_price_parameter(self):
        scraper = VintedScraper({"vinted_max_price": "25"})
        with patch.object(scraper.session, "get", return_value=_mock_response({"items": []})) as mock_get:
            scraper.search("babywanne")
        params = mock_get.call_args[1]["params"]
        assert params["price_to"] == 25.0

    def test_authenticate_wird_im_init_aufgerufen(self):
        with patch.object(VintedScraper, "_authenticate") as mock_auth:
            VintedScraper({})
        mock_auth.assert_called_once()

    def test_401_loest_reauth_und_retry_aus(self):
        scraper = VintedScraper({})
        response_401 = _mock_response(status=401)
        response_401.raise_for_status.side_effect = Exception("401")
        response_ok = _mock_response({"items": []})
        with patch.object(scraper.session, "get", side_effect=[response_401, response_ok, response_ok]) as mock_get:
            scraper.search("babywanne")
        # Erster Call: API (401), zweiter: _authenticate (Homepage), dritter: API-Retry
        assert mock_get.call_count == 3

    def test_parse_preis_als_dict(self):
        scraper = VintedScraper({})
        item = {**VINTED_ITEM, "price": {"amount": "9.5", "currency_code": "EUR"}}
        listing = scraper._parse(item, "test")
        assert listing.price == "9.50 €"

    def test_radius_null_deaktiviert_filter(self):
        """radius_km=0 → Entfernungsfilter komplett deaktiviert."""
        settings = {"vinted_radius": "0", "vinted_location": "München"}
        with patch("app.scrapers.vinted.geocode", return_value=(48.1351, 11.5820)):
            scraper = VintedScraper(settings)
        far_item = {**VINTED_ITEM, "user": {"city": "Hamburg"}}
        response = _mock_response({"items": [far_item]})
        with patch.object(scraper.session, "get", return_value=response):
            with patch("app.scrapers.vinted.geocode", return_value=(53.5753, 10.0153)):
                results = scraper.search("babywanne")
        assert len(results) == 1

    def test_radius_null_kein_geocode_fuer_item(self):
        """Bei radius_km=0 wird geocode() für die Artikel-Standorte nicht aufgerufen."""
        settings = {"vinted_radius": "0", "vinted_location": ""}
        scraper = VintedScraper(settings)
        response = _mock_response({"items": [VINTED_ITEM]})
        with patch.object(scraper.session, "get", return_value=response):
            with patch("app.scrapers.vinted.geocode") as mock_geocode:
                scraper.search("babywanne")
        mock_geocode.assert_not_called()

    def test_detailbeschreibung_wird_aus_meta_tag_geladen(self):
        _description_cache.clear()
        scraper = self._scraper()
        title = "Momcozy Air 1"
        detail = "Bonjour, ce tire-lait portable est neuf et encore dans son emballage d'origine."
        html = (
            '<html><head><meta name="description" '
            f'content="{title} - {detail}"/></head><body>großer Rest</body></html>'
        )
        response = MagicMock()
        response.encoding = "utf-8"
        response.iter_content.return_value = [html.encode()]
        response.raise_for_status = MagicMock()

        with patch.object(scraper.session, "get", return_value=response) as mock_get:
            listing = Listing("Vinted", title, "50 €", "", "https://www.vinted.de/items/991-test", "vt_991")
            enriched = scraper.enrich_listing(listing)

        assert enriched.description == detail
        mock_get.assert_called_once_with(listing.url, timeout=15, stream=True)
        response.close.assert_called_once()

    def test_detailbeschreibung_wird_prozessweit_gecached(self):
        _description_cache.clear()
        scraper = self._scraper()
        url = "https://www.vinted.de/items/992-test"
        _description_cache[url] = "Ausführliche deutsche Beschreibung aus dem Cache für diesen Artikel."
        listing = Listing("Vinted", "Kinderwagen", "50 €", "", url, "vt_992")

        with patch.object(scraper.session, "get") as mock_get:
            scraper.enrich_listing(listing)

        assert listing.description.startswith("Ausführliche deutsche Beschreibung")
        mock_get.assert_not_called()

    def test_fremde_detail_url_wird_nicht_aufgerufen(self):
        scraper = self._scraper()
        listing = Listing("Vinted", "Test", "10 €", "", "https://example.com/items/1", "vt_993")
        with patch.object(scraper.session, "get") as mock_get:
            scraper.enrich_listing(listing)
        assert listing.description == ""
        mock_get.assert_not_called()

    def test_detailfehler_laesst_beschreibung_unveraendert(self):
        _description_cache.clear()
        scraper = self._scraper()
        listing = Listing(
            "Vinted", "Test", "10 €", "", "https://www.vinted.de/items/994-test", "vt_994",
            description="Kurz",
        )
        with patch.object(scraper.session, "get", side_effect=ConnectionError("Timeout")):
            scraper.enrich_listing(listing)
        assert listing.description == "Kurz"

    def test_detailabruf_wird_einmal_wiederholt(self):
        _description_cache.clear()
        scraper = self._scraper()
        title = "Kinderwagen"
        detail = "Sehr guter Zustand und nur wenige Male benutzt."
        html = f'<html><head><meta name="description" content="{title} - {detail}"/></head></html>'
        response = MagicMock()
        response.encoding = "utf-8"
        response.iter_content.return_value = [html.encode()]
        listing = Listing(
            "Vinted", title, "50 €", "", "https://www.vinted.de/items/995-test", "vt_995"
        )

        with patch.object(
            scraper.session, "get", side_effect=[ConnectionError("Timeout"), response]
        ) as mock_get, patch("app.scrapers.vinted.time.sleep") as mock_sleep:
            scraper.enrich_listing(listing)

        assert listing.description == detail
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(0.25)


# ── Shpock ────────────────────────────────────────────────────────────────────

SHPOCK_ITEM = {
    "__typename": "ItemSummary",
    "id": "abc123",
    "title": "Babytrage Ergobaby",
    "description": "Wenig benutzt",
    "price": 45,
    "isFree": False,
    "isSold": False,
    "locality": "44135 Dortmund",
    "distance": None,
    "distanceUnit": None,
    "path": "/de-de/i/abc123/babytrage",
    "media": [{"id": "deadbeef01234567890abcde"}],
}


class TestShpockScraper:

    def _scraper(self, settings=None):
        return ShpockScraper(settings or {
            "shpock_max_price": "100",
            "shpock_radius": "30",
            "shpock_latitude": "51.5136",
            "shpock_longitude": "7.4653",
        })

    def _api_response(self, items):
        return {"data": {"itemSearch": {"itemResults": [{"items": items}]}}}

    def test_parse_felder(self):
        scraper = self._scraper()
        listing = scraper._parse(SHPOCK_ITEM, "babytrage")
        assert listing.platform == "Shpock"
        assert listing.listing_id == "sp_abc123"
        assert listing.title == "Babytrage Ergobaby"
        assert listing.price == "45.00 €"
        assert listing.location == "44135 Dortmund"
        assert listing.url == "https://www.shpock.com/de-de/i/abc123/babytrage"
        assert listing.image_url == "https://m1.secondhandapp.at/full/deadbeef01234567890abcde"
        assert listing.search_term == "babytrage"

    def test_parse_is_free(self):
        scraper = self._scraper()
        item = {**SHPOCK_ITEM, "isFree": True, "price": 0}
        listing = scraper._parse(item, "test")
        assert listing.price == "0 €"

    def test_parse_ohne_media(self):
        scraper = self._scraper()
        listing = scraper._parse({**SHPOCK_ITEM, "media": []}, "test")
        assert listing.image_url == ""

    def test_search_filtert_verkaufte_items(self):
        scraper = self._scraper()
        sold = {**SHPOCK_ITEM, "isSold": True}
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([sold]))):
            with patch("app.scrapers.shpock.geocode", return_value=(51.5136, 7.4653)):
                results = scraper.search("babytrage")
        assert results == []

    def test_search_filtert_nach_max_price(self):
        scraper = self._scraper({"shpock_max_price": "30", "shpock_radius": "200",
                                  "shpock_latitude": "51.5136", "shpock_longitude": "7.4653"})
        teuer = {**SHPOCK_ITEM, "price": 50}
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([teuer]))):
            with patch("app.scrapers.shpock.geocode", return_value=(51.5136, 7.4653)):
                results = scraper.search("babytrage")
        assert results == []

    def test_search_filtert_nach_radius(self):
        scraper = self._scraper()  # radius=30 km, Dortmund
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([SHPOCK_ITEM]))):
            # München liegt ~470 km entfernt
            with patch("app.scrapers.shpock.geocode", return_value=(48.1372, 11.5755)):
                results = scraper.search("babytrage")
        assert results == []

    def test_search_gibt_treffer_im_radius_zurueck(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([SHPOCK_ITEM]))):
            # Dortmund-Mitte: innerhalb 30 km
            with patch("app.scrapers.shpock.geocode", return_value=(51.5200, 7.4800)):
                results = scraper.search("babytrage")
        assert len(results) == 1
        assert results[0].title == "Babytrage Ergobaby"

    def test_search_bei_api_fehler(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "post", side_effect=Exception("Timeout")):
            assert scraper.search("babytrage") == []

    def test_search_bei_graphql_fehler(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "post", return_value=_mock_response({"errors": [{"message": "oops"}]})):
            assert scraper.search("babytrage") == []

    def test_radius_null_deaktiviert_filter(self):
        """radius_km=0 → Entfernungsfilter komplett deaktiviert."""
        scraper = self._scraper({
            "shpock_max_price": "200",
            "shpock_radius": "0",
            "shpock_latitude": "51.5136",
            "shpock_longitude": "7.4653",
        })
        far_item = {**SHPOCK_ITEM, "locality": "München"}
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([far_item]))):
            with patch("app.scrapers.shpock.geocode", return_value=(48.1372, 11.5755)):
                results = scraper.search("babytrage")
        assert len(results) == 1

    def test_radius_null_kein_geocode_aufruf(self):
        """Bei radius_km=0 wird geocode() nicht aufgerufen."""
        scraper = self._scraper({
            "shpock_max_price": "200",
            "shpock_radius": "0",
            "shpock_latitude": "51.5136",
            "shpock_longitude": "7.4653",
        })
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([SHPOCK_ITEM]))):
            with patch("app.scrapers.shpock.geocode") as mock_geocode:
                scraper.search("babytrage")
        mock_geocode.assert_not_called()

    def test_radius_null_kein_distance_feld_im_payload(self):
        """Bei radius_km=0 enthält der API-Payload kein distance-Feld (verhindert 0-Meter-Filter)."""
        import json as _json
        scraper = self._scraper({"shpock_radius": "0"})
        mock_post = MagicMock(return_value=_mock_response(self._api_response([])))
        with patch.object(scraper.session, "post", mock_post):
            scraper.search("test")
        _, kwargs = mock_post.call_args
        payload = kwargs.get("json", mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else {})
        filters = _json.loads(payload["variables"]["serializedFilters"])
        assert "distance" not in filters


# ── eBay ──────────────────────────────────────────────────────────────────────

EBAY_ITEM_HTML = """
<li class="s-card s-card--horizontal" data-listingid="123456789">
  <img alt="Kinderwagen Bugaboo" class="s-card__image" src="https://i.ebayimg.com/img/123.jpg" />
  <a class="s-card__link" href="https://www.ebay.de/itm/123456789?_trkparms=test">
    <div class="s-card__title">
      <span class="su-styled-text primary default">Kinderwagen Bugaboo</span>
    </div>
  </a>
  <span class="su-styled-text primary bold large-1 s-card__price">EUR 80,00</span>
</li>
"""

EBAY_NO_TITLE_HTML = """
<li class="s-card s-card--horizontal" data-listingid="999">
  <span>kein Titel hier</span>
</li>
"""


class TestEbayScraper:

    def _scraper(self, settings=None):
        return EbayScraper(settings or {})

    def test_search_gibt_listings_zurueck(self):
        scraper = self._scraper()
        html = _ebay_page(EBAY_ITEM_HTML)
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            results = scraper.search("kinderwagen", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Kinderwagen Bugaboo"

    def test_item_ohne_titel_wird_ignoriert(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", return_value=_mock_response(text=_ebay_page(EBAY_NO_TITLE_HTML))):
            assert scraper.search("kinderwagen") == []

    def test_search_bei_exception(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", side_effect=Exception("Timeout")):
            assert scraper.search("kinderwagen") == []

    def test_parse_felder(self):
        from bs4 import BeautifulSoup
        scraper = self._scraper()
        item = BeautifulSoup(EBAY_ITEM_HTML, "lxml").select_one("li.s-card")
        listing = scraper._parse(item, "kinderwagen")
        assert listing.platform == "eBay"
        assert listing.title == "Kinderwagen Bugaboo"
        assert listing.listing_id == "eb_123456789"
        assert listing.location == ""
        assert listing.image_url == "https://i.ebayimg.com/img/123.jpg"
        assert listing.search_term == "kinderwagen"

    def test_build_url_enkodiert_leerzeichen(self):
        scraper = self._scraper()
        assert "baby+stuhl" in scraper._build_url("baby stuhl", 20)

    def test_build_url_enthaelt_neuheits_sortierung(self):
        scraper = self._scraper()
        assert "_sop=10" in scraper._build_url("test", 20)

    def test_price_ok_unter_max(self):
        scraper = EbayScraper({"ebay_max_price": "100"})
        listing = Listing("eBay", "Test", "80,00 €", "", "", "eb_1", "test")
        assert scraper._price_ok(listing) is True

    def test_price_ok_ueber_max(self):
        scraper = EbayScraper({"ebay_max_price": "50"})
        listing = Listing("eBay", "Test", "80,00 €", "", "", "eb_1", "test")
        assert scraper._price_ok(listing) is False

    def test_price_ok_ohne_max_immer_true(self):
        scraper = self._scraper()
        listing = Listing("eBay", "Test", "999,00 €", "", "", "eb_1", "test")
        assert scraper._price_ok(listing) is True

    def test_price_ok_ka_wird_durchgelassen(self):
        scraper = EbayScraper({"ebay_max_price": "50"})
        listing = Listing("eBay", "Test", "k.A.", "", "", "eb_1", "test")
        assert scraper._price_ok(listing) is True

    def test_max_price_ungueltig_wird_ignoriert(self):
        scraper = EbayScraper({"ebay_max_price": "abc"})
        assert scraper.max_price is None

    def test_build_url_mit_standort(self):
        scraper = EbayScraper({"ebay_location": "44135", "ebay_radius": "25"})
        url = scraper._build_url("kinderwagen", 20)
        assert "_stpos=44135" in url
        assert "_sadis=25" in url

    def test_build_url_ohne_standort_kein_stpos(self):
        scraper = EbayScraper({})
        url = scraper._build_url("kinderwagen", 20)
        assert "_stpos" not in url
        assert "_sadis" not in url

    def test_standort_stadtname_wird_enkodiert(self):
        scraper = EbayScraper({"ebay_location": "Bad Homburg", "ebay_radius": "30"})
        url = scraper._build_url("test", 20)
        assert "_stpos=Bad+Homburg" in url


class TestVintedScraperStandort:

    def _scraper(self, settings=None):
        with patch("app.scrapers.vinted.VintedScraper._authenticate"):
            with patch("app.scrapers.vinted.geocode", return_value=(48.1351, 11.5820)):
                return VintedScraper(settings or {
                    "vinted_location": "München",
                    "vinted_radius": "30",
                })

    def test_resolve_location_gibt_koordinaten_zurueck(self):
        with patch("app.scrapers.vinted.geocode", return_value=(48.1351, 11.5820)):
            with patch("app.scrapers.vinted.VintedScraper._authenticate"):
                scraper = VintedScraper({"vinted_location": "München", "vinted_radius": "30"})
        assert scraper._home == (48.1351, 11.5820)
        assert scraper.radius_km == 30

    def test_kein_standort_kein_filter(self):
        with patch("app.scrapers.vinted.VintedScraper._authenticate"):
            scraper = VintedScraper({})
        assert scraper._home is None

    def test_search_filtert_nach_radius(self):
        scraper = self._scraper()
        item_hamburg = {**VINTED_ITEM, "user": {"city": "Hamburg"}}
        mock_resp = _mock_response({"items": [item_hamburg]})
        with patch.object(scraper.session, "get", return_value=mock_resp):
            # Hamburg liegt ~610 km von München
            with patch("app.scrapers.vinted.geocode", return_value=(53.5511, 10.0)):
                results = scraper.search("babywanne")
        assert results == []

    def test_search_gibt_treffer_im_radius_zurueck(self):
        scraper = self._scraper()
        item_nahe = {**VINTED_ITEM, "user": {"city": "Dachau"}}
        mock_resp = _mock_response({"items": [item_nahe]})
        with patch.object(scraper.session, "get", return_value=mock_resp):
            # Dachau liegt ~20 km von München
            with patch("app.scrapers.vinted.geocode", return_value=(48.2601, 11.4338)):
                results = scraper.search("babywanne")
        assert len(results) == 1


# ── eBay: fehlende Pfade ──────────────────────────────────────────────────────

class TestEbayScraperCoverage:

    def test_parse_ohne_title_element_gibt_none(self):
        from bs4 import BeautifulSoup
        scraper = EbayScraper({})
        item = BeautifulSoup('<li class="s-card"><span>kein Titel</span></li>', "lxml").select_one("li")
        assert scraper._parse(item, "test") is None

    def test_parse_exception_gibt_none(self):
        scraper = EbayScraper({})
        assert scraper._parse(None, "test") is None


# ── Shpock: fehlende Pfade ────────────────────────────────────────────────────

class TestShpockScraperCoverage:

    def _scraper(self, settings=None):
        return ShpockScraper(settings or {"shpock_radius": "0"})

    def _api_response(self, items):
        return {"data": {"itemSearch": {"itemResults": [{"items": items}]}}}

    def test_search_filtert_nicht_item_summary(self):
        """Items mit falschem __typename werden übersprungen."""
        scraper = self._scraper()
        wrong = {**SHPOCK_ITEM, "__typename": "Advertisement"}
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([wrong]))):
            assert scraper.search("test") == []

    def test_search_ueberspringt_none_listings(self):
        """_parse gibt None zurück → Item wird übersprungen."""
        scraper = self._scraper()
        # Kaputtes media (kein 'id') → _parse wirft KeyError → None
        broken = {**SHPOCK_ITEM, "media": [{"no_id": "x"}]}
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([broken]))):
            assert scraper.search("test") == []

    def test_search_preis_nicht_parsierbar_wird_durchgelassen(self):
        """ValueError beim Preisvergleich wird abgefangen; Listing bleibt erhalten."""
        scraper = self._scraper({"shpock_radius": "0", "shpock_max_price": "50"})
        unparseable = Listing("Shpock", "Test", "auf Anfrage", "", "https://x.com", "sp_x", "test")
        with patch.object(scraper, "_parse", return_value=unparseable):
            with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([SHPOCK_ITEM]))):
                results = scraper.search("test")
        assert len(results) == 1

    def test_search_stoppt_bei_max_results(self):
        """max_results wird eingehalten; überzählige Items werden nicht zurückgegeben."""
        scraper = self._scraper()
        two_items = [SHPOCK_ITEM, {**SHPOCK_ITEM, "id": "xyz999"}]
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response(two_items))):
            results = scraper.search("test", max_results=1)
        assert len(results) == 1

    def test_parse_preis_ka_fuer_none(self):
        """price=None und isFree=False → 'k.A.'."""
        scraper = self._scraper()
        listing = scraper._parse({**SHPOCK_ITEM, "price": None, "isFree": False}, "test")
        assert listing is not None
        assert listing.price == "k.A."

    def test_parse_exception_gibt_none(self):
        scraper = self._scraper()
        assert scraper._parse(None, "test") is None


# ── Vinted: fehlende Pfade ────────────────────────────────────────────────────

class TestVintedScraperCoverage:

    def test_resolve_location_geocode_fehlschlag_gibt_none(self):
        """geocode gibt None zurück → _home bleibt None."""
        with patch("app.scrapers.vinted.geocode", return_value=None):
            with patch.object(VintedScraper, "_authenticate"):
                scraper = VintedScraper({"vinted_location": "Unbekannte-Stadt-XYZ"})
        assert scraper._home is None

    def test_authenticate_nicht_ok_gibt_false(self):
        """HTTP non-ok → _authenticate gibt False zurück."""
        scraper = VintedScraper({})
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 403
        with patch.object(scraper.session, "get", return_value=mock_resp):
            assert scraper._authenticate() is False

    def test_authenticate_exception_gibt_false(self):
        """Netzwerkfehler in _authenticate → False."""
        scraper = VintedScraper({})
        with patch.object(scraper.session, "get", side_effect=ConnectionError("Timeout")):
            assert scraper._authenticate() is False

    def test_search_age_filter_verwirft_altes_item(self):
        """Items älter als vinted_max_age_hours werden gefiltert."""
        import time
        scraper = VintedScraper({"vinted_max_age_hours": "24"})
        old_ts = str(int(time.time()) - 48 * 3600)
        old_item = {**VINTED_ITEM, "created_at_ts": old_ts}
        with patch.object(scraper.session, "get", return_value=_mock_response({"items": [old_item]})):
            assert scraper.search("babywanne") == []

    def test_search_ueberspringt_none_listings(self):
        """_parse gibt None zurück → Item wird übersprungen."""
        scraper = VintedScraper({})
        with patch.object(scraper, "_parse", return_value=None):
            with patch.object(scraper.session, "get", return_value=_mock_response({"items": [VINTED_ITEM]})):
                assert scraper.search("test") == []

    def test_parse_preis_nicht_konvertierbar_ergibt_ka(self):
        """Nicht-numerischer Preisstring → 'k.A.'."""
        scraper = VintedScraper({})
        listing = scraper._parse({**VINTED_ITEM, "price": "auf Anfrage"}, "test")
        assert listing is not None
        assert listing.price == "k.A."

    def test_parse_exception_gibt_none(self):
        scraper = VintedScraper({})
        assert scraper._parse(None, "test") is None


# ── markt.de: fehlende Pfade ──────────────────────────────────────────────────

MARKTDE_EMPTY_TITLE_HTML = """
<article class="clsy-c-result-list-item">
  <a class="clsy-c-result-list-item__link" href="/test/99999/"></a>
</article>
"""


class TestMarktdeScraperCoverage:

    def test_parse_leerer_titel_gibt_none(self):
        from bs4 import BeautifulSoup
        scraper = MarktdeScraper({})
        item = BeautifulSoup(MARKTDE_EMPTY_TITLE_HTML, "lxml").select_one(".clsy-c-result-list-item")
        assert scraper._parse(item, "test") is None

    def test_parse_exception_gibt_none(self):
        scraper = MarktdeScraper({})
        assert scraper._parse(None, "test") is None

    def test_search_stoppt_bei_max_results_innerhalb_seite(self):
        """max_results < Seiten-Items → Loop bricht ab, nicht alle Items werden verarbeitet."""
        scraper = MarktdeScraper({"marktde_location": "Berlin"})
        page = _marktde_page(MARKTDE_ITEM_HTML * 5)
        with patch.object(scraper.session, "get", return_value=_mock_response(text=page)):
            results = scraper.search("kinderwagen", max_results=2)
        assert len(results) == 2

    def test_search_ruft_zweite_seite_ab(self):
        """Volle Seite (20 Items) → page-Parameter für Seite 2 gesetzt."""
        scraper = MarktdeScraper({"marktde_location": "Berlin"})
        page1 = _marktde_page(MARKTDE_ITEM_HTML * 20)
        page2 = _marktde_page(MARKTDE_ITEM_HTML * 3)
        with patch.object(scraper.session, "get", side_effect=[
            _mock_response(text=page1), _mock_response(text=page2),
        ]) as mock_get:
            results = scraper.search("kinderwagen", max_results=30)
        assert len(results) == 23
        # Zweiter Aufruf muss page-Parameter enthalten
        second_call_params = mock_get.call_args_list[1][1]["params"]
        assert second_call_params.get("page") == 2


# ── willhaben: fehlende Pfade ─────────────────────────────────────────────────

class TestWillhabenScraperCoverage:

    def test_search_stoppt_bei_max_results_und_paginiert(self):
        """max_results=1 mit 3 Items → stoppt nach erstem + pagination-Check läuft trotzdem."""
        scraper = WillhabenScraper({"willhaben_paylivery_only": "1"})
        html = _willhaben_html([_willhaben_advert(str(i)) for i in range(3)])
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            results = scraper.search("test", max_results=1)
        assert len(results) == 1

    def test_search_ueberspringt_none_listings(self):
        """_parse gibt None zurück → Item wird übersprungen."""
        scraper = WillhabenScraper({})
        html = _willhaben_html([_willhaben_advert()])
        with patch.object(scraper, "_parse", return_value=None):
            with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
                assert scraper.search("test") == []

    def test_search_price_filter_in_loop(self):
        """Item mit Preis über max_price wird im Loop gefiltert."""
        scraper = WillhabenScraper({"willhaben_max_price": "80", "willhaben_paylivery_only": "1"})
        teures_item = _willhaben_advert(price="€ 150")
        html = _willhaben_html([teures_item])
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            assert scraper.search("test") == []

    def test_search_pagination_bei_gefilterten_items(self):
        """Seite voll aber viele Items gefiltert → Seite 2 wird abgerufen."""
        scraper = WillhabenScraper({"willhaben_max_price": "80", "willhaben_paylivery_only": "1"})
        cheap = [_willhaben_advert(str(i), price="€ 50") for i in range(2)]
        expensive = [_willhaben_advert(str(i + 10), price="€ 500") for i in range(8)]
        page2 = _willhaben_html([_willhaben_advert("99", price="€ 30")])
        # per_page = min(10, 30) = 10; page1 hat genau 10 → nicht früh abbrechen
        with patch.object(scraper.session, "get", side_effect=[
            _mock_response(text=_willhaben_html(cheap + expensive)),
            _mock_response(text=page2),
        ]):
            results = scraper.search("test", max_results=10)
        assert len(results) == 3  # 2 günstige + 1 von Seite 2

    def test_extract_adverts_ungueliges_json(self):
        """Fehlerhaftes JSON in __NEXT_DATA__ → leere Liste, kein Absturz."""
        scraper = WillhabenScraper({})
        html = '<script id="__NEXT_DATA__">{ das ist kein json {{{</script>'
        assert scraper._extract_adverts(html) == []

    def test_extract_coords_exception_wird_abgefangen(self):
        """Exception beim Koordinaten-Parsen wird abgefangen → None."""
        scraper = WillhabenScraper({})
        bad_val = MagicMock()
        bad_val.__bool__ = lambda s: True
        bad_val.__contains__ = lambda s, x: True
        bad_val.strip = MagicMock(return_value=bad_val)
        bad_val.split = MagicMock(side_effect=ValueError("Mock"))
        attrs = [{"name": "COORDINATES", "values": [bad_val]}]
        assert scraper._extract_coords({"attributes": {"attribute": attrs}}) is None

    def test_parse_exception_gibt_none(self):
        scraper = WillhabenScraper({})
        assert scraper._parse(None, "test") is None


# ── Kleinanzeigen ─────────────────────────────────────────────────────────────

from app.scrapers.kleinanzeigen import KleinanzeigenScraper, _ascii_slug

KA_ITEM_HTML = """
<article class="aditem">
  <h2 class="text-module-begin">
    <a href="/s-anzeige/kinderwagen-abc/123456789-123-456">Kinderwagen ABC</a>
  </h2>
  <p class="aditem-main--middle--price-shipping--price">80 €</p>
  <div class="aditem-main--top--left">Dortmund</div>
  <p class="aditem-main--middle--description">Sehr guter Zustand</p>
  <img class="aditem-image" src="https://img.kleinanzeigen.de/api/v1/img.jpg" />
</article>
"""


def _ka_page(items_html: str) -> str:
    return f"<html><body>{items_html}</body></html>"


class TestAsciiSlug:

    def test_umlaut_ae(self):
        assert _ascii_slug("Kinderwagen") == "kinderwagen"

    def test_umlaut_oe(self):
        assert _ascii_slug("Köln") == "koeln"

    def test_umlaut_ue(self):
        assert _ascii_slug("Übersicht") == "uebersicht"

    def test_umlaut_ss(self):
        assert _ascii_slug("Straße") == "strasse"

    def test_leerzeichen_zu_bindestrich(self):
        assert _ascii_slug("baby stuhl") == "baby-stuhl"

    def test_mehrere_leerzeichen(self):
        assert _ascii_slug("baby  stuhl") == "baby-stuhl"


class TestKleinanzeigenScraper:

    def _scraper(self, settings=None):
        with patch.object(KleinanzeigenScraper, "_resolve_location_id", return_value=None):
            return KleinanzeigenScraper(settings or {})

    def test_ist_base_scraper(self):
        assert isinstance(self._scraper(), BaseScraper)

    def test_resolve_location_kein_ort_gibt_none(self):
        with patch.object(KleinanzeigenScraper, "_resolve_location_id", return_value=None):
            scraper = KleinanzeigenScraper({})
        assert scraper._location_id is None

    def test_resolve_location_id_findet_id(self):
        """Redirect-URL enthält locationId → wird korrekt extrahiert."""
        scraper = self._scraper({"kleinanzeigen_location": "Dortmund", "kleinanzeigen_radius": "30"})
        mock_resp = _mock_response()
        mock_resp.url = "https://www.kleinanzeigen.de/s-dortmund/kinderwagen/k0l7637r30"
        with patch.object(scraper.session, "get", return_value=mock_resp):
            lid = scraper._resolve_location_id()
        assert lid == 7637

    def test_resolve_location_id_keine_id_in_url(self):
        """Redirect-URL ohne locationId → None."""
        scraper = self._scraper({"kleinanzeigen_location": "Dortmund"})
        mock_resp = _mock_response()
        mock_resp.url = "https://www.kleinanzeigen.de/s-anzeigen/kinderwagen/k0"
        with patch.object(scraper.session, "get", return_value=mock_resp):
            assert scraper._resolve_location_id() is None

    def test_resolve_location_id_exception_gibt_none(self):
        """Netzwerkfehler → None."""
        scraper = self._scraper({"kleinanzeigen_location": "Dortmund"})
        with patch.object(scraper.session, "get", side_effect=Exception("Timeout")):
            assert scraper._resolve_location_id() is None

    def test_search_gibt_listings_zurueck(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", return_value=_mock_response(text=_ka_page(KA_ITEM_HTML))):
            results = scraper.search("kinderwagen", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Kinderwagen ABC"

    def test_search_bei_exception(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", side_effect=Exception("Timeout")):
            assert scraper.search("kinderwagen") == []

    def test_parse_felder(self):
        from bs4 import BeautifulSoup
        scraper = self._scraper()
        item = BeautifulSoup(KA_ITEM_HTML, "lxml").select_one("article.aditem")
        listing = scraper._parse(item, "kinderwagen")
        assert listing is not None
        assert listing.platform == "Kleinanzeigen"
        assert listing.title == "Kinderwagen ABC"
        assert listing.listing_id == "ka_123456789"
        assert listing.price == "80 €"
        assert listing.location == "Dortmund"
        assert listing.description == "Sehr guter Zustand"
        assert listing.image_url == "https://img.kleinanzeigen.de/api/v1/img.jpg"
        assert listing.search_term == "kinderwagen"

    def test_parse_ohne_title_element_gibt_none(self):
        from bs4 import BeautifulSoup
        scraper = self._scraper()
        item = BeautifulSoup('<article class="aditem"><p>kein Titel</p></article>', "lxml").select_one("article")
        assert scraper._parse(item, "test") is None

    def test_parse_exception_gibt_none(self):
        scraper = self._scraper()
        assert scraper._parse(None, "test") is None

    def test_build_url_mit_location_id(self):
        with patch.object(KleinanzeigenScraper, "_resolve_location_id", return_value=7637):
            scraper = KleinanzeigenScraper({
                "kleinanzeigen_location": "Dortmund",
                "kleinanzeigen_radius": "30",
            })
        url = scraper._build_url("kinderwagen")
        assert "k0l7637r30" in url
        assert "dortmund" in url

    def test_build_url_ohne_location_fallback(self):
        scraper = self._scraper()
        url = scraper._build_url("kinderwagen")
        assert "/s-kinderwagen/k0" in url

    def test_build_url_mit_max_price(self):
        with patch.object(KleinanzeigenScraper, "_resolve_location_id", return_value=7637):
            scraper = KleinanzeigenScraper({
                "kleinanzeigen_location": "Dortmund",
                "kleinanzeigen_max_price": "100",
                "kleinanzeigen_radius": "30",
            })
        url = scraper._build_url("kinderwagen")
        assert "maxPrice=100" in url

    def test_build_url_fallback_mit_max_price(self):
        with patch.object(KleinanzeigenScraper, "_resolve_location_id", return_value=None):
            scraper = KleinanzeigenScraper({"kleinanzeigen_max_price": "80"})
        url = scraper._build_url("kinderwagen")
        assert "maxPrice=80" in url

    def test_price_ok_filtert_teure_items(self):
        with patch.object(KleinanzeigenScraper, "_resolve_location_id", return_value=None):
            scraper = KleinanzeigenScraper({"kleinanzeigen_max_price": "50"})
        listing = Listing("Kleinanzeigen", "Test", "80 €", "", "", "ka_1", "test")
        assert scraper._price_ok(listing) is False

    def test_price_ok_guenstiges_item(self):
        with patch.object(KleinanzeigenScraper, "_resolve_location_id", return_value=None):
            scraper = KleinanzeigenScraper({"kleinanzeigen_max_price": "100"})
        listing = Listing("Kleinanzeigen", "Test", "80 €", "", "", "ka_1", "test")
        assert scraper._price_ok(listing) is True


# ── Willhaben ─────────────────────────────────────────────────────────────────

def _willhaben_advert(advert_id="12345", title="Kinderwagen ABC", price="€ 50",
                       location="Wien", seo_url="kaufen-und-verkaufen/d/kinderwagen-abc/12345/",
                       description="Super Zustand", image="3/abc/1.jpg",
                       coords="48.2083,16.3731") -> dict:
    attrs = [
        {"name": "HEADING", "values": [title]},
        {"name": "PRICE_FOR_DISPLAY", "values": [price]},
        {"name": "LOCATION", "values": [location]},
        {"name": "SEO_URL", "values": [seo_url]},
        {"name": "BODY_DYN", "values": [description]},
        {"name": "MMO", "values": [image]},
        {"name": "COORDINATES", "values": [coords]},
    ]
    return {"id": advert_id, "attributes": {"attribute": attrs}}


def _willhaben_html(adverts: list) -> str:
    data = {
        "props": {
            "pageProps": {
                "searchResult": {
                    "advertSummaryList": {
                        "advertSummary": adverts
                    }
                }
            }
        }
    }
    return f'<script id="__NEXT_DATA__">{json.dumps(data)}</script>'


class TestWillhabenScraper:

    def _scraper(self, settings=None):
        return WillhabenScraper(settings or {})

    def test_ist_base_scraper(self):
        assert isinstance(self._scraper(), BaseScraper)

    def test_attr_helper(self):
        attrs = [{"name": "HEADING", "values": ["Kinderwagen"]}, {"name": "PRICE", "values": ["50"]}]
        assert _attr(attrs, "HEADING") == "Kinderwagen"
        assert _attr(attrs, "MISSING") == ""

    def test_parse_felder(self):
        scraper = self._scraper()
        advert = _willhaben_advert()
        listing = scraper._parse(advert, "kinderwagen")
        assert listing is not None
        assert listing.platform == "Willhaben"
        assert listing.title == "Kinderwagen ABC"
        assert listing.price == "€ 50"
        assert listing.location == "Wien"
        assert listing.listing_id == "wh_12345"
        assert listing.url == "https://www.willhaben.at/iad/kaufen-und-verkaufen/d/kinderwagen-abc/12345/"
        assert listing.description == "Super Zustand"
        assert listing.image_url == "https://cache.willhaben.at/mmo/3/abc/1.jpg"
        assert listing.search_term == "kinderwagen"

    def test_parse_seo_url_absolut(self):
        scraper = self._scraper()
        advert = _willhaben_advert(seo_url="https://www.willhaben.at/iad/x/99/")
        listing = scraper._parse(advert, "test")
        assert listing.url == "https://www.willhaben.at/iad/x/99/"

    def test_parse_seo_url_mit_fuehrendem_slash(self):
        scraper = self._scraper()
        advert = _willhaben_advert(seo_url="/iad/kaufen-und-verkaufen/d/abc/99/")
        listing = scraper._parse(advert, "test")
        assert listing.url == "https://www.willhaben.at/iad/kaufen-und-verkaufen/d/abc/99/"

    def test_parse_image_absolut_bleibt_unveraendert(self):
        scraper = self._scraper()
        advert = _willhaben_advert(image="https://cdn.example.com/img.jpg")
        listing = scraper._parse(advert, "test")
        assert listing.image_url == "https://cdn.example.com/img.jpg"

    def test_parse_ohne_seo_url_fallback(self):
        scraper = self._scraper()
        advert = _willhaben_advert(seo_url="")
        listing = scraper._parse(advert, "test")
        assert listing.url == "https://www.willhaben.at/iad/kaufen-und-verkaufen/d/12345"

    def test_parse_fehlende_felder_kein_absturz(self):
        scraper = self._scraper()
        assert scraper._parse({}, "test") is not None

    def test_extract_adverts_parst_next_data(self):
        scraper = self._scraper()
        adverts = [_willhaben_advert()]
        html = _willhaben_html(adverts)
        result = scraper._extract_adverts(html)
        assert len(result) == 1

    def test_extract_adverts_kein_next_data(self):
        scraper = self._scraper()
        assert scraper._extract_adverts("<html>leer</html>") == []

    def test_extract_coords(self):
        scraper = self._scraper()
        advert = _willhaben_advert(coords="48.2083,16.3731")
        coords = scraper._extract_coords(advert)
        assert coords == (48.2083, 16.3731)

    def test_extract_coords_fehlt(self):
        scraper = self._scraper()
        advert = _willhaben_advert(coords="")
        assert scraper._extract_coords(advert) is None

    def test_search_gibt_listings_zurueck(self):
        scraper = self._scraper()
        html = _willhaben_html([_willhaben_advert()])
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            results = scraper.search("kinderwagen", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Kinderwagen ABC"

    def test_search_bei_exception(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", side_effect=Exception("Timeout")):
            assert scraper.search("kinderwagen") == []

    def test_search_paylivery_param_gesetzt(self):
        scraper = WillhabenScraper({"willhaben_paylivery_only": "1"})
        with patch.object(scraper.session, "get", return_value=_mock_response(text="<html></html>")) as mock_get:
            scraper.search("kinderwagen")
        params = mock_get.call_args[1]["params"]
        assert params.get("paylivery") == "true"

    def test_search_kein_paylivery_param_wenn_deaktiviert(self):
        scraper = WillhabenScraper({"willhaben_paylivery_only": "0"})
        with patch.object(scraper.session, "get", return_value=_mock_response(text="<html></html>")) as mock_get:
            scraper.search("kinderwagen")
        params = mock_get.call_args[1]["params"]
        assert "paylivery" not in params

    def test_search_max_price_in_params(self):
        scraper = WillhabenScraper({"willhaben_max_price": "80"})
        with patch.object(scraper.session, "get", return_value=_mock_response(text="<html></html>")) as mock_get:
            scraper.search("kinderwagen")
        params = mock_get.call_args[1]["params"]
        assert params.get("PRICE_TO") == 80

    def test_search_paylivery_ueberspringt_radius_filter(self):
        """PayLivery aktiviert → Radius-Filter wird nicht angewendet."""
        scraper = WillhabenScraper({
            "willhaben_paylivery_only": "1",
            "home_latitude": "48.1351",
            "home_longitude": "11.5820",
            "willhaben_radius": "50",
        })
        # Wien liegt ~600 km von München
        advert = _willhaben_advert(coords="48.2083,16.3731")
        html = _willhaben_html([advert])
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            results = scraper.search("kinderwagen")
        assert len(results) == 1

    def test_search_radius_filter_ohne_paylivery(self):
        """PayLivery deaktiviert + Radius → weit entfernte Items werden gefiltert."""
        scraper = WillhabenScraper({
            "willhaben_paylivery_only": "0",
            "home_latitude": "48.1351",
            "home_longitude": "11.5820",
            "willhaben_radius": "50",
        })
        # Wien liegt ~600 km von München
        advert = _willhaben_advert(coords="48.2083,16.3731")
        html = _willhaben_html([advert])
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            results = scraper.search("kinderwagen")
        assert results == []


# ── markt.de ─────────────────────────────────────────────────────────────────

MARKTDE_ITEM_HTML = """
<article class="clsy-c-result-list-item">
  <a class="clsy-c-result-list-item__link" href="/kinderwagen/12345/">Kinderwagen Bugaboo</a>
  <span class="clsy-c-result-list-item__price-amount">75 €</span>
  <span class="clsy-c-result-list-item__location">München</span>
  <div class="clsy-c-result-list-item__thumbnail">
    <img src="https://cdn.markt.de/img/12345.jpg" alt="Bild">
  </div>
  <p class="clsy-c-result-list-item__description">Sehr guter Zustand</p>
</article>
"""


def _marktde_page(items_html: str) -> str:
    return f"<html><body><div>{items_html}</div></body></html>"


class TestMarktdeScraper:

    def _scraper(self, settings=None):
        return MarktdeScraper(settings or {})

    def test_ist_base_scraper(self):
        assert isinstance(self._scraper(), BaseScraper)

    def test_city_slug_umlaut(self):
        assert _city_slug("München") == "muenchen"
        assert _city_slug("Köln") == "koeln"
        assert _city_slug("Düsseldorf") == "duesseldorf"
        assert _city_slug("Straße") == "strasse"

    def test_city_slug_leerzeichen(self):
        assert _city_slug("Bad Homburg") == "bad-homburg"

    def test_city_slug_lowercase(self):
        assert _city_slug("BERLIN") == "berlin"

    def test_parse_felder(self):
        from bs4 import BeautifulSoup
        scraper = self._scraper()
        item = BeautifulSoup(MARKTDE_ITEM_HTML, "lxml").select_one(".clsy-c-result-list-item")
        listing = scraper._parse(item, "kinderwagen")
        assert listing is not None
        assert listing.platform == "markt.de"
        assert listing.title == "Kinderwagen Bugaboo"
        assert listing.price == "75 €"
        assert listing.location == "München"
        assert listing.listing_id == "md_12345"
        assert listing.url == "https://www.markt.de/kinderwagen/12345/"
        assert listing.image_url == "https://cdn.markt.de/img/12345.jpg"
        assert listing.description == "Sehr guter Zustand"
        assert listing.search_term == "kinderwagen"

    def test_parse_ohne_link_gibt_none(self):
        from bs4 import BeautifulSoup
        scraper = self._scraper()
        item = BeautifulSoup("<article class='clsy-c-result-list-item'></article>", "lxml").select_one(".clsy-c-result-list-item")
        assert scraper._parse(item, "test") is None

    def test_search_gibt_listings_zurueck(self):
        scraper = MarktdeScraper({"marktde_location": "münchen"})
        html = _marktde_page(MARKTDE_ITEM_HTML)
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            results = scraper.search("kinderwagen", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Kinderwagen Bugaboo"

    def test_search_leere_ergebnisseite(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", return_value=_mock_response(text="<html></html>")):
            assert scraper.search("kinderwagen") == []

    def test_search_bei_exception(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", side_effect=Exception("Timeout")):
            assert scraper.search("kinderwagen") == []

    def test_search_max_price_filter(self):
        scraper = MarktdeScraper({"marktde_max_price": "50"})
        html = _marktde_page(MARKTDE_ITEM_HTML)  # Preis = 75 €, über 50 → gefiltert
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            results = scraper.search("kinderwagen")
        assert results == []

    def test_search_url_enthaelt_city_slug(self):
        scraper = MarktdeScraper({"marktde_location": "München"})
        with patch.object(scraper.session, "get", return_value=_mock_response(text="<html></html>")) as mock_get:
            scraper.search("kinderwagen")
        url = mock_get.call_args[0][0]
        assert "muenchen" in url

    def test_search_url_enthaelt_term(self):
        scraper = MarktdeScraper({"marktde_location": "Berlin"})
        with patch.object(scraper.session, "get", return_value=_mock_response(text="<html></html>")) as mock_get:
            scraper.search("baby stuhl")
        url = mock_get.call_args[0][0]
        assert "baby" in url.lower()
