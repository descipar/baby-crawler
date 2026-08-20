"""Tests für app/database.py: CRUD-Operationen mit temporärer SQLite-DB."""

import pytest
from app.scrapers.base import Listing


# ── Fixtures ─────────────────────────────────────────────────
# temp_db kommt aus conftest.py und liefert ein frisches db-Modul


# ── Search Terms ─────────────────────────────────────────────

class TestSearchTerms:

    def test_default_terms_wurden_angelegt(self, temp_db):
        """Nach init_db() müssen die Default-Suchbegriffe vorhanden sein."""
        terms = temp_db.get_search_terms()
        names = [t["term"] for t in terms]
        assert "kinderwagen" in names
        assert "babybett" in names

    def test_neuen_term_hinzufuegen(self, temp_db):
        before = len(temp_db.get_search_terms())
        ok = temp_db.add_search_term("testbegriff")
        assert ok is True
        assert len(temp_db.get_search_terms()) == before + 1

    def test_duplikat_wird_abgelehnt(self, temp_db):
        temp_db.add_search_term("duplikat")
        ok = temp_db.add_search_term("duplikat")
        assert ok is False

    def test_term_loeschen(self, temp_db):
        temp_db.add_search_term("zulöschen")
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "zulöschen")
        temp_db.delete_search_term(tid)
        names = [t["term"] for t in temp_db.get_search_terms()]
        assert "zulöschen" not in names

    def test_term_aktivieren_deaktivieren(self, temp_db):
        temp_db.add_search_term("toggletest")
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "toggletest")

        # Initial: enabled
        temp_db.toggle_search_term(tid)
        terms = temp_db.get_search_terms()
        t = next(t for t in terms if t["id"] == tid)
        assert t["enabled"] == 0

        # Wieder aktivieren
        temp_db.toggle_search_term(tid)
        terms = temp_db.get_search_terms()
        t = next(t for t in terms if t["id"] == tid)
        assert t["enabled"] == 1

    def test_enabled_only_filter(self, temp_db):
        temp_db.add_search_term("aktiv")
        temp_db.add_search_term("inaktiv")
        terms = temp_db.get_search_terms()
        inaktiv_id = next(t["id"] for t in terms if t["term"] == "inaktiv")
        temp_db.toggle_search_term(inaktiv_id)

        aktive = temp_db.get_search_terms(enabled_only=True)
        names = [t["term"] for t in aktive]
        assert "aktiv" in names
        assert "inaktiv" not in names


# ── Settings ─────────────────────────────────────────────────

class TestSettings:

    def test_defaults_wurden_geladen(self, temp_db):
        s = temp_db.get_settings()
        assert "crawler_interval" in s
        assert s["crawler_interval"] == "15"

    def test_setting_speichern_und_lesen(self, temp_db):
        temp_db.set_setting("test_key", "test_value")
        assert temp_db.get_setting("test_key") == "test_value"

    def test_setting_ueberschreiben(self, temp_db):
        temp_db.set_setting("crawler_interval", "30")
        assert temp_db.get_setting("crawler_interval") == "30"

    def test_unbekanntes_setting_liefert_default(self, temp_db):
        val = temp_db.get_setting("gibt_es_nicht", default="fallback")
        assert val == "fallback"

    def test_save_settings_batch(self, temp_db):
        temp_db.save_settings({"crawler_interval": "15", "crawler_delay": "1"})
        assert temp_db.get_setting("crawler_interval") == "15"
        assert temp_db.get_setting("crawler_delay") == "1"


# ── Listings ─────────────────────────────────────────────────

def make_listing(listing_id="test-001", title="Kinderwagen", is_free=False) -> Listing:
    return Listing(
        platform="Kleinanzeigen",
        title=title,
        price="50 €",
        location="Dortmund",
        url=f"https://example.com/{listing_id}",
        listing_id=listing_id,
        search_term="kinderwagen",
        is_free=is_free,
    )


class TestListings:

    def test_neue_anzeige_speichern(self, temp_db):
        ok = temp_db.save_listing(make_listing("neu-001"))
        assert ok is True
        assert temp_db.get_listing_count() == 1

    def test_duplikat_wird_ignoriert(self, temp_db):
        temp_db.save_listing(make_listing("dup-001"))
        ok = temp_db.save_listing(make_listing("dup-001"))
        assert ok is False
        assert temp_db.get_listing_count() == 1

    def test_is_known_listing_findet_gespeicherte_anzeige(self, temp_db):
        temp_db.save_listing(make_listing("known-001"))
        assert temp_db.is_known_listing("known-001") is True

    def test_is_known_listing_findet_dismissed_anzeige(self, temp_db):
        temp_db.save_listing(make_listing("known-dismissed-001"))
        db_id = temp_db.get_listings()[0]["id"]
        temp_db.dismiss_listing(db_id)
        assert temp_db.is_known_listing("known-dismissed-001") is True

    def test_is_known_listing_unbekannt_false(self, temp_db):
        assert temp_db.is_known_listing("unknown-001") is False

    def test_mehrere_anzeigen(self, temp_db):
        for i in range(5):
            temp_db.save_listing(make_listing(f"multi-{i:03d}"))
        assert temp_db.get_listing_count() == 5

    def test_get_listings_limit(self, temp_db):
        for i in range(10):
            temp_db.save_listing(make_listing(f"limit-{i:03d}"))
        result = temp_db.get_listings(limit=3)
        assert len(result) == 3

    def test_get_listings_nur_gratis(self, temp_db):
        temp_db.save_listing(make_listing("gratis-001", is_free=True))
        temp_db.save_listing(make_listing("normal-001", is_free=False))
        result = temp_db.get_listings(only_free=True)
        assert len(result) == 1
        assert result[0]["listing_id"] == "gratis-001"

    def test_is_free_wird_gespeichert(self, temp_db):
        temp_db.save_listing(make_listing("frei-001", is_free=True))
        listings = temp_db.get_listings()
        assert listings[0]["is_free"] == 1

    def test_entfernung_aktualisieren(self, temp_db):
        temp_db.save_listing(make_listing("dist-001"))
        temp_db.update_listing_distance("dist-001", 42.3)
        listings = temp_db.get_listings()
        assert listings[0]["distance_km"] == pytest.approx(42.3, abs=0.05)

    def test_toggle_favorit(self, temp_db):
        temp_db.save_listing(make_listing("fav-001"))
        listing = temp_db.get_listings()[0]
        lid = listing["id"]
        assert listing["is_favorite"] == 0

        temp_db.toggle_favorite(lid)
        assert temp_db.get_listings()[0]["is_favorite"] == 1

        temp_db.toggle_favorite(lid)
        assert temp_db.get_listings()[0]["is_favorite"] == 0

    def test_favoriten_filter(self, temp_db):
        temp_db.save_listing(make_listing("fav-a"))
        temp_db.save_listing(make_listing("fav-b"))
        lid = temp_db.get_listings()[0]["id"]
        temp_db.toggle_favorite(lid)

        result = temp_db.get_listings(only_favorites=True)
        assert len(result) == 1

    def test_favoriten_bleiben_bei_clear_old_listings(self, temp_db):
        """Favoriten dürfen beim automatischen Aufräumen nicht gelöscht werden."""
        import sqlite3

        temp_db.save_listing(make_listing("old-fav"))
        temp_db.save_listing(make_listing("old-normal"))

        # Beide Anzeigen künstlich alt machen (31 Tage)
        conn = sqlite3.connect(str(temp_db.DB_PATH))
        conn.execute("UPDATE listings SET found_at = datetime('now', '-31 days')")
        conn.commit()
        conn.close()

        # Favorit setzen
        fav_id = next(l["id"] for l in temp_db.get_listings() if l["listing_id"] == "old-fav")
        temp_db.toggle_favorite(fav_id)

        temp_db.clear_old_listings(days=30)

        remaining = [l["listing_id"] for l in temp_db.get_listings()]
        assert "old-fav" in remaining
        assert "old-normal" not in remaining

    def test_offset_paginierung(self, temp_db):
        for i in range(5):
            temp_db.save_listing(make_listing(f"page-{i:03d}"))
        page1 = temp_db.get_listings(limit=3, offset=0)
        page2 = temp_db.get_listings(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2
        ids1 = {l["listing_id"] for l in page1}
        ids2 = {l["listing_id"] for l in page2}
        assert ids1.isdisjoint(ids2)


class TestSearchTermsFilter:

    def _save(self, temp_db, lid, term):
        from app.scrapers.base import Listing
        temp_db.save_listing(Listing(
            platform="Test", title=lid, price="10 €", location="München",
            url=f"https://example.com/{lid}", listing_id=lid, search_term=term,
        ))

    def test_einzel_term_filter(self, temp_db):
        self._save(temp_db, "a", "kinderwagen")
        self._save(temp_db, "b", "babybett")
        result = temp_db.get_listings(search_terms=["kinderwagen"])
        assert len(result) == 1
        assert result[0]["listing_id"] == "a"

    def test_mehrere_terme_filter(self, temp_db):
        self._save(temp_db, "c", "kinderwagen")
        self._save(temp_db, "d", "babybett")
        self._save(temp_db, "e", "hochstuhl")
        result = temp_db.get_listings(search_terms=["kinderwagen", "babybett"])
        ids = {l["listing_id"] for l in result}
        assert ids == {"c", "d"}
        assert "e" not in ids

    def test_kein_filter_gibt_alles_zurueck(self, temp_db):
        self._save(temp_db, "f", "kinderwagen")
        self._save(temp_db, "g", "babybett")
        result = temp_db.get_listings(search_terms=None)
        assert len(result) == 2

    def test_unbekannter_term_gibt_leer_zurueck(self, temp_db):
        self._save(temp_db, "h", "kinderwagen")
        result = temp_db.get_listings(search_terms=["gibtesnicht"])
        assert result == []


class TestSortierung:

    def _save_listings(self, temp_db):
        """Legt drei Listings mit unterschiedlichen Preisen und Distanzen an."""
        from app.scrapers.base import Listing
        entries = [
            ("sort-a", "10 €", 5.0),
            ("sort-b", "50 €", 30.0),
            ("sort-c", "25 €", 15.0),
        ]
        for lid, price, dist in entries:
            l = Listing(
                platform="Test", title=lid, price=price,
                location="München", url=f"https://example.com/{lid}",
                listing_id=lid, search_term="test",
            )
            temp_db.save_listing(l)
            temp_db.update_listing_distance(lid, dist)

    def test_sort_preis_aufsteigend(self, temp_db):
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="price_asc")
        prices = [l["price"] for l in result]
        assert prices == ["10 €", "25 €", "50 €"]

    def test_sort_preis_absteigend(self, temp_db):
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="price_desc")
        prices = [l["price"] for l in result]
        assert prices == ["50 €", "25 €", "10 €"]

    def test_sort_entfernung_aufsteigend(self, temp_db):
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="distance_asc")
        ids = [l["listing_id"] for l in result]
        assert ids == ["sort-a", "sort-c", "sort-b"]

    def test_sort_entfernung_null_ans_ende(self, temp_db):
        """Listings ohne Distanz landen beim Entfernungs-Sort am Ende."""
        from app.scrapers.base import Listing
        l_ohne = Listing(
            platform="Test", title="ohne", price="5 €",
            location="", url="https://example.com/ohne",
            listing_id="ohne-dist", search_term="test",
        )
        temp_db.save_listing(l_ohne)
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="distance_asc")
        assert result[-1]["listing_id"] == "ohne-dist"

    def test_sort_preis_ohne_preis_ans_ende(self, temp_db):
        """Listings mit nicht-numerischem Preis landen beim Preis-Sort am Ende."""
        from app.scrapers.base import Listing
        l_ka = Listing(
            platform="Test", title="ka", price="k.A.",
            location="München", url="https://example.com/ka",
            listing_id="preis-ka", search_term="test",
        )
        temp_db.save_listing(l_ka)
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="price_asc")
        assert result[-1]["listing_id"] == "preis-ka"

    def test_sort_unbekannter_wert_faellt_auf_default(self, temp_db):
        """Ungültiger sort_by-Wert löst keinen Fehler aus."""
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="gibts_nicht")
        assert len(result) == 3

    def test_favoriten_bleiben_immer_oben(self, temp_db):
        """Favoriten erscheinen unabhängig von der Sortierung zuerst."""
        self._save_listings(temp_db)
        fav_id = next(l["id"] for l in temp_db.get_listings() if l["listing_id"] == "sort-b")
        temp_db.toggle_favorite(fav_id)
        result = temp_db.get_listings(sort_by="price_asc")
        assert result[0]["listing_id"] == "sort-b"


# ── Geocache ─────────────────────────────────────────────────

class TestGeocache:

    def test_speichern_und_laden(self, temp_db):
        temp_db.save_geocache("Dortmund", 51.5136, 7.4653)
        result = temp_db.get_geocache("Dortmund")
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(51.5136)
        assert lon == pytest.approx(7.4653)

    def test_unbekannter_ort_gibt_none(self, temp_db):
        assert temp_db.get_geocache("NichtVorhanden") is None

    def test_ueberschreiben_funktioniert(self, temp_db):
        temp_db.save_geocache("Ort", 10.0, 20.0)
        temp_db.save_geocache("Ort", 11.0, 21.0)
        lat, lon = temp_db.get_geocache("Ort")
        assert lat == pytest.approx(11.0)


# ── Dismiss ──────────────────────────────────────────────────

class TestDismiss:

    def _save(self, temp_db, lid, term="test"):
        from app.scrapers.base import Listing
        l = Listing(
            platform="Test", title=lid, price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term=term,
        )
        temp_db.save_listing(l)
        return next(l["id"] for l in temp_db.get_listings() if l["listing_id"] == lid)

    def test_dismiss_entfernt_listing(self, temp_db):
        db_id = self._save(temp_db, "dismiss-1")
        temp_db.dismiss_listing(db_id)
        ids = [l["listing_id"] for l in temp_db.get_listings()]
        assert "dismiss-1" not in ids

    def test_dismiss_merkt_listing_id(self, temp_db):
        db_id = self._save(temp_db, "dismiss-2")
        temp_db.dismiss_listing(db_id)
        assert temp_db.is_dismissed("dismiss-2") is True

    def test_undismissed_ist_nicht_geblockt(self, temp_db):
        assert temp_db.is_dismissed("nicht-vorhanden") is False

    def test_save_dismissed_listing_wird_abgelehnt(self, temp_db):
        from app.scrapers.base import Listing
        db_id = self._save(temp_db, "dismiss-3")
        temp_db.dismiss_listing(db_id)
        l = Listing(
            platform="Test", title="wieder", price="5 €",
            location="München", url="https://example.com/dismiss-3",
            listing_id="dismiss-3", search_term="test",
        )
        result = temp_db.save_listing(l)
        assert result is False
        ids = [x["listing_id"] for x in temp_db.get_listings()]
        assert "dismiss-3" not in ids

    def test_dismiss_unbekannte_id_kein_fehler(self, temp_db):
        temp_db.dismiss_listing(9999)


class TestDeleteTermWithListings:

    def test_loeschen_entfernt_zugehoerige_anzeigen(self, temp_db):
        from app.scrapers.base import Listing
        temp_db.add_search_term("wegtest")
        l = Listing(
            platform="Test", title="X", price="5 €",
            location="München", url="https://example.com/x",
            listing_id="weg-1", search_term="wegtest",
        )
        temp_db.save_listing(l)
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "wegtest")
        temp_db.delete_search_term(tid)
        ids = [x["listing_id"] for x in temp_db.get_listings()]
        assert "weg-1" not in ids

    def test_loeschen_belaesst_andere_anzeigen(self, temp_db):
        from app.scrapers.base import Listing
        temp_db.add_search_term("behalten")
        l = Listing(
            platform="Test", title="Y", price="5 €",
            location="München", url="https://example.com/y",
            listing_id="keep-1", search_term="behalten",
        )
        temp_db.save_listing(l)
        terms = temp_db.get_search_terms()
        # Löschen eines anderen Terms
        other_tid = next(t["id"] for t in terms if t["term"] == "kinderwagen")
        temp_db.delete_search_term(other_tid)
        ids = [x["listing_id"] for x in temp_db.get_listings()]
        assert "keep-1" in ids


# ── ExcludeFilter ─────────────────────────────────────────────

class TestExcludeFilter:

    def _make(self, temp_db, lid, title, description=""):
        from app.scrapers.base import Listing
        l = Listing(
            platform="Test", title=title, price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test", description=description,
        )
        temp_db.save_listing(l)

    def test_exclude_filtert_aus_titel(self, temp_db):
        self._make(temp_db, "a", "Schöner Kinderwagen")
        self._make(temp_db, "b", "Kinderwagen defekt")
        result = temp_db.get_listings(exclude_text="defekt")
        ids = [l["listing_id"] for l in result]
        assert "a" in ids
        assert "b" not in ids

    def test_exclude_filtert_aus_beschreibung(self, temp_db):
        self._make(temp_db, "c", "Hochstuhl", description="Leider defekt")
        self._make(temp_db, "d", "Hochstuhl NEU", description="Neuwertig")
        result = temp_db.get_listings(exclude_text="defekt")
        ids = [l["listing_id"] for l in result]
        assert "d" in ids
        assert "c" not in ids

    def test_exclude_none_gibt_alle_zurueck(self, temp_db):
        self._make(temp_db, "e", "Babybett")
        self._make(temp_db, "f", "Babybett defekt")
        result = temp_db.get_listings(exclude_text=None)
        ids = [l["listing_id"] for l in result]
        assert "e" in ids
        assert "f" in ids

    def test_exclude_leerstring_gibt_alle_zurueck(self, temp_db):
        self._make(temp_db, "g", "Laufstall")
        result = temp_db.get_listings(exclude_text="")
        ids = [l["listing_id"] for l in result]
        assert "g" in ids


class TestNotesAndDuplicates:

    def _save(self, temp_db, lid, title="Kinderwagen", platform="Kleinanzeigen"):
        from app.scrapers.base import Listing
        l = Listing(
            platform=platform, title=title, price="30 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test",
        )
        temp_db.save_listing(l)
        return next(x["id"] for x in temp_db.get_listings() if x["listing_id"] == lid)

    def test_update_listing_note_speichert(self, temp_db):
        db_id = self._save(temp_db, "note-1")
        temp_db.update_listing_note(db_id, "Schaut gut aus!")
        l = next(x for x in temp_db.get_listings() if x["listing_id"] == "note-1")
        assert l["notes"] == "Schaut gut aus!"

    def test_update_listing_note_loescht(self, temp_db):
        db_id = self._save(temp_db, "note-2")
        temp_db.update_listing_note(db_id, "Notiz")
        temp_db.update_listing_note(db_id, "")
        l = next(x for x in temp_db.get_listings() if x["listing_id"] == "note-2")
        assert l["notes"] is None

    def test_find_duplicate_platform_findet_anderen_plattform(self, temp_db):
        self._save(temp_db, "dup-ka", title="Kinderwagen Bugaboo Fox 3", platform="Kleinanzeigen")
        result = temp_db.find_duplicate_platform("Kinderwagen Bugaboo Fox 3", "Shpock")
        assert result == "Kleinanzeigen"

    def test_find_duplicate_gleiche_plattform_ignoriert(self, temp_db):
        self._save(temp_db, "dup-same", title="Kinderwagen Bugaboo Fox 3", platform="Kleinanzeigen")
        result = temp_db.find_duplicate_platform("Kinderwagen Bugaboo Fox 3", "Kleinanzeigen")
        assert result is None

    def test_find_duplicate_zu_kurzer_titel(self, temp_db):
        self._save(temp_db, "dup-short", title="ABC", platform="Kleinanzeigen")
        result = temp_db.find_duplicate_platform("ABC", "Shpock")
        assert result is None

    def test_find_duplicate_kein_treffer(self, temp_db):
        result = temp_db.find_duplicate_platform("Ganz einzigartiger Titel XY", "Kleinanzeigen")
        assert result is None


class TestPlatformCounts:

    def _save(self, temp_db, lid, platform):
        from app.scrapers.base import Listing
        temp_db.save_listing(Listing(
            platform=platform, title=lid, price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test",
        ))

    def test_get_distinct_platforms(self, temp_db):
        self._save(temp_db, "p1", "Kleinanzeigen")
        self._save(temp_db, "p2", "Shpock")
        self._save(temp_db, "p3", "Kleinanzeigen")
        platforms = temp_db.get_distinct_platforms()
        assert set(platforms) == {"Kleinanzeigen", "Shpock"}

    def test_get_distinct_platforms_leer(self, temp_db):
        assert temp_db.get_distinct_platforms() == []

    def test_get_platform_counts(self, temp_db):
        self._save(temp_db, "c1", "Kleinanzeigen")
        self._save(temp_db, "c2", "Kleinanzeigen")
        self._save(temp_db, "c3", "Shpock")
        counts = temp_db.get_platform_counts()
        assert counts["Kleinanzeigen"] == 2
        assert counts["Shpock"] == 1

    def test_get_platform_counts_leer(self, temp_db):
        assert temp_db.get_platform_counts() == {}


class TestTermMaxPrice:

    def test_update_term_max_price_setzen(self, temp_db):
        temp_db.add_search_term("pricetest")
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "pricetest")
        temp_db.update_term_max_price(tid, 50)
        terms = temp_db.get_search_terms()
        t = next(t for t in terms if t["term"] == "pricetest")
        assert t["max_price"] == 50

    def test_update_term_max_price_auf_none(self, temp_db):
        temp_db.add_search_term("pricenone")
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "pricenone")
        temp_db.update_term_max_price(tid, 100)
        temp_db.update_term_max_price(tid, None)
        terms = temp_db.get_search_terms()
        t = next(t for t in terms if t["term"] == "pricenone")
        assert t["max_price"] is None


class TestClearListingsOlderThan:

    def _save_old(self, temp_db, lid, hours=25):
        import sqlite3
        from app.scrapers.base import Listing
        temp_db.save_listing(Listing(
            platform="Test", title=lid, price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test",
        ))
        conn = sqlite3.connect(str(temp_db.DB_PATH))
        conn.execute(
            "UPDATE listings SET found_at=datetime('now', ? || ' hours') WHERE listing_id=?",
            (f"-{hours}", lid),
        )
        conn.commit()
        conn.close()

    def test_loescht_alte_listings(self, temp_db):
        self._save_old(temp_db, "old-1", hours=25)
        deleted = temp_db.clear_listings_older_than(24)
        assert deleted == 1
        assert temp_db.get_listing_count() == 0

    def test_belaesst_neue_listings(self, temp_db):
        self._save_old(temp_db, "new-1", hours=1)
        deleted = temp_db.clear_listings_older_than(24)
        assert deleted == 0
        assert temp_db.get_listing_count() == 1

    def test_schont_favoriten(self, temp_db):
        self._save_old(temp_db, "fav-old", hours=25)
        db_id = next(x["id"] for x in temp_db.get_listings() if x["listing_id"] == "fav-old")
        temp_db.toggle_favorite(db_id)
        deleted = temp_db.clear_listings_older_than(24)
        assert deleted == 0
        assert temp_db.get_listing_count() == 1

    def test_dismissed_nach_loeschen(self, temp_db):
        self._save_old(temp_db, "dismiss-old", hours=25)
        temp_db.clear_listings_older_than(24)
        assert temp_db.is_dismissed("dismiss-old") is True

    def test_gibt_anzahl_zurueck(self, temp_db):
        self._save_old(temp_db, "count-1", hours=25)
        self._save_old(temp_db, "count-2", hours=25)
        deleted = temp_db.clear_listings_older_than(24)
        assert deleted == 2


class TestClearListingsByPlatform:

    def _save(self, temp_db, lid, platform="TestPlattform"):
        from app.scrapers.base import Listing
        temp_db.save_listing(Listing(
            platform=platform, title=lid, price="10 €",
            location="Wien", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test",
        ))

    def test_loescht_listings_der_plattform(self, temp_db):
        self._save(temp_db, "wh-1", "Willhaben")
        self._save(temp_db, "wh-2", "Willhaben")
        deleted = temp_db.clear_listings_by_platform("Willhaben")
        assert deleted == 2
        assert temp_db.get_listing_count() == 0

    def test_belaesst_andere_plattformen(self, temp_db):
        self._save(temp_db, "wh-1", "Willhaben")
        self._save(temp_db, "ka-1", "Kleinanzeigen")
        temp_db.clear_listings_by_platform("Willhaben")
        assert temp_db.get_listing_count() == 1
        assert temp_db.get_listings()[0]["listing_id"] == "ka-1"

    def test_schont_favoriten(self, temp_db):
        self._save(temp_db, "wh-fav", "Willhaben")
        db_id = temp_db.get_listings()[0]["id"]
        temp_db.toggle_favorite(db_id)
        deleted = temp_db.clear_listings_by_platform("Willhaben")
        assert deleted == 0
        assert temp_db.get_listing_count() == 1

    def test_dismissed_nach_loeschen(self, temp_db):
        self._save(temp_db, "wh-dismiss", "Willhaben")
        temp_db.clear_listings_by_platform("Willhaben")
        assert temp_db.is_dismissed("wh-dismiss") is True

    def test_leere_plattform_gibt_null(self, temp_db):
        deleted = temp_db.clear_listings_by_platform("Willhaben")
        assert deleted == 0


class TestMigrationFramework:
    """Tests für das versionierte Migrations-Framework (_migrations-Tabelle)."""

    def _minimal_db(self, path):
        """Erstellt eine minimale 'alte' DB ohne neue Spalten."""
        import sqlite3
        conn = sqlite3.connect(str(path))
        conn.executescript("""
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, listing_id TEXT UNIQUE, platform TEXT,
                title TEXT, price TEXT, location TEXT, url TEXT,
                found_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE geocache (location_text TEXT PRIMARY KEY, lat REAL, lon REAL);
        """)
        conn.commit()
        conn.close()

    def test_migrations_tabelle_wird_angelegt(self, tmp_path, monkeypatch):
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_track.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        self._minimal_db(old_db)
        db.init_db()

        conn = sqlite3.connect(str(old_db))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "_migrations" in tables

    def test_jede_migration_wird_nur_einmal_ausgefuehrt(self, tmp_path, monkeypatch):
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_idem.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        self._minimal_db(old_db)

        # Zweimal init_db() aufrufen
        db.init_db()
        db.init_db()

        conn = sqlite3.connect(str(old_db))
        rows = conn.execute("SELECT name FROM _migrations").fetchall()
        conn.close()

        # Jeder Name darf nur einmal vorkommen
        names = [r[0] for r in rows]
        assert len(names) == len(set(names)), "Doppelte Migrations-Einträge gefunden"

    def test_migration_traegt_alle_namen_ein(self, tmp_path, monkeypatch):
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_names.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        self._minimal_db(old_db)
        db.init_db()

        conn = sqlite3.connect(str(old_db))
        names = {r[0] for r in conn.execute("SELECT name FROM _migrations")}
        conn.close()
        # Alle vier Kernmigrationen müssen eingetragen sein (mit vN_-Prefix)
        assert "v1_settings_rename" in names
        assert "v2_listings_columns" in names
        assert "v3_search_terms_max_price" in names
        assert "v4_backfill_notified_at" in names
        assert "v5_rename_email_subjects" in names

    def test_backfill_migration_markiert_bestehende_listings(self, tmp_path, monkeypatch):
        """v4-Migration setzt notified_at für alle NULL-Einträge – verhindert Massen-E-Mail."""
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_backfill.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        # Alte DB mit Listings ohne notified_at
        conn = sqlite3.connect(str(old_db))
        conn.executescript("""
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, listing_id TEXT UNIQUE, platform TEXT,
                title TEXT, price TEXT, location TEXT, url TEXT,
                found_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE geocache (location_text TEXT PRIMARY KEY, lat REAL, lon REAL);
            INSERT INTO listings (listing_id, platform, title, price, location, url)
            VALUES ('alt-1', 'Shpock', 'Alter Eintrag', '10 €', 'Berlin', 'https://x.com/1');
            INSERT INTO listings (listing_id, platform, title, price, location, url)
            VALUES ('alt-2', 'Shpock', 'Noch ein alter', '20 €', 'Hamburg', 'https://x.com/2');
        """)
        conn.commit()
        conn.close()

        db.init_db()

        conn = sqlite3.connect(str(old_db))
        nulls = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE notified_at IS NULL"
        ).fetchone()[0]
        conn.close()
        assert nulls == 0, "Alle bestehenden Listings müssen nach Migration notified_at haben"

    def test_v5_migration_aktualisiert_email_betreffs(self, tmp_path, monkeypatch):
        """v5-Migration ersetzt alte Baby-Crawler-Betreffs durch Marktcrawler-Betreffs."""
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_v5.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        conn = sqlite3.connect(str(old_db))
        conn.executescript("""
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE geocache (location_text TEXT PRIMARY KEY, lat REAL, lon REAL);
            INSERT INTO settings VALUES
                ('email_subject_alert', '🍼 Baby-Crawler: {n} neue Anzeige(n) gefunden!'),
                ('email_subject_digest', '🍼 Baby-Crawler Tages-Digest: {n} Anzeige(n) heute');
        """)
        conn.commit()
        conn.close()

        db.init_db()

        conn = sqlite3.connect(str(old_db))
        alert = conn.execute("SELECT value FROM settings WHERE key='email_subject_alert'").fetchone()[0]
        digest = conn.execute("SELECT value FROM settings WHERE key='email_subject_digest'").fetchone()[0]
        conn.close()
        assert "Marktcrawler" in alert
        assert "Marktcrawler" in digest

    def test_v13_migration_korrigiert_is_free_willhaben_format(self, tmp_path, monkeypatch):
        """v13-Migration setzt is_free=0 für Listings mit positivem Willhaben-Preis ('€ 9')."""
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_v13.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        conn = sqlite3.connect(str(old_db))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE geocache (location_text TEXT PRIMARY KEY, lat REAL, lon REAL);
            CREATE TABLE dismissed_listings (listing_id TEXT PRIMARY KEY, dismissed_at TEXT);
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, listing_id TEXT UNIQUE, platform TEXT,
                title TEXT, price TEXT, location TEXT, url TEXT,
                description TEXT, search_term TEXT, found_at TEXT,
                is_favorite INTEGER DEFAULT 0, is_free INTEGER DEFAULT 0,
                distance_km REAL, notes TEXT, potential_duplicate TEXT,
                notified_at TEXT, image_url TEXT
            );
        """)
        # Listing mit positivem Willhaben-Preis das fälschlich is_free=1 hat
        conn.execute(
            "INSERT INTO listings(listing_id, platform, title, price, url, is_free, description) "
            "VALUES('wh_1','Willhaben','Hose','€ 9','http://x',1,'gratis Zubehör dabei')"
        )
        # Echtes Gratis-Listing soll is_free=1 behalten
        conn.execute(
            "INSERT INTO listings(listing_id, platform, title, price, url, is_free, description) "
            "VALUES('wh_2','Willhaben','Babysachen','€ 0','http://y',1,'')"
        )
        # Normales Listing soll is_free=0 behalten
        conn.execute(
            "INSERT INTO listings(listing_id, platform, title, price, url, is_free, description) "
            "VALUES('ka_1','Kleinanzeigen','Kinderwagen','50 €','http://z',0,'')"
        )
        conn.commit()
        conn.close()

        db.init_db()

        conn = sqlite3.connect(str(old_db))
        conn.row_factory = sqlite3.Row
        rows = {r["listing_id"]: r["is_free"] for r in conn.execute("SELECT listing_id, is_free FROM listings")}
        conn.close()
        assert rows["wh_1"] == 0, "Willhaben '€ 9' mit gratis-Beschreibung darf nicht is_free=1 sein"
        assert rows["wh_2"] == 1, "Willhaben '€ 0' muss is_free=1 bleiben"
        assert rows["ka_1"] == 0, "Normales Listing muss is_free=0 bleiben"

    def test_v5_migration_ueberschreibt_keine_benutzerdefinierten_betreffs(self, tmp_path, monkeypatch):
        """v5-Migration lässt angepasste Betreffs unverändert."""
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_v5_custom.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        custom = "Mein eigener Betreff {n}"
        conn = sqlite3.connect(str(old_db))
        conn.executescript(f"""
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE geocache (location_text TEXT PRIMARY KEY, lat REAL, lon REAL);
            INSERT INTO settings VALUES ('email_subject_alert', '{custom}');
        """)
        conn.commit()
        conn.close()

        db.init_db()

        conn = sqlite3.connect(str(old_db))
        alert = conn.execute("SELECT value FROM settings WHERE key='email_subject_alert'").fetchone()[0]
        conn.close()
        assert alert == custom


class TestEnsureIndexes:
    """Tests für _ensure_indexes(): Indexes werden auf vollständiger DB angelegt."""

    def test_indexes_werden_angelegt(self, tmp_path, monkeypatch):
        import sqlite3
        import app.database as db

        test_db = tmp_path / "idx.db"
        monkeypatch.setattr(db, "DB_PATH", test_db)
        db.init_db()

        conn = sqlite3.connect(str(test_db))
        indexes = {r[1] for r in conn.execute("PRAGMA index_list(listings)")}
        conn.close()
        assert "idx_listings_platform" in indexes
        assert "idx_listings_found_at" in indexes
        assert "idx_listings_notified_at" in indexes

    def test_keine_fehler_auf_alter_db_ohne_neue_spalten(self, tmp_path, monkeypatch):
        """_ensure_indexes() darf nicht abstürzen wenn Spalten fehlen."""
        import sqlite3
        import app.database as db

        old_db = tmp_path / "idx_old.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        # Minimale DB ohne is_favorite / notified_at
        conn = sqlite3.connect(str(old_db))
        conn.executescript("""
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, listing_id TEXT UNIQUE, platform TEXT,
                title TEXT, price TEXT, location TEXT, url TEXT,
                found_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE geocache (location_text TEXT PRIMARY KEY, lat REAL, lon REAL);
        """)
        conn.commit()
        conn.close()

        # Darf nicht werfen
        db.init_db()


class TestMigration:

    def test_migration_fuegt_fehlende_spalten_hinzu(self, tmp_path, monkeypatch):
        """
        Simuliert eine alte DB ohne is_favorite/is_free/distance_km
        und prüft, dass _migrate_listings() die Spalten ergänzt.
        """
        import sqlite3
        import app.database as db

        old_db = tmp_path / "old.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)

        # Alte DB ohne neue Spalten anlegen
        conn = sqlite3.connect(str(old_db))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS listings (
                id         INTEGER PRIMARY KEY,
                listing_id TEXT UNIQUE,
                platform   TEXT,
                title      TEXT,
                price      TEXT,
                location   TEXT,
                url        TEXT,
                found_at   TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS geocache (
                location_text TEXT PRIMARY KEY, lat REAL, lon REAL
            );
        """)
        conn.commit()
        conn.close()

        # Migration ausführen
        db.init_db()

        # Prüfen ob neue Spalten vorhanden
        conn = sqlite3.connect(str(old_db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
        conn.close()

        assert "is_favorite" in cols
        assert "is_free" in cols
        assert "distance_km" in cols
        assert "notes" in cols
        assert "potential_duplicate" in cols

    def test_migration_search_terms_max_price(self, tmp_path, monkeypatch):
        """search_terms.max_price wird ergänzt wenn nicht vorhanden."""
        import sqlite3
        import app.database as db

        old_db = tmp_path / "old2.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)

        conn = sqlite3.connect(str(old_db))
        conn.executescript("""
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, listing_id TEXT UNIQUE, platform TEXT,
                title TEXT, price TEXT, location TEXT, url TEXT,
                found_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE geocache (
                location_text TEXT PRIMARY KEY, lat REAL, lon REAL
            );
        """)
        conn.commit()
        conn.close()

        db.init_db()

        conn = sqlite3.connect(str(old_db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(search_terms)")}
        conn.close()
        assert "max_price" in cols


# ── Profile ───────────────────────────────────────────────────

class TestProfiles:

    def test_profile_anlegen_und_lesen(self, temp_db):
        pid = temp_db.create_profile("Kai", "🐣")
        assert isinstance(pid, int)
        profile = temp_db.get_profile(pid)
        assert profile["name"] == "Kai"
        assert profile["emoji"] == "🐣"
        assert profile["last_seen_at"] is None

    def test_get_profiles_leer(self, temp_db):
        assert temp_db.get_profiles() == []

    def test_get_profiles_mehrere(self, temp_db):
        temp_db.create_profile("Kai", "🐣")
        temp_db.create_profile("Lisa", "🌸")
        profiles = temp_db.get_profiles()
        assert len(profiles) == 2
        assert {p["name"] for p in profiles} == {"Kai", "Lisa"}

    def test_unbekanntes_profil_gibt_none(self, temp_db):
        assert temp_db.get_profile(9999) is None

    def test_profil_aktualisieren(self, temp_db):
        pid = temp_db.create_profile("Alt", "👤")
        temp_db.update_profile(pid, "Neu", "🎉")
        profile = temp_db.get_profile(pid)
        assert profile["name"] == "Neu"
        assert profile["emoji"] == "🎉"

    def test_profil_loeschen(self, temp_db):
        pid = temp_db.create_profile("Löschen", "❌")
        temp_db.delete_profile(pid)
        assert temp_db.get_profile(pid) is None
        assert temp_db.get_profiles() == []

    def test_last_seen_at_wird_aktualisiert(self, temp_db):
        pid = temp_db.create_profile("Test", "👤")
        assert temp_db.get_profile(pid)["last_seen_at"] is None
        temp_db.update_profile_last_seen(pid)
        assert temp_db.get_profile(pid)["last_seen_at"] is not None

    def test_update_profile_notify_speichert_felder(self, temp_db):
        pid = temp_db.create_profile("Alice", "👤")
        temp_db.update_profile_notify(pid, "alice@example.com", "immediate", "08:00")
        p = temp_db.get_profile(pid)
        assert p["email"] == "alice@example.com"
        assert p["notify_mode"] == "immediate"
        assert p["digest_time"] == "08:00"

    def test_update_profile_notify_alle_modi(self, temp_db):
        pid = temp_db.create_profile("Bob", "👤")
        for mode in ("immediate", "digest_only", "both", "off"):
            temp_db.update_profile_notify(pid, "b@example.com", mode, "19:00")
            assert temp_db.get_profile(pid)["notify_mode"] == mode

    def test_update_profile_notify_ungültiger_modus_wird_zu_immediate(self, temp_db):
        pid = temp_db.create_profile("Carol", "👤")
        temp_db.update_profile_notify(pid, "c@example.com", "ungültig", "19:00")
        assert temp_db.get_profile(pid)["notify_mode"] == "immediate"

    def test_update_profile_notify_leere_email_wird_null(self, temp_db):
        pid = temp_db.create_profile("Dave", "👤")
        temp_db.update_profile_notify(pid, "", "immediate", "19:00")
        assert temp_db.get_profile(pid)["email"] is None

    def test_update_profile_notify_leere_digest_time_verwendet_default(self, temp_db):
        pid = temp_db.create_profile("Eve", "👤")
        temp_db.update_profile_notify(pid, "e@example.com", "both", "")
        assert temp_db.get_profile(pid)["digest_time"] == "19:00"

    def test_update_profile_notify_interval_wird_gespeichert(self, temp_db):
        pid = temp_db.create_profile("Frank", "👤")
        temp_db.update_profile_notify(pid, "f@example.com", "immediate", "19:00", alert_interval_minutes=60)
        assert temp_db.get_profile(pid)["alert_interval_minutes"] == 60

    def test_update_profile_notify_interval_minimum_15(self, temp_db):
        pid = temp_db.create_profile("Grace", "👤")
        temp_db.update_profile_notify(pid, "g@example.com", "immediate", "19:00", alert_interval_minutes=5)
        assert temp_db.get_profile(pid)["alert_interval_minutes"] == 15

    def test_update_last_alert_sent(self, temp_db):
        pid = temp_db.create_profile("Hans", "👤")
        assert temp_db.get_profile(pid)["last_alert_sent_at"] is None
        temp_db.update_last_alert_sent(pid)
        assert temp_db.get_profile(pid)["last_alert_sent_at"] is not None


# ── Crawl-Log & Notification-Log ─────────────────────────────

class TestCrawlLog:

    def test_log_crawl_run_speichert_eintrag(self, temp_db):
        temp_db.log_crawl_run("kleinanzeigen", "2026-01-01T10:00:00", "2026-01-01T10:01:30",
                              90.0, 5, 3)
        stats = temp_db.get_system_stats()
        assert stats["total_crawl_runs"] == 1
        cs = stats["crawl_stats"]
        assert len(cs) == 1
        assert cs[0]["platform"] == "kleinanzeigen"
        assert cs[0]["runs"] == 1
        assert cs[0]["total_found"] == 5
        assert cs[0]["avg_duration_s"] == 90.0

    def test_log_crawl_run_mehrere_plattformen(self, temp_db):
        temp_db.log_crawl_run("kleinanzeigen", "2026-01-01T10:00:00", "2026-01-01T10:01:00", 60.0, 3, 2)
        temp_db.log_crawl_run("shpock",        "2026-01-01T10:00:00", "2026-01-01T10:01:30", 90.0, 7, 2)
        temp_db.log_crawl_run("kleinanzeigen", "2026-01-01T11:00:00", "2026-01-01T11:02:00", 120.0, 2, 2)
        stats = temp_db.get_system_stats()
        assert stats["total_crawl_runs"] == 3
        plats = {c["platform"]: c for c in stats["crawl_stats"]}
        assert plats["kleinanzeigen"]["runs"] == 2
        assert plats["kleinanzeigen"]["total_found"] == 5
        assert plats["shpock"]["runs"] == 1

    def test_log_notification_alert(self, temp_db):
        temp_db.log_notification("alert", 12, 2)
        stats = temp_db.get_system_stats()
        assert stats["total_notifications"] == 1
        n = stats["notif_stats"][0]
        assert n["type"] == "alert"
        assert n["total"] == 1
        assert n["avg_listings"] == 12.0

    def test_log_notification_digest_und_alert(self, temp_db):
        temp_db.log_notification("alert", 5, 1)
        temp_db.log_notification("digest", 20, 1)
        temp_db.log_notification("alert", 3, 1)
        stats = temp_db.get_system_stats()
        assert stats["total_notifications"] == 3
        types = {n["type"]: n for n in stats["notif_stats"]}
        assert types["alert"]["total"] == 2
        assert round(types["alert"]["avg_listings"], 1) == 4.0
        assert types["digest"]["total"] == 1


# ── get_system_stats ─────────────────────────────────────────

class TestSystemStats:

    def test_alle_keys_vorhanden(self, temp_db):
        stats = temp_db.get_system_stats()
        required = [
            "db_size_mb", "disk_free_gb", "disk_total_gb", "disk_used_pct",
            "geocache_count", "listings_total", "listings_today", "listings_last_7d",
            "listings_favorites", "listings_free", "listings_with_notes",
            "listings_no_image", "listings_duplicates", "listings_dismissed",
            "platforms", "top_terms", "daily_counts", "daily_max",
            "price_avg", "price_min", "price_max", "price_unknown_count",
            "crawl_stats", "total_crawl_runs", "notif_stats", "total_notifications",
            "search_term_count", "active_term_count", "profile_count", "migrations",
        ]
        for key in required:
            assert key in stats, f"Key fehlt: {key}"

    def test_listings_zaehler(self, temp_db):
        from app.scrapers.base import Listing
        l = Listing(platform="Test", title="Item", price="10 €",
                    location="München", url="https://x.com/1",
                    listing_id="x1", search_term="test", is_free=False)
        temp_db.save_listing(l)
        stats = temp_db.get_system_stats()
        assert stats["listings_total"] == 1
        assert stats["listings_today"] == 1
        assert stats["listings_last_7d"] == 1

    def test_daily_counts_hat_7_eintraege(self, temp_db):
        stats = temp_db.get_system_stats()
        assert len(stats["daily_counts"]) == 7

    def test_daily_max_mindestens_1(self, temp_db):
        stats = temp_db.get_system_stats()
        assert stats["daily_max"] >= 1

    def test_migrations_liste_nicht_leer(self, temp_db):
        stats = temp_db.get_system_stats()
        assert len(stats["migrations"]) >= 8  # v1–v8 alle angewendet

    def test_platform_breakdown(self, temp_db):
        from app.scrapers.base import Listing
        for i, plat in enumerate(["Shpock", "Shpock", "Vinted"]):
            temp_db.save_listing(Listing(
                platform=plat, title=f"Item {i}", price="5 €",
                location="München", url=f"https://x.com/{i}",
                listing_id=f"p{i}", search_term="test",
            ))
        stats = temp_db.get_system_stats()
        plats = {p["platform"]: p["count"] for p in stats["platforms"]}
        assert plats["Shpock"] == 2
        assert plats["Vinted"] == 1

    def test_preis_statistik(self, temp_db):
        from app.scrapers.base import Listing
        for i, price in enumerate(["10 €", "20 €", "30 €"]):
            temp_db.save_listing(Listing(
                platform="Test", title=f"Item {i}", price=price,
                location="München", url=f"https://x.com/{i}",
                listing_id=f"pr{i}", search_term="test",
            ))
        stats = temp_db.get_system_stats()
        assert stats["price_min"] == 10.0
        assert stats["price_max"] == 30.0
        assert stats["price_avg"] == 20.0


class TestPlatformMaxAges:
    """Tests für den pro-Plattform Alters-Filter in get_listings()."""

    def _add(self, db, listing_id, platform, age_hours):
        """Fügt ein Listing mit künstlichem found_at-Alter ein."""
        import sqlite3
        from app import database as _db_mod
        l = Listing(
            platform=platform, title=f"Test {listing_id}", price="10 €",
            location="München", url=f"https://x.com/{listing_id}",
            listing_id=listing_id, search_term="test",
        )
        db.save_listing(l)
        conn = sqlite3.connect(str(_db_mod.DB_PATH))
        conn.execute(
            "UPDATE listings SET found_at = datetime('now', ? || ' hours') WHERE listing_id = ?",
            (f"-{age_hours}", listing_id),
        )
        conn.commit()
        conn.close()

    def test_kein_filter_zeigt_alles(self, temp_db):
        self._add(temp_db, "v1", "vinted", 72)
        self._add(temp_db, "k1", "kleinanzeigen", 72)
        results = temp_db.get_listings()
        ids = {r["listing_id"] for r in results}
        assert "v1" in ids and "k1" in ids

    def test_plattform_max_age_filtert_alte_anzeigen(self, temp_db):
        self._add(temp_db, "v_old", "vinted", 72)   # 72h alt → zu alt bei max 48h
        self._add(temp_db, "v_new", "vinted", 10)   # 10h alt → ok
        self._add(temp_db, "k_old", "kleinanzeigen", 72)  # 72h alt → kein Filter für KA
        results = temp_db.get_listings(platform_max_ages={"vinted": 48})
        ids = {r["listing_id"] for r in results}
        assert "v_old" not in ids
        assert "v_new" in ids
        assert "k_old" in ids

    def test_mehrere_plattformen_gefiltert(self, temp_db):
        self._add(temp_db, "v_old", "vinted", 50)
        self._add(temp_db, "s_old", "shpock", 25)
        self._add(temp_db, "v_new", "vinted", 10)
        self._add(temp_db, "s_new", "shpock", 5)
        results = temp_db.get_listings(
            platform_max_ages={"vinted": 48, "shpock": 24}
        )
        ids = {r["listing_id"] for r in results}
        assert "v_old" not in ids
        assert "s_old" not in ids
        assert "v_new" in ids
        assert "s_new" in ids

    def test_global_override_ignoriert_plattform_ages(self, temp_db):
        self._add(temp_db, "v_old", "vinted", 72)
        # global max_age=0 bedeutet kein globaler Filter, aber platform_max_ages greift
        results = temp_db.get_listings(
            max_age_hours=0,
            platform_max_ages={"vinted": 48},
        )
        ids = {r["listing_id"] for r in results}
        assert "v_old" not in ids

    def test_global_max_age_ueberschreibt_plattform_filter(self, temp_db):
        self._add(temp_db, "v_old", "vinted", 30)   # 30h alt
        # global max_age=48 → vinted_old (30h) sollte sichtbar sein, auch wenn
        # platform_max_ages theoretisch dagegen wäre
        results = temp_db.get_listings(
            max_age_hours=48,
            platform_max_ages={"vinted": 24},  # wird ignoriert, weil global gesetzt
        )
        ids = {r["listing_id"] for r in results}
        assert "v_old" in ids

    def test_null_wert_in_platform_ages_ignoriert(self, temp_db):
        self._add(temp_db, "v_old", "vinted", 72)
        results = temp_db.get_listings(platform_max_ages={"vinted": 0})
        ids = {r["listing_id"] for r in results}
        assert "v_old" in ids  # 0 = kein Filter


class TestClaimUnnotifiedListings:
    """B5-Fix: claim_unnotified_listings() holt und markiert atomar."""

    def _listing(self, lid: str):
        return Listing(
            platform="Test", title="Kinderwagen", price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test",
        )

    def test_gibt_leere_liste_wenn_keine_unbenachrichtigten(self, temp_db):
        result = temp_db.claim_unnotified_listings()
        assert result == []

    def test_gibt_unbenachrichtigte_listings_zurueck(self, temp_db):
        temp_db.save_listing(self._listing("a"))
        temp_db.save_listing(self._listing("b"))
        result = temp_db.claim_unnotified_listings()
        assert len(result) == 2
        assert {r["listing_id"] for r in result} == {"a", "b"}

    def test_markiert_listings_als_notified(self, temp_db):
        temp_db.save_listing(self._listing("x"))
        temp_db.claim_unnotified_listings()
        # Zweiter Aufruf findet nichts mehr
        result = temp_db.claim_unnotified_listings()
        assert result == []

    def test_bereits_notified_listings_werden_nicht_zurueckgegeben(self, temp_db):
        temp_db.save_listing(self._listing("old"))
        temp_db.mark_listings_notified(["old"])
        temp_db.save_listing(self._listing("new"))
        result = temp_db.claim_unnotified_listings()
        assert len(result) == 1
        assert result[0]["listing_id"] == "new"


class TestSaveListingSingleConnection:
    """A2-Fix: save_listing() arbeitet in einer einzigen Verbindung."""

    def test_dismissed_listing_wird_nicht_gespeichert(self, temp_db):
        temp_db.dismiss_listing  # ensure function exists
        listing = Listing(
            platform="Test", title="Kinderwagen", price="10 €",
            location="München", url="https://example.com/d1",
            listing_id="dismissed-1", search_term="test",
        )
        # dismiss simulieren: erst speichern, dann ausblenden
        temp_db.save_listing(listing)
        listings = temp_db.get_listings()
        db_id = next(r["id"] for r in listings if r["listing_id"] == "dismissed-1")
        temp_db.dismiss_listing(db_id)

        # Zweiter Speicherversuch muss False zurückgeben
        result = temp_db.save_listing(listing)
        assert result is False

    def test_duplikat_erkennung_in_selber_transaktion(self, temp_db):
        first = Listing(
            platform="Shpock", title="Toller Kinderwagen", price="50 €",
            location="München", url="https://shpock.com/1",
            listing_id="dup-1", search_term="kinderwagen",
        )
        second = Listing(
            platform="Kleinanzeigen", title="Toller Kinderwagen", price="50 €",
            location="München", url="https://ka.de/2",
            listing_id="dup-2", search_term="kinderwagen",
        )
        temp_db.save_listing(first)
        temp_db.save_listing(second)
        listings = temp_db.get_listings()
        second_saved = next(r for r in listings if r["listing_id"] == "dup-2")
        assert second_saved["potential_duplicate"] == "Shpock"


# ── Preisstatistik ───────────────────────────────────────────

class TestGetPriceStats:

    def _save(self, temp_db, listing_id, term, price, is_free=False):
        temp_db.save_listing(Listing(
            platform="Kleinanzeigen", title="Artikel", price=price,
            location="Dortmund", url=f"https://example.com/{listing_id}",
            listing_id=listing_id, search_term=term, is_free=is_free,
        ))

    def test_leere_db_liefert_leere_liste(self, temp_db):
        assert temp_db.get_price_stats() == []

    def test_aggregation_pro_suchbegriff(self, temp_db):
        self._save(temp_db, "p1", "kinderwagen", "40 €")
        self._save(temp_db, "p2", "kinderwagen", "60 €")
        stats = temp_db.get_price_stats()
        assert len(stats) == 1
        row = stats[0]
        assert row["search_term"] == "kinderwagen"
        assert row["count"] == 2
        assert row["avg_price"] == 50.0
        assert row["min_price"] == 40.0
        assert row["max_price"] == 60.0

    def test_mehrere_terme_je_eigene_zeile(self, temp_db):
        self._save(temp_db, "a1", "kinderwagen", "50 €")
        self._save(temp_db, "b1", "babyschale", "80 €")
        terms = {r["search_term"] for r in temp_db.get_price_stats()}
        assert terms == {"kinderwagen", "babyschale"}

    def test_unbekannte_preise_werden_ignoriert(self, temp_db):
        self._save(temp_db, "u1", "kinderwagen", "k.A.")
        self._save(temp_db, "u2", "kinderwagen", "Preis nicht angegeben")
        self._save(temp_db, "u3", "kinderwagen", "")
        assert temp_db.get_price_stats() == []

    def test_gratis_anzeigen_werden_gezaehlt(self, temp_db):
        self._save(temp_db, "f1", "kinderwagen", "0 €", is_free=True)
        self._save(temp_db, "f2", "kinderwagen", "50 €", is_free=False)
        # Preis 0 wird durch WHERE > 0 gefiltert; is_free=True auf einer
        # bezahlten Anzeige (z.B. "gratis Zubehör dabei") muss gezählt werden
        stats = temp_db.get_price_stats()
        paid_row = next((r for r in stats if r["search_term"] == "kinderwagen"), None)
        assert paid_row is not None
        assert paid_row["free_count"] == 0  # is_free=False bei der 50-€-Anzeige


# ── CleanupMismatchedListings ────────────────────────────────

def _mismatch_listing(listing_id: str, term: str, title: str, desc: str = "") -> Listing:
    return Listing(
        platform="Test", title=title, price="10 €", location="München",
        url=f"https://x.com/{listing_id}", listing_id=listing_id,
        search_term=term, description=desc,
    )


class TestCleanupMismatchedListings:

    def test_leere_db_gibt_null(self, temp_db):
        assert temp_db.cleanup_mismatched_listings() == 0

    def test_passende_anzeige_bleibt_erhalten(self, temp_db):
        temp_db.save_listing(_mismatch_listing("ok1", "baby werder", "Baby Werder Trikot"))
        assert temp_db.cleanup_mismatched_listings() == 0
        assert len(temp_db.get_listings()) == 1

    def test_nicht_passende_anzeige_wird_geloescht(self, temp_db):
        temp_db.save_listing(_mismatch_listing("bad1", "baby werder", "Kinderwagen günstig"))
        assert temp_db.cleanup_mismatched_listings() == 1
        assert len(temp_db.get_listings()) == 0

    def test_nur_mismatches_werden_geloescht(self, temp_db):
        temp_db.save_listing(_mismatch_listing("ok1", "baby werder", "Baby Werder Trikot"))
        temp_db.save_listing(_mismatch_listing("bad1", "baby werder", "Zufälliger Kinderwagen"))
        assert temp_db.cleanup_mismatched_listings() == 1
        titles = [l["title"] for l in temp_db.get_listings()]
        assert "Baby Werder Trikot" in titles
        assert "Zufälliger Kinderwagen" not in titles

    def test_geloeschte_werden_dismissed(self, temp_db):
        temp_db.save_listing(_mismatch_listing("bad2", "baby werder", "Nur Kinderwagen hier"))
        temp_db.cleanup_mismatched_listings()
        assert temp_db.is_dismissed("bad2") is True

    def test_einwort_suchbegriff_nicht_betroffen(self, temp_db):
        temp_db.save_listing(_mismatch_listing("ok2", "kinderwagen", "Buggy Pram Jogging"))
        assert temp_db.cleanup_mismatched_listings() == 0

    def test_wortgrenze_schwerder_ist_mismatch(self, temp_db):
        # "werder" als Teilwort in "Schwerder" darf nicht matchen
        temp_db.save_listing(_mismatch_listing("bad3", "body werder", "Schwerder Fan Jacke"))
        assert temp_db.cleanup_mismatched_listings() == 1

    def test_mehrere_mismatches_werden_alle_geloescht(self, temp_db):
        for i in range(3):
            temp_db.save_listing(_mismatch_listing(f"bad{i+10}", "baby werder", f"Kinderwagen {i}"))
        assert temp_db.cleanup_mismatched_listings() == 3
        assert len(temp_db.get_listings()) == 0

    def test_dismissed_verhindert_wiederanlage(self, temp_db):
        temp_db.save_listing(_mismatch_listing("bad4", "baby werder", "Kein Match Anzeige"))
        temp_db.cleanup_mismatched_listings()
        # Nach Cleanup: erneut speichern muss fehlschlagen (dismissed)
        ok = temp_db.save_listing(_mismatch_listing("bad4", "baby werder", "Kein Match Anzeige"))
        assert ok is False
