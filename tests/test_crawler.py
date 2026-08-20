"""Tests für app/crawler.py: _is_free(), _is_blacklisted(), _matches_all_words(), _is_lang_allowed()."""

import sys
import pytest
from unittest.mock import MagicMock, patch
from app.crawler import _is_free, _is_blacklisted, _matches_all_words, _is_lang_allowed
from app.scrapers.base import Listing


def make_listing(**kwargs) -> Listing:
    """Hilfsfunktion: Listing mit sinnvollen Defaults erstellen."""
    defaults = dict(
        platform="Test",
        title="Kinderwagen",
        price="50 €",
        location="Dortmund",
        url="https://example.com/1",
        listing_id="test-1",
        search_term="kinderwagen",
        description="",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


# ── _is_free ─────────────────────────────────────────────────

class TestIsFree:

    # --- Preis-Erkennung ---

    def test_preis_null_euro(self):
        assert _is_free(make_listing(price="0 €")) is True

    def test_preis_null_euro_ohne_space(self):
        assert _is_free(make_listing(price="0€")) is True

    def test_preis_null_komma_null(self):
        assert _is_free(make_listing(price="0,00 €")) is True

    def test_preis_kostenlos(self):
        assert _is_free(make_listing(price="Kostenlos")) is True

    def test_preis_kostenlos_kleinschreibung(self):
        assert _is_free(make_listing(price="kostenlos")) is True

    def test_preis_gratis(self):
        assert _is_free(make_listing(price="Gratis")) is True

    def test_preis_umsonst(self):
        assert _is_free(make_listing(price="umsonst")) is True

    def test_preis_zu_verschenken(self):
        assert _is_free(make_listing(price="zu verschenken")) is True

    def test_preis_free(self):
        assert _is_free(make_listing(price="free")) is True

    def test_normaler_preis_nicht_frei(self):
        assert _is_free(make_listing(price="50 €")) is False

    def test_preis_mit_fuehrendem_nullen_nicht_frei(self):
        """'01 €' ist kein Gratis-Angebot."""
        assert _is_free(make_listing(price="01 €")) is False

    # --- Titel-Erkennung ---

    def test_titel_zu_verschenken(self):
        assert _is_free(make_listing(title="Kinderwagen zu verschenken", price="")) is True

    def test_titel_verschenke(self):
        assert _is_free(make_listing(title="Verschenke Babywippe", price="")) is True

    def test_titel_gratis(self):
        assert _is_free(make_listing(title="Babyschale gratis abzugeben", price="")) is True

    def test_titel_zu_vergeben(self):
        assert _is_free(make_listing(title="Babybett zu vergeben", price="")) is True

    # --- Beschreibungs-Erkennung ---

    def test_beschreibung_kostenlos(self):
        listing = make_listing(price="VB", description="Ist kostenlos, einfach abholen")
        assert _is_free(listing) is True

    def test_beschreibung_zu_verschenken(self):
        # Echter Preis schlägt Text: 5 € → nicht gratis
        listing = make_listing(price="5 €", description="Wir geben es lieber zu verschenken")
        assert _is_free(listing) is False

    # --- Kein False Positive ---

    def test_normales_listing_nicht_frei(self):
        listing = make_listing(
            title="Guter Kinderwagen Maxi-Cosi",
            price="80 €",
            description="Wenig benutzt, guter Zustand",
        )
        assert _is_free(listing) is False

    def test_preis_mit_gratis_in_beschreibung_nicht_frei(self):
        """44 € + 'gratis Zubehör dabei' in Beschreibung → nicht gratis (Original-Bug)."""
        listing = make_listing(price="44.00 €", description="Inkl. gratis Zubehör dabei")
        assert _is_free(listing) is False

    def test_vb_preis_mit_kostenlos_in_beschreibung_ist_frei(self):
        """VB ist kein echter Preis → Beschreibung 'kostenlos' zählt."""
        listing = make_listing(price="VB", description="Ist kostenlos, einfach abholen")
        assert _is_free(listing) is True

    def test_leerer_preis_kein_fehler(self):
        """Leerer Preis darf keinen Exception werfen."""
        assert _is_free(make_listing(price="")) is False

    def test_keiner_angabe_preis(self):
        assert _is_free(make_listing(price="k.A.")) is False

    # --- Willhaben-Format (€ vor Zahl) ---

    def test_willhaben_preis_euro_vor_zahl_nicht_frei(self):
        """'€ 9' (Willhaben-Format) darf nicht als gratis erkannt werden."""
        assert _is_free(make_listing(price="€ 9")) is False

    def test_willhaben_preis_euro_vor_zahl_mit_gratis_beschreibung_nicht_frei(self):
        """'€ 15' + 'gratis' in Beschreibung → nicht gratis (Willhaben-Bug-Regression)."""
        listing = make_listing(price="€ 15", description="gratis Zubehör dabei")
        assert _is_free(listing) is False

    def test_willhaben_preis_null_euro_vorne_ist_frei(self):
        """'€ 0' (Willhaben Gratis-Format) → gratis."""
        assert _is_free(make_listing(price="€ 0")) is True

    def test_willhaben_preis_euro_ohne_space_nicht_frei(self):
        """'€9' ohne Leerzeichen → nicht gratis."""
        assert _is_free(make_listing(price="€9")) is False


# ── _is_blacklisted ───────────────────────────────────────────

class TestIsBlacklisted:

    def test_leere_blacklist_nie_blacklisted(self):
        assert _is_blacklisted(make_listing(title="defekter Kinderwagen"), []) is False

    def test_wort_im_titel_wird_erkannt(self):
        assert _is_blacklisted(make_listing(title="Kinderwagen defekt"), ["defekt"]) is True

    def test_wort_in_beschreibung_wird_erkannt(self):
        listing = make_listing(description="Für Bastler geeignet")
        assert _is_blacklisted(listing, ["bastler"]) is True

    def test_grossschreibung_wird_ignoriert(self):
        assert _is_blacklisted(make_listing(title="DEFEKTER Kinderwagen"), ["defekt"]) is True

    def test_blacklist_grossschreibung_wird_ignoriert(self):
        assert _is_blacklisted(make_listing(title="defekter Kinderwagen"), ["DEFEKT"]) is True

    def test_substring_match(self):
        """Blacklist prüft Teilstring: 'ersatz' trifft auch 'Ersatzteil'."""
        assert _is_blacklisted(make_listing(title="Ersatzteil"), ["ersatz"]) is True
        # Umgekehrt: 'ersatzteile' trifft kein Listing ohne dieses Wort
        assert _is_blacklisted(make_listing(title="guter Kinderwagen"), ["ersatzteile"]) is False

    def test_mehrere_blacklist_worter(self):
        assert _is_blacklisted(make_listing(title="Kinderwagen"), ["defekt", "kinderwagen"]) is True

    def test_kein_match_bei_unbekanntem_wort(self):
        assert _is_blacklisted(make_listing(title="Sehr guter Zustand"), ["defekt", "bastler"]) is False

    def test_zeilenumbruch_separierte_blacklist(self):
        """Blacklist kann auch mit Zeilenumbrüchen übergeben werden (nach Parse durch Crawler)."""
        # crawler.py splittet schon vor dem Aufruf – hier testen wir die bereits geparste Liste
        blacklist = ["defekt", "bastler", "kaputt"]
        assert _is_blacklisted(make_listing(title="kaputtes Babybett"), blacklist) is True

    def test_leerzeichen_in_blacklist_eintrag(self):
        """Mehrteilige Blacklist-Einträge funktionieren."""
        assert _is_blacklisted(
            make_listing(title="Kinderwagen zu reparieren"),
            ["zu reparieren"],
        ) is True


# ── _matches_all_words ─────────────────────────────────────────

class TestMatchesAllWords:

    def test_einwort_suche_match(self):
        assert _matches_all_words(make_listing(title="Kinderwagen"), "kinderwagen") is True

    def test_einwort_suche_kein_match_ergibt_false(self):
        assert _matches_all_words(make_listing(title="Buggy"), "kinderwagen") is False

    def test_einwort_zahl_kein_substring_match(self):
        # "56" darf nicht in "1956" oder "56m²" matchen
        assert _matches_all_words(make_listing(title="Wohnung von 1956", description="ca.56m² Wohnzimmer"), "56") is False

    def test_einwort_zahl_standalone_match(self):
        assert _matches_all_words(make_listing(title="Kinderwagen Baujahr 56"), "56") is True

    def test_alle_woerter_im_titel(self):
        assert _matches_all_words(make_listing(title="Baby Werder Kinderwagen"), "baby werder") is True

    def test_alle_woerter_in_beschreibung(self):
        assert _matches_all_words(
            make_listing(title="Kinderwagen", description="Für Baby aus Werder"),
            "baby werder",
        ) is True

    def test_woerter_verteilt_auf_titel_und_beschreibung(self):
        assert _matches_all_words(
            make_listing(title="Baby Kinderwagen", description="Angebot aus Werder"),
            "baby werder",
        ) is True

    def test_nur_ein_wort_vorhanden_ergibt_false(self):
        assert _matches_all_words(make_listing(title="Baby Kinderwagen"), "baby werder") is False

    def test_kein_wort_vorhanden_ergibt_false(self):
        assert _matches_all_words(make_listing(title="Buggy Bremen"), "baby werder") is False

    def test_grossschreibung_wird_ignoriert(self):
        assert _matches_all_words(make_listing(title="BABY WERDER"), "baby werder") is True

    def test_suchbegriff_grossschreibung_ignoriert(self):
        assert _matches_all_words(make_listing(title="baby werder"), "BABY WERDER") is True

    def test_drei_woerter_alle_vorhanden(self):
        assert _matches_all_words(
            make_listing(title="Maxi Cosi Baby Schale"),
            "maxi cosi baby",
        ) is True

    def test_drei_woerter_eines_fehlt(self):
        assert _matches_all_words(
            make_listing(title="Maxi Cosi Schale"),
            "maxi cosi baby",
        ) is False

    def test_leerer_suchbegriff_immer_true(self):
        assert _matches_all_words(make_listing(title="irgendwas"), "") is True

    # --- Wortgrenzen ---

    def test_wortgrenze_kein_teilstring_werder(self):
        """'werder' darf NICHT 'Schwerder' matchen."""
        assert _matches_all_words(make_listing(title="Schwerder Jacke Baby"), "baby werder") is False

    def test_wortgrenze_kein_teilstring_body(self):
        """'body' darf NICHT 'somebody' matchen."""
        assert _matches_all_words(make_listing(title="somebody loves babies"), "body werder") is False

    def test_wortgrenze_bindestrich_gilt_als_trenner(self):
        """'werder' trifft in 'Werder-Fan' (Bindestrich = Wortgrenze)."""
        assert _matches_all_words(make_listing(title="Baby Werder-Fan"), "baby werder") is True

    def test_wortgrenze_anfang_ende_string(self):
        """Wort am Anfang/Ende des Strings wird korrekt erkannt."""
        assert _matches_all_words(make_listing(title="werder baby"), "baby werder") is True


# ── _is_lang_allowed ────────────────────────────────────────────

class TestIsLangAllowed:

    def _lang(self, code: str, prob: float = 0.99):
        """Hilfsfunktion: Mock-Language-Objekt für detect_langs-Ergebnisse."""
        obj = MagicMock()
        obj.lang = code
        obj.prob = prob
        return obj

    def _mock_detect_langs(self, results, side_effect=None):
        """Patcht langdetect.detect_langs im sys.modules."""
        mock_mod = MagicMock()
        if side_effect:
            mock_mod.detect_langs.side_effect = side_effect
        else:
            mock_mod.detect_langs.return_value = results
        mock_mod.DetectorFactory = MagicMock()
        return patch.dict(sys.modules, {"langdetect": mock_mod})

    def test_leere_allowed_langs_immer_true(self):
        assert _is_lang_allowed(make_listing(description="Bonjour le monde, ceci est une description"), []) is True

    def test_kurze_fremdsprachige_beschreibung_mit_titel_wird_gefiltert(self):
        with self._mock_detect_langs([self._lang("fr", 0.99)]) as mocked:
            assert _is_lang_allowed(
                make_listing(title="Vêtements pour bébé", description="Très joli"),
                ["de"],
            ) is False
            mocked["langdetect"].detect_langs.assert_called_once_with(
                "Vêtements pour bébé Très joli"
            )

    def test_fremdsprachiger_titel_ohne_beschreibung_wird_gefiltert(self):
        with self._mock_detect_langs([self._lang("fr", 0.99)]) as mocked:
            assert _is_lang_allowed(
                make_listing(title="Poussette bébé en très bon état", description=""),
                ["de"],
            ) is False
            mocked["langdetect"].detect_langs.assert_called_once_with(
                "Poussette bébé en très bon état"
            )

    def test_sehr_kurzer_text_wird_durchgelassen(self):
        with self._mock_detect_langs([self._lang("fr")]) as mocked:
            assert _is_lang_allowed(make_listing(title="Bébé", description=""), ["de"]) is True
            mocked["langdetect"].detect_langs.assert_not_called()

    def test_erkannte_sprache_erlaubt(self):
        with self._mock_detect_langs([self._lang("de")]):
            assert _is_lang_allowed(
                make_listing(description="Sehr gut erhalten, kaum benutzt, aus tierfreiem Haushalt"),
                ["de"],
            ) is True

    def test_erkannte_sprache_nicht_erlaubt(self):
        with self._mock_detect_langs([self._lang("it")]):
            assert _is_lang_allowed(
                make_listing(description="abbigliamento per bambini da uno a tre mesi quasi nuovo"),
                ["de"],
            ) is False

    def test_niedrige_konfidenz_gibt_true(self):
        with self._mock_detect_langs([self._lang("fr", prob=0.55)]):
            assert _is_lang_allowed(
                make_listing(description="Tripp Trapp Classic Kissen Nordic Grey Kein Versand hier"),
                ["de"],
            ) is True

    def test_erlaubte_nebensprache_reicht_nicht(self):
        # Nur die wahrscheinlichste Sprache zählt.
        with self._mock_detect_langs([self._lang("en", 0.75), self._lang("de", 0.25)]):
            assert _is_lang_allowed(
                make_listing(description="Nice baby carrier in very good condition and barely used"),
                ["de"],
            ) is False

    def test_ergebnisreihenfolge_aendert_beste_sprache_nicht(self):
        with self._mock_detect_langs([self._lang("de", 0.10), self._lang("fr", 0.90)]):
            assert _is_lang_allowed(
                make_listing(description="Cette poussette pour bébé est en excellent état général"),
                ["de"],
            ) is False

    def test_erlaubte_sprachen_werden_normalisiert(self):
        with self._mock_detect_langs([self._lang("de")]):
            assert _is_lang_allowed(
                make_listing(description="Sehr gut erhalten, kaum benutzt, aus tierfreiem Haushalt"),
                [" DE "],
            ) is True

    def test_mehrere_erlaubte_sprachen(self):
        with self._mock_detect_langs([self._lang("en")]):
            assert _is_lang_allowed(
                make_listing(description="Nice baby stroller in very good condition barely used once"),
                ["de", "en"],
            ) is True

    def test_detection_exception_gibt_true(self):
        with self._mock_detect_langs(None, side_effect=Exception("DetectorError")):
            assert _is_lang_allowed(
                make_listing(description="Kurzer Text Kinderwagen Vinted Anzeige hier zu verkaufen"),
                ["de"],
            ) is True

    def test_langdetect_nicht_installiert_gibt_true(self):
        with patch.dict(sys.modules, {"langdetect": None}):
            assert _is_lang_allowed(
                make_listing(description="Irgendein Anzeigentext für den Test hier und da"),
                ["de"],
            ) is True
