"""Tests für app/crawler.py: run_crawl() Orchestrierung."""

import pytest
from unittest.mock import patch, MagicMock
from app.scrapers.base import Listing
import app.crawler as crawler_module


def make_listing(**kwargs) -> Listing:
    defaults = dict(
        platform="Test", title="Kinderwagen", price="50 €",
        location="München", url="https://example.com/1",
        listing_id="test-1", search_term="kinderwagen", description="",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


@pytest.fixture()
def patched_db(tmp_path, monkeypatch):
    """Frische DB + monkeypatcht DB_PATH im database-Modul."""
    import app.database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db


# ── Basis-Orchestrierung ─────────────────────────────────────

_BASE_SETTINGS = {
    "kleinanzeigen_enabled": "1",
    "shpock_enabled": "0", "facebook_enabled": "0",
    "vinted_enabled": "0", "ebay_enabled": "0",
    "crawler_delay": "0", "crawler_max_results": "5",
    "crawler_blacklist": "",
}


class TestRunCrawlOrchestration:

    def test_kein_suchbegriff_gibt_no_terms_zurueck(self, patched_db):
        patched_db.set_setting("kleinanzeigen_enabled", "1")
        for t in patched_db.get_search_terms():
            patched_db.delete_search_term(t["id"])

        with patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[]), \
             patch("app.crawler.db.set_setting"):
            result = crawler_module.run_crawl("kleinanzeigen")
        assert result["status"] == "no_terms"

    def test_keine_plattform_gibt_no_platforms_zurueck(self, patched_db):
        with patch("app.crawler.db.get_settings", return_value={
            **_BASE_SETTINGS, "kleinanzeigen_enabled": "0"
        }), patch("app.crawler.db.set_setting"):
            result = crawler_module.run_crawl("kleinanzeigen")
        assert result["status"] == "no_platforms"

    def test_crawl_setzt_status_auf_running_dann_idle(self, patched_db):
        statuses = []

        def tracking_set_setting(key, value):
            if key == "crawl_status":
                statuses.append(value)

        mock_scraper = MagicMock()
        mock_scraper.search.return_value = []

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=False), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting", side_effect=tracking_set_setting):
            crawler_module.run_crawl("kleinanzeigen")

        assert "running" in statuses
        assert statuses[-1] == "idle"

    def test_neue_listings_werden_gespeichert(self, patched_db):
        listing = make_listing(listing_id="new-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True) as mock_save, \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")

        assert result["new"] == 1
        mock_save.assert_called_once()

    def test_blacklist_filtert_listings_heraus(self, patched_db):
        listing = make_listing(title="defekter Kinderwagen", listing_id="bl-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={**_BASE_SETTINGS, "crawler_blacklist": "defekt"}), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True) as mock_save, \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")

        assert result["new"] == 0
        assert result["skipped_blacklist"] == 1
        mock_save.assert_not_called()

    def test_aktivierter_sprachfilter_filtert_listing_vor_dem_speichern(self, patched_db):
        listing = make_listing(title="Poussette bébé en très bon état", listing_id="lang-fr-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]
        mock_scraper.enrich_listing.return_value = listing

        settings = {
            **_BASE_SETTINGS,
            "crawler_lang_filter_enabled": "1",
            "crawler_lang_filter_langs": "de",
        }
        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=settings), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "bébé"}]), \
             patch("app.crawler._is_lang_allowed", return_value=False) as mock_lang_allowed, \
             patch("app.crawler.db.save_listing", return_value=True) as mock_save, \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")

        assert result["new"] == 0
        assert result["skipped_lang"] == 1
        mock_scraper.enrich_listing.assert_called_once_with(listing)
        mock_lang_allowed.assert_called_once_with(listing, ["de"])
        mock_save.assert_not_called()

    def test_bekanntes_listing_wird_nicht_erneut_angereichert(self, patched_db):
        listing = make_listing(listing_id="known-lang-1")
        assert patched_db.save_listing(listing) is True
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]
        settings = {
            **_BASE_SETTINGS,
            "crawler_lang_filter_enabled": "1",
            "crawler_lang_filter_langs": "de",
        }

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=settings), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")

        assert result["new"] == 0
        mock_scraper.enrich_listing.assert_not_called()

    def test_deaktivierter_sprachfilter_prueft_sprache_nicht(self, patched_db):
        listing = make_listing(listing_id="lang-off-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler._is_lang_allowed") as mock_lang_allowed, \
             patch("app.crawler.db.save_listing", return_value=True) as mock_save, \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")

        assert result["new"] == 1
        assert result["skipped_lang"] == 0
        mock_lang_allowed.assert_not_called()
        mock_save.assert_called_once()

    def test_gratis_listings_werden_gezaehlt(self, patched_db):
        listing = make_listing(listing_id="free-1", price="0 €")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")

        assert result["free"] >= 1

    def test_scraper_fehler_inkrementiert_errors(self, patched_db):
        mock_scraper = MagicMock()
        mock_scraper.search.side_effect = RuntimeError("API kaputt")

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=False), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")

        assert result["errors"] >= 1
        assert result["status"] == "ok"

    def test_notify_wird_nur_bei_neuen_listings_aufgerufen(self, patched_db):
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = []

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=False), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify") as mock_notify:
            crawler_module.run_crawl("kleinanzeigen")

        mock_notify.assert_not_called()

    def test_notify_wird_bei_auto_crawl_nicht_aufgerufen(self, patched_db):
        listing = make_listing(listing_id="notify-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify") as mock_notify:
            crawler_module.run_crawl("kleinanzeigen")  # auto crawl

        mock_notify.assert_not_called()

    def test_notify_wird_bei_manuellem_crawl_aufgerufen(self, patched_db):
        listing = make_listing(listing_id="notify-manual-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify") as mock_notify:
            crawler_module.run_crawl("kleinanzeigen", manual=True)

        mock_notify.assert_called_once()

    def test_entfernung_wird_berechnet_wenn_location_vorhanden(self, patched_db):
        listing = make_listing(listing_id="dist-1", location="Augsburg")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.distance_to_home", return_value=55.3) as mock_dist, \
             patch("app.crawler.db.update_listing_distance") as mock_update, \
             patch("app.crawler.notify"):
            crawler_module.run_crawl("kleinanzeigen")

        mock_dist.assert_called_once()
        mock_update.assert_called_once()

    def test_entfernung_fehler_bricht_crawl_nicht_ab(self, patched_db):
        listing = make_listing(listing_id="dist-err-1", location="Unbekannt")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.distance_to_home", side_effect=RuntimeError("Geo kaputt")), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")

        assert result["new"] == 1


# ── Per-Term Preisfilter ──────────────────────────────────────

class TestPerTermPreisfilter:

    def _run_with_listing(self, listing, term_max_price=None):
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]
        term = {"term": "kinderwagen"}
        if term_max_price is not None:
            term["max_price"] = term_max_price

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[term]), \
             patch("app.crawler.db.save_listing", return_value=True) as mock_save, \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl("kleinanzeigen")
        return result, mock_save

    def test_kein_limit_speichert_alle(self, patched_db):
        listing = make_listing(price="200 €", listing_id="price-none-1")
        result, mock_save = self._run_with_listing(listing, term_max_price=None)
        assert result["new"] == 1
        mock_save.assert_called_once()

    def test_listing_unter_limit_gespeichert(self, patched_db):
        listing = make_listing(price="30 €", listing_id="price-ok-1")
        result, _ = self._run_with_listing(listing, term_max_price=50)
        assert result["new"] == 1

    def test_listing_ueber_limit_wird_gefiltert(self, patched_db):
        listing = make_listing(price="80 €", listing_id="price-skip-1")
        result, mock_save = self._run_with_listing(listing, term_max_price=50)
        assert result["new"] == 0
        mock_save.assert_not_called()

    def test_gratispreis_passiert_filter(self, patched_db):
        listing = make_listing(price="0 €", listing_id="price-free-1")
        result, _ = self._run_with_listing(listing, term_max_price=50)
        assert result["new"] == 1


# ── Double-Run-Schutz ─────────────────────────────────────────

class TestRunCrawlLock:

    def test_is_running_false_initial(self):
        assert crawler_module.is_running() is False

    def test_is_running_mit_plattform_false_initial(self):
        assert crawler_module.is_running("kleinanzeigen") is False

    def test_bereits_laufend_gibt_already_running_zurueck(self, patched_db):
        crawler_module._running.add("kleinanzeigen")
        try:
            result = crawler_module.run_crawl("kleinanzeigen")
            assert result["status"] == "already_running"
        finally:
            crawler_module._running.discard("kleinanzeigen")

    def test_run_crawl_async_gibt_thread_zurueck(self, patched_db):
        import threading
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = []

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=False), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify"):
            t = crawler_module.run_crawl_async("kleinanzeigen")
            assert isinstance(t, threading.Thread)
            t.join(timeout=5)


# ── Race-Condition-Fix: kein globaler last_crawl_found ────────

class TestLastCrawlFoundPerPlatform:
    """Crawl schreibt last_crawl_found nur per Plattform, nicht global."""

    def _run_with_mock(self, patched_db):
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [
            make_listing(listing_id="rc-1"),
        ]
        written_keys = []

        def capture_set_setting(key, value):
            written_keys.append(key)

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value=_BASE_SETTINGS), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen", "max_price": None}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting", side_effect=capture_set_setting), \
             patch("app.crawler.notify"):
            crawler_module.run_crawl("kleinanzeigen")
        return written_keys

    def test_kein_globaler_last_crawl_found_key(self, patched_db):
        keys = self._run_with_mock(patched_db)
        assert "last_crawl_found" not in keys

    def test_plattform_last_crawl_found_wird_gesetzt(self, patched_db):
        keys = self._run_with_mock(patched_db)
        assert "kleinanzeigen_last_crawl_found" in keys
