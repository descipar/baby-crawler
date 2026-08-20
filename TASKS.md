# 📋 Marktcrawler – Aufgaben & Roadmap

Die vollständige Geschichte aller abgeschlossenen Phasen (1–24) findet sich in [TASKS_v1.0.md](TASKS_v1.0.md) (Stand: Release v1.0.0).

---

## ✅ Abgeschlossene Phasen (seit v1.0)

### Phase 25 – UX-Verbesserungen & Info-Seite

- [x] Preisstatistik (per Suchbegriff) von Dashboard auf Info-Seite verschoben — passt besser zur dortigen Analyse-Ansicht
- [x] `get_price_stats()` in `test_database.py` durch 5 Unit-Tests abgedeckt (leere DB, Aggregation, mehrere Terme, ungültige Preise, Gratis-Zähler)
- [x] E-Mail-Benachrichtigung: „Im Dashboard →"-Button pro Anzeige mit Deep-Link `/?modal=<db_id>` — öffnet Modal direkt beim Seitenload
- [x] `server_url`-Eingabe in Settings tolerant: IP oder Hostname reicht (`192.168.1.10`, `raspberrypi.local`), `http://` und `:5000` werden automatisch ergänzt; `_normalize_server_url()` mit 8 Unit-Tests abgedeckt
- [x] Settings: Datenverwaltungs-Block in eigenen Tab „🗑️ Daten" verschoben; Speichern-Button auf diesem Tab ausgeblendet
- [x] Info-Seite: aktuellen Commit (Hash, Datum, Message) und verfügbare GitHub-Updates anzeigen; `app/version.py` liest `.git` beim `docker build` via `scripts/bake_version.py` ein — kein Build-Arg, kein Script nötig, `git pull && docker compose up -d --build` reicht
- [x] Update-Check auf On-Demand-Button umgestellt (war Auto-Load); Commit-Hashes auf Info-Seite als GitHub-Links; Repo-URL im Check-Updates-Response
- [x] `_last_commit_from_log()` in `bake_version.py` filtert "Fast-forward"-/Checkout-Einträge aus dem `.git/logs`-Branch-Log heraus — zeigt korrekte letzte Commit-Message statt "Fast-forward"
- [x] 11 weitere Tests (`TestLastCommitFromLog` × 6, `TestCheckUpdatesApi` × 6) — gesamt 430

---

### Phase 28 – Per-Profil-E-Mail-Benachrichtigungen

- [x] DB-Migration v10: `profiles` bekommt Spalten `email`, `notify_mode` (immediate/digest_only/both/off), `digest_time`
- [x] DB-Migration v11: `profiles` bekommt `alert_interval_minutes` (Default 15, Minimum 15) und `last_alert_sent_at`
- [x] `database/profiles.py`: `update_profile_notify()` als neue Funktion; `get_profiles()` liefert neue Felder
- [x] `notifier.py`: `notify_pending()` sendet pro Profil mit `mode=immediate/both` an die profil-eigene E-Mail; Fallback auf globale Settings wenn kein Profil eine E-Mail hat
- [x] `scheduler.py`: `_schedule_profile_digests()` legt pro aktivem Profil einen eigenen CronJob an; `update_profile_digest_schedules()` wird vom Route-Handler aufgerufen wenn Profil-Settings sich ändern
- [x] `routes/profiles.py`: neuer `POST /profiles/<id>/notify`-Endpunkt (JSON: `email`, `notify_mode`, `digest_time`)
- [x] `settings.html`: Profile-Tab zeigt inline E-Mail/Modus/Digest-Zeit pro Profil (AJAX-Save)
- [x] Per-Profil Alert-Intervall: `alert_interval_minutes` (15/30/60/120/240/480 Min, Minimum 15); `last_alert_sent_at` pro Profil; `notify_pending()` sendet nur wenn Intervall abgelaufen, kein Claim wenn alle Profile noch im Intervall
- [x] E-Mail-Anzeige im Profil-Tab: Kompakte Status-Zeile zeigt hinterlegte E-Mail + aktiven Modus + Intervall; JS aktualisiert Zeile sofort nach Save ohne Reload
- [x] 24h-Format-Fix für alle `type="time"`-Inputs: CSS `::-webkit-datetime-edit-ampm-field { display: none }` erzwingt 24h in WebKit unabhängig von OS-Locale
- [x] `tests/test_notifier.py`: Intervall-Tests (Versand an Profile, last_alert_sent aktualisiert, Intervall nicht abgelaufen → kein Claim) — 598 Tests gesamt
- [x] Kein globaler E-Mail-Fallback: Empfänger-E-Mail im Notifications-Tab entfernt; kein `email_recipient`-Feld mehr; kein stiller Fallback in `notify_pending()` / `notify()` / `send_digest()`; blaue Erklärungsbox entfernt
- [x] Digest-Zeit + Profil-Digest-Zeit auf `type="text"` mit `pattern="[0-2][0-9]:[0-5][0-9]"` umgestellt — löst AM/PM-Anzeige in allen Browsern permanent

---

### Phase 30 – Ruhezeit (Quiet Hours) pro Profil

- [x] DB-Migration v12: `profiles` bekommt `quiet_start` (Default `20:00`) und `quiet_end` (Default `08:00`)
- [x] `notifier.py`: `_is_quiet_hours(profile, now_local)` mit korrekter Über-Mitternacht-Logik; `notify_pending()` überspringt Profile in Ruhezeit — kein Claim, Listings akkumulieren bis Ruhezeit endet
- [x] `database/profiles.py`: `update_profile_notify()` nimmt `quiet_start`/`quiet_end` entgegen
- [x] `routes/profiles.py`: `POST /profiles/<id>/notify` leitet `quiet_start`/`quiet_end` weiter
- [x] `settings.html`: Zwei Zeitfelder (Von/Bis) pro Profil; Status-Zeile zeigt 🌙 HH:MM–HH:MM; JS sendet neue Felder mit; `toggleProfileNotifyFields` blendet Ruhezeit bei Modus `off` aus
- [x] 11 neue Tests für `_is_quiet_hours` (innerhalb/außerhalb, Grenzfälle, Über-Mitternacht, Tagfenster, ungültige Eingaben, Defaults, Integration in `notify_pending`) — 629 Tests gesamt

---

### Phase 29 – Daten-Tab & Coverage-Verbesserungen

- [x] „Alte Anzeigen löschen"-Block vom Crawler-Tab in den Daten-Tab verschoben
- [x] Gemeinsames Aktivitäts-Log-Terminal im Daten-Tab (`#data-log-output`): zeigt Logs aller Daten-Tab-Operationen; alle Buttons rufen `_refreshDataLog()` / `_startDataLog()` / `_stopDataLog()` auf
- [x] Geocache-Löschung im Daten-Tab: `clear_geocache()` in `database/geocache.py`; `POST /api/clear-geocache`; Button mit Log-Refresh
- [x] CI-Fix: `test_sendet_nicht_ohne_listings` mockt jetzt `db.get_profiles` — lief lokal durch vorhandene leere DB, schlug in CI fehl
- [x] Coverage-Lücken geschlossen: 21 neue Tests für `notifier._alert_interval_elapsed` (naive tz, ungültiger String), `_send_dicts` (kein recipients-Arg, leere Liste), `_smtp_send` (Auth-Fehler, allg. Fehler), `_get_server_url` (Socket-Fallback), `api/crawl` (alle Plattformen, unbekannte Plattform, einzeln laufend), `api_test_scraper` (Exception), `api_cleanup_mismatched`, `api_availability_check`, `api/clear-geocache`, Profil-Session-Updates — 639 Tests gesamt (618 Unit + 22 UI)

---

### Phase 27 – Neue Plattformen: Willhaben.at & markt.de

- [x] **WillhabenScraper** (`app/scrapers/willhaben.py`): `__NEXT_DATA__`-JSON-Parsing (Next.js SSR), `_attr()`-Hilfsfunktion für Attributlisten, PayLivery-Parameter (Versand-Only, Default aktiv), Haversine-Radius wenn PayLivery deaktiviert
- [x] **MarktdeScraper** (`app/scrapers/markt.py`): BeautifulSoup HTML, `_city_slug()` mit Umlaut-Normalisierung, Radius als URL-Parameter, Pagination
- [x] Beide in `PLATFORM_SCRAPER_MAP` + `DEFAULT_INTERVALS` + `scrapers/__init__.py` eingetragen
- [x] `DEFAULT_SETTINGS` in `core.py` ergänzt (willhaben_*, marktde_*)
- [x] Settings-Formular: neue Plattform-Abschnitte mit PayLivery-Checkbox und Hinweistext
- [x] `allowed_keys` in `views.py` + `test-scraper`-Endpoint in `api.py` aktualisiert
- [x] Fix: `crawler_lang_filter_enabled` und `willhaben_paylivery_only` als Checkboxen korrekt behandelt
- [x] 26 neue Tests (519 gesamt)
- [x] **100% Testabdeckung** aller 6 Scraper (ebay, kleinanzeigen, markt, shpock, vinted, willhaben): 49 neue Coverage-Tests, Fix `except Exception` in `kleinanzeigen.py` — 568 Tests gesamt
- [x] Fix: Willhaben URLs (`SEO_URL` ohne führendes `/` → `BASE_URL/iad/` vorangestellt) und Bilder (`MMO` relativ → `https://cache.willhaben.at/mmo/` ergänzt)
- [x] Fix: Wortgrenzen-Matching (`\b`) jetzt auch für Einwort-Suchbegriffe — verhindert False-Positives wie „56" → „1956" oder „56m²"
- [x] Feature: Anzeigen einer Plattform im Daten-Tab löschen (Dropdown + `POST /api/clear-listings-by-platform`); Favoriten bleiben erhalten — 579 Tests gesamt

---

### Phase 31 – Scraper-Fixes & Health Check

- [x] **eBay: CSS-Selektoren nach Layout-Update** — eBay hat die Suchergebnisseite auf neue Klassen umgestellt (`s-card` statt `s-item`). `_parse()` nutzt jetzt `li.s-card`, `data-listingid`, `img.s-card__image` alt, `.s-card__price`, `a.s-card__link`. Kein Standort mehr in Suchergebnissen.
- [x] **eBay: Bot-Detection-Umgehung** — `_warmup()` fetcht einmalig die eBay-Homepage, um Session-Cookies zu initialisieren (verhindert 403). Erweiterte `Sec-*` Browser-Headers + `Referer`-Header nach Warmup.
- [x] **eBay: Rate-Limiting-Schutz** — `ebay_request_delay` (Default 10s) als Mindestabstand zwischen Suchanfragen. `_last_request`-Timestamp pro Scraper-Instanz; Delay wird am Anfang jedes `search()`-Aufrufs abgewartet.
- [x] **Shpock: Radius=0 fix** — Bei `radius_km=0` wurde bisher `distance: {radius: 0}` an die GraphQL-API gesendet → 0 Meter Filter → keine Ergebnisse. Fix: `distance`-Feld komplett weglassen wenn `radius_km=0`.
- [x] **Scraper Health Check** — 6 separate GitHub-Action-Workflows (`scraper-health-{name}.yml`), gestaffelt ab 03:00 UTC (alle 5 Min.). Jeder importiert seinen Scraper direkt und ruft einmalig `search("kinderwagen", max_results=3)` auf. Schlägt fehl wenn 0 Ergebnisse oder Exception. 6 individuelle Badges im README — man sieht sofort welche Plattform defekt ist.
- [x] 2 neue Tests (630 gesamt); `ebay_request_delay`-Setting dokumentiert
- [x] **Bugfix: Gratis-Badge bei Willhaben-Anzeigen mit Preis** — `_POSITIVE_PRICE_RE` erkannte nur `9 €` (Zahl vor €), nicht `€ 9` (Willhaben-Format). Damit griff der Price-Guard nicht, und `gratis` in der Beschreibung löste fälschlich das Badge aus. Fix: Regex um `€\s*[1-9]\d*...` erweitert; `_FREE_PRICE_RE` um `€\s*0` ergänzt. DB-Migration v13 berechnet `is_free` für alle bestehenden Listings neu. 5 neue Tests — 639 Tests gesamt.

---

### Phase 26 – Crawl-Qualität

- [x] **Wortgrenzen-Matching**: `_matches_all_words()` nutzt jetzt `\b`-Regex statt Substring-Suche — verhindert False-Positives wie „werder" → „Schwerder" oder „body" → „somebody". Cleanup-Script ebenfalls aktualisiert.
- [x] **Sprachfilter**: Setting `crawler_lang_filter_enabled` + `crawler_lang_filter_langs` (Default `de`). Anzeigen in nicht erlaubten Sprachen werden via `langdetect` herausgefiltert. Bei kurzer oder fehlender Beschreibung wird Titel+Beschreibung mit strengerer Konfidenzschwelle geprüft; nur Texte mit weniger als sechs Buchstaben, unsichere Erkennungen und Erkennungsfehler werden durchgelassen. Settings-Tab Crawler.
- [x] **Auto-Cleanup nicht passender Anzeigen**: `db.cleanup_mismatched_listings()` entfernt alle Anzeigen, deren Titel+Beschreibung nicht alle Wörter des Suchbegriffs enthalten, und trägt sie als dismissed ein. Läuft einmalig als v9-Migration beim ersten Start nach Update. Manuell auslösbar über `POST /api/cleanup-mismatched` + Button im Daten-Tab.
- [x] **Verfügbarkeits-Timestamp auf Karte**: Zeitpunkt der letzten Verfügbarkeitsprüfung als Klartext direkt auf der Anzeigenkarte (kein Badge) — „Verfügbarkeit geprüft: vor 2h" oder „Verfügbarkeit noch nicht geprüft". Mit relativem Zeitformat via `initRelativeTimes()`.
- [x] 32 neue Tests (462 gesamt)

---

## 🔜 Offene Aufgaben

Zum Umsetzen einfach den Kategorienamen nennen (z.B. „mach Tastaturkürzel") oder einzelne Tasks per Nummer (z.B. „mach 11 und 21").

---

### Features – KI-Integration

**Option B – Listing-Bewertung (Score 1–10)**
- [ ] Beim Crawl: Claude bewertet jedes neue Listing anhand von Titel + Beschreibung (Relevanz, Preis-Leistung, Zustand)
- [ ] Score wird in DB gespeichert (neues Feld `ai_score`), im Dashboard als Badge angezeigt
- [ ] Dashboard: nach Score sortieren/filtern
- [ ] Nur neue Listings werden bewertet (kein Re-Scoring bestehender)

**Option C – Smarte Benachrichtigung**
- [ ] E-Mail/Notify-Job sendet nur Listings ab konfiguriertem Mindest-Score (z.B. ≥ 7)
- [ ] Einstellung `ai_notify_min_score` in Settings
- [ ] Abhängig von Option B (Score muss vorhanden sein)

**Option D – Zustand & Details extrahieren**
- [ ] KI extrahiert aus Beschreibung: Zustand (neu/gut/gebraucht/defekt), Altersangabe, enthaltenes Zubehör
- [ ] Strukturiert gespeichert, filtert "defekt"-Anzeigen zuverlässiger als die aktuelle Keyword-Blacklist
- [ ] Wird als Tooltip/Badge im Dashboard angezeigt

**Option E – Duplikat-Erkennung verbessern**
- [ ] Aktueller Ansatz: einfacher String-Vergleich des Titelanfangs
- [ ] KI-gestützt: erkennt semantische Duplikate auch bei unterschiedlichen Titeln

**Sonstiges KI**
- [ ] Install-Script (fragt ab ob Ollama gewünscht, erkennt Hardware/Arch)

---

### Features – Benachrichtigungen

- [ ] **12** – Telegram-Bot als Alternative zu SMTP (Bot-Token + Chat-ID, Alert + Digest)
- [ ] **20** – Browser Push Notifications (Web Push API, kein E-Mail-Setup nötig)

---

### Features – Daten & Export

- [ ] **13** – CSV/JSON-Export der aktuell gefilterten Anzeigen (clientseitiger Download)
- [ ] **23** – Settings-Backup: Import/Export als JSON-Datei

---

### Features – Komfort & Bedienung

- [ ] **11** – Tastaturkürzel: j/k navigieren, f favorisieren, d dismisssen, / Suche fokussieren, ? Hilfe-Overlay
- [ ] **21** – Dark Mode (`prefers-color-scheme` + manueller Toggle, Zustand in `localStorage`)
- [ ] **22** – PWA-Manifest: App auf Smartphone installierbar (Homescreen-Icon, Offline-Splash)
