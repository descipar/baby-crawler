# Marktcrawler – Feature-Dokumentation

Vollständige Beschreibung aller Features, der Admin-UI und der API-Endpunkte.

## Inhaltsverzeichnis

- [Suche & Filterung](#suche--filterung)
- [Anzeigen-Verwaltung](#anzeigen-verwaltung)
- [Benachrichtigungen & Automatisierung](#benachrichtigungen--automatisierung)
- [KI-Assistent](#ki-assistent)
- [Admin-UI: Dashboard](#admin-ui-dashboard)
- [Admin-UI: Einstellungen](#admin-ui-einstellungen)
- [API-Endpunkte](#api-endpunkte)
- [Architektur](#architektur)

---

## Suche & Filterung

### Suchbegriffe
Suchbegriffe werden in der Sidebar verwaltet: hinzufügen, aktivieren/deaktivieren, löschen. Beim Löschen eines Suchbegriffs werden auch alle zugehörigen Anzeigen entfernt. Pro Suchbegriff kann eine optionale Preisobergrenze gesetzt werden (Stift-Icon → Eingabefeld → ENTER), die den globalen Plattform-Maximalpreis überschreibt.

### Plattformen
Gleichzeitig durchsuchbar: **Kleinanzeigen.de**, **Shpock**, **Vinted**, **eBay**, **Willhaben.at**, **markt.de**, **Facebook Marketplace** (optional). Jede Plattform hat ein eigenes konfigurierbares Crawl-Intervall (Standard: Kleinanzeigen 15 Min., Shpock/Vinted/Willhaben 30 Min., eBay/markt.de/Facebook 60 Min.).

**Willhaben.at** — Österreichisches Kleinanzeigen-Portal. Der Scraper liest `__NEXT_DATA__`-JSON aus der Next.js-Seite aus. Standard: nur PayLivery-Angebote (`willhaben_paylivery_only = 1`) — das sind Versand-Angebote, die nach Deutschland geliefert werden. Bei aktiviertem PayLivery wird der Radius-Filter deaktiviert (Standort in Österreich ist irrelevant). Mit `paylivery_only = 0` können auch Abholangebote gecrawlt werden; dann wird der Haversine-Radius auf COORDINATES-Attribute angewendet.

**markt.de** — Deutsches Kleinanzeigen-Portal mit Fokus auf regionale Schnäppchen. Der Scraper parst HTML via BeautifulSoup. Die Suchanfrage wird als `markt.de/{city-slug}/suche/{term}/` aufgebaut; Umlaute im Städtenamen werden automatisch normalisiert (München → muenchen). Der Radius wird als URL-Parameter übergeben.

### Suchbegriff-Matching (Wortgrenzen, AND-Logik)
Alle Suchbegriffe — auch einwörtige — werden mit `\b`-Wortgrenzen (Regex) gegen Titel und Beschreibung geprüft. Das verhindert False-Positives wie „56" → „1956" oder „56m²", oder „werder" → „Schwerder". Bei Mehrwort-Begriffen (z.B. „baby werder") müssen **alle** Wörter vorkommen (AND-Logik). Anzeigen, die den Filter nicht bestehen, werden still übersprungen.

### Blacklist
Stichworte wie „defekt" oder „bastler" können zeilenweise in die Blacklist eingetragen werden. Groß-/Kleinschreibung wird ignoriert. Blacklistete Anzeigen werden still übersprungen — kein Speichern, keine Benachrichtigung.

### Sprachfilter
Optionaler Filter, der Anzeigen in unerwünschten Sprachen herausfiltert (Settings → Crawler & Daten). Aktiviert: `crawler_lang_filter_enabled = 1`, erlaubte Sprachen kommagetrennt in `crawler_lang_filter_langs` (Default: `de`). Analysiert werden ausschließlich natürliche Beschreibungstexte mit mindestens 12 Buchstaben; Produkttitel werden wegen der hohen Fehlerrate bei Marken- und Modellnamen nie allein klassifiziert. Da die Vinted-Katalog-API keine Beschreibung liefert, liest der Scraper bei neuen, noch unbekannten Treffern den HTML-Kopf der Detailseite und übernimmt deren Meta-Beschreibung. Detailbeschreibungen werden prozessweit gecacht, bereits gespeicherte oder ausgeblendete Anzeigen nicht erneut geladen; fehlgeschlagene Abrufe werden einmal wiederholt. Nur eine fremde Sprache mit mindestens 95 % Erkennungssicherheit wird abgelehnt. Kürzere oder fehlende Beschreibungen, unsichere Erkennungen und technische Fehler werden durchgelassen. Spracherkennung via `langdetect`-Bibliothek (lazy import — kein Fehler wenn nicht installiert).

### Radius-Filter
Radius pro Plattform konfigurierbar in km. Geocoding über OpenStreetMap/Nominatim, Distanzberechnung via Haversine-Formel. Ergebnisse werden gecacht (kein doppelter API-Aufruf). **Radius 0 = kein Filter** (kein Geocoding-Aufruf).

### Dashboard-Filter
- **Suchbegriff-Filter** — Klick auf einen Suchbegriff in der Sidebar filtert die Liste; mehrere Begriffe gleichzeitig wählbar (Toggle). Aktive Begriffe werden blau hervorgehoben.
- **Exclude-Filter** — Freitexteingabe mit 400 ms Debounce; blendet Anzeigen aus deren Titel oder Beschreibung den Begriff enthält. ×-Button zum Zurücksetzen.
- **Altersfilter** — nur Anzeigen der letzten 3h / 6h / 24h / 48h anzeigen (Dropdown).
- **Plattform-Filter** — nur eine Plattform anzeigen (Dropdown, nur tatsächlich vorhandene Plattformen).
- **Entfernungsfilter** — max. Entfernung in km.
- **Gratis-Filter** — nur kostenlose Anzeigen.
- **Favoriten-Filter** — nur markierte Anzeigen.

Der Filter-Bereich ist ein-/ausklappbar. Anzahl aktiver Filter wird als Badge am Toggle-Button angezeigt. Zustand wird in `localStorage` gespeichert.

### Sortierung
Sortierbar nach: Datum (neu → alt, Standard), Datum (alt → neu), Preis (auf-/absteigend), Entfernung. Favoriten stehen unabhängig von der Sortierung immer oben.

---

## Anzeigen-Verwaltung

### Detail-Modal
Klick auf eine Karte öffnet das Detail-Modal mit Vollbild-Bild, Preis, Standort, vollständiger Beschreibung, Notiz-Textarea und KI-Anfragetext-Generator. „↗ öffnen" auf der Karte führt direkt zur Anzeige auf der Plattform.

### Favoriten
⭐ auf der Karte oder im Modal toggelt den Favoriten-Status (AJAX, kein Seitenneustart). Favoriten werden beim automatischen Aufräumen (clear_old_listings) **nie** gelöscht. Dashboard-Filter: `?favorites=1`.

### Notizen
Pro Anzeige eine private Notiz hinterlegen — editierbar im Detail-Modal, Auto-Save. Leer lassen zum Löschen. Karten mit Notiz zeigen ein 💬-Badge.

### Ausblenden (Dismiss)
✕-Button auf der Karte blendet eine Anzeige dauerhaft aus. Sie wird sofort gelöscht und beim nächsten Crawl nicht wieder angezeigt — auch wenn sie neu gefunden wird.

### Gratis-Erkennung
Anzeigen mit Preis 0 € / „zu verschenken" / „gratis" werden automatisch erkannt und mit 🎁-Badge gekennzeichnet. Ein echter Preis > 0 hat immer Vorrang, damit „gratis Zubehör dabei" kein False-Positive auslöst.

### Duplikat-Erkennung
Gleiche `listing_id` wird nie doppelt gespeichert. Plattformübergreifend: gleicher Titelanfang auf einer anderen Plattform (letzte 30 Tage) wird als Amber-Badge „📋 auch auf Shpock" markiert.

### Entfernungsanzeige
Luftlinie vom eigenen Heimstandort zu jeder Anzeige, berechnet via Nominatim + Haversine. Heimstandort in **Einstellungen → Crawler & Daten** als Stadtname eingeben.

### Preisstatistik
Tabelle auf der Info-Seite (`/info`) zeigt Durchschnitt, Min, Max und Gratis-Zähler pro Suchbegriff (`GET /api/stats`).

### Relative Zeitangaben
Timestamps werden als „vor 2h" / „vor 30 Min." angezeigt (Tooltip mit absolutem Datum).

### Mehrbenutzer-Profile
Mehrere Personen können die App gemeinsam nutzen, ohne sich gegenseitig die „Neu"-Badges wegzunehmen. Beim Öffnen der App wird ein Profil gewählt (Netflix-Stil). Jedes Profil merkt sich den eigenen `last_seen_at`-Zeitstempel — Anzeigen, die nach dem letzten Besuch gefunden wurden, tragen das **✨ Neu**-Badge. Suchbegriffe und Einstellungen sind global geteilt. Profile werden in **Einstellungen → Profile** verwaltet (anlegen, umbenennen, Emoji setzen, löschen). Der aktive Nutzer ist in der Navbar sichtbar; Wechseln per Klick.

Jedes Profil kann zusätzlich eine **eigene E-Mail-Adresse** und einen **Benachrichtigungsmodus** haben (konfigurierbar direkt im Profile-Tab der Einstellungen):
- **⚡ Sofort-Alert** — gebündelt, maximal alle `alert_interval_minutes` Minuten (Minimum 15, Spamschutz)
- **📋 Nur Tages-Digest** — täglich zur profil-eigenen Digest-Uhrzeit
- **Beides** — Alert + Digest
- **Keine E-Mails** — stumm (nur Neu-Badge im Dashboard)

**Ruhezeit (Quiet Hours)** — Pro Profil konfigurierbar ab wann bis wann keine Mails verschickt werden (Standard: 20:00–08:00). Während der Ruhezeit werden Listings **nicht** als notified markiert — sie akkumulieren und werden mit der ersten Mail nach Ende der Ruhezeit gesammelt zugestellt. Über-Mitternacht-Fenster werden korrekt behandelt (z.B. 22:00–06:00).

Es gibt kein globales Empfänger-Feld mehr. Wenn kein Profil eine E-Mail hat, werden keine Mails verschickt. Endpoint: `POST /profiles/<id>/notify` (JSON: `{"email": "...", "notify_mode": "immediate|digest_only|both|off", "digest_time": "HH:MM", "alert_interval_minutes": 15, "quiet_start": "HH:MM", "quiet_end": "HH:MM"}`).

### Pagination
30 Anzeigen pro Seite, „Mehr laden"-Button lädt weitere per AJAX.

### Verfügbarkeits-Check
Prüft periodisch per HEAD-Request ob Anzeigen noch online sind. HTTP 404/410 → automatisch löschen (inkl. Favoriten). Konfigurierbar: Aktiviert/Deaktiviert, Intervall in Stunden. Manuell auslösbar per Button in den Einstellungen. Anzeigen jünger als 60 Minuten werden übersprungen. Zeitpunkt der letzten Prüfung wird als Klartext direkt auf der Anzeigenkarte angezeigt („Verfügbarkeit geprüft: vor 2h" oder „Verfügbarkeit noch nicht geprüft").

### Auto-Cleanup nicht passender Anzeigen
`db.cleanup_mismatched_listings()` durchsucht alle gespeicherten Anzeigen und entfernt solche, deren Titel + Beschreibung nicht alle Wörter des zugehörigen Suchbegriffs enthalten (gleiche `\b`-Regex wie der Crawler). Entfernte Anzeigen werden als dismissed eingetragen und tauchen beim nächsten Crawl nicht erneut auf. Läuft einmalig automatisch als DB-Migration v9 beim ersten Start nach Update. Manuell auslösbar über `POST /api/cleanup-mismatched` + Button im Daten-Tab der Einstellungen.

### Anzeigen einer Plattform löschen
Im Daten-Tab der Einstellungen: Plattform aus Dropdown wählen → Löschen. `db.clear_listings_by_platform(platform)` löscht alle Nicht-Favoriten der gewählten Plattform und trägt sie in `dismissed_listings` ein — beim nächsten Crawl werden sie frisch eingelesen. Favoriten bleiben erhalten. Endpoint: `POST /api/clear-listings-by-platform` (`{"platform": "Willhaben"}`).

---

## Benachrichtigungen & Automatisierung

### E-Mail-Alert (gebündelt)
Alle 15 Min. prüft der Notify-Job ob es neue (nicht gemeldete) Anzeigen gibt. Falls ja, wird eine gebündelte HTML-E-Mail versandt — strukturiert nach Plattform → Suchbegriff mit Inhaltsverzeichnis. Gratis-Items werden grün hervorgehoben. Jede Anzeige wird nur einmal gemeldet. Mit Per-Profil-E-Mails: `notify_pending()` sendet an alle Profile mit `notify_mode=immediate` oder `both`, jeweils an die profil-eigene Adresse.

### Manueller Crawl
Per Knopfdruck im Dashboard: einzelne Plattform oder alle aktiven. Live-Log-Terminal zeigt den Fortschritt. Bei neuen Treffern wird sofort eine E-Mail versandt (unabhängig vom 15-Min.-Job).

### Tages-Digest
Täglich zur konfigurierten Uhrzeit (z.B. `19:00`) eine Zusammenfassung aller heute gefundenen Anzeigen als HTML-E-Mail. Unabhängig vom gebündelten Alert — eine Anzeige kann in beiden auftauchen. Per-Profil: `scheduler._schedule_profile_digests()` legt für jedes Profil mit `notify_mode=digest_only` oder `both` und eigener E-Mail-Adresse einen eigenen CronJob mit der profil-spezifischen `digest_time` an.

### Pro-Plattform-Scheduler
Jede Plattform hat ihr eigenes konfigurierbares Crawl-Intervall. Der Scheduler läuft im Hintergrund — kein manueller Cronjob nötig.

### Scraper Health Check (GitHub Action)
6 separate GitHub-Action-Workflows (`scraper-health-{name}.yml`), gestaffelt ab 03:00 UTC (alle 5 Min.): Kleinanzeigen, eBay, Shpock, Vinted, Willhaben, markt.de. Jeder importiert seinen Scraper direkt aus dem Projekt (`importlib`) und ruft einmalig `search("kinderwagen", max_results=3)` auf — keine Mocks, keine neuen Dateien. Geocoding deaktiviert (`radius=0` / `paylivery_only=1`). Facebook übersprungen (braucht interaktiven Login). Exit-Code 1 bei 0 Ergebnissen oder Exception. 6 individuelle Badges im README — man sieht sofort welche Plattform defekt ist (z.B. eBay oft instabiler als Kleinanzeigen).

---

## KI-Assistent

### Anfragetext-Generator
Im Detail-Modal per Klick auf „✨ Generieren" wird ein höflicher Kontakttext an den Verkäufer generiert. Der Text erscheint in einer editierbaren Textarea — nie automatisch gesendet.

### VB-Preisvorschlag
Bei Anzeigen mit „Verhandlungsbasis" schlägt die KI automatisch einen Preis vor: 85% des Durchschnittspreises aus den eigenen gesammelten Daten, auf 5 € gerundet.

### Persönliche Hinweise (`ai_prompt_hints`)
Eigene Instruktionen für alle generierten Texte, z.B. „Wir sind eine Familie mit zwei Kindern" oder „Keine Besichtigung bei Kleidung nötig". Werden an jeden Prompt angehängt.

### Modell-Selector
Dropdown mit vordefinierten Modellen nach Anbieter (Anthropic / OpenAI / Groq / Ollama). „🔄 Laden"-Button holt die aktuelle Modellliste direkt vom Anbieter. Provider wird automatisch erkannt: API-Key-Prefix `sk-ant-` → Anthropic, `sk-` → OpenAI; bei gesetzter Base-URL → Hostname `localhost`/`ollama` → Ollama (`/api/tags`), sonst → OpenAI-kompatibler Anbieter (`/v1/models` mit Bearer-Auth, z.B. Groq).

### Betriebsmodi
| Modus | Konfiguration |
|-------|--------------|
| Anthropic (Cloud) | API-Key `sk-ant-…`, Modell wählen, Base-URL leer |
| OpenAI (Cloud) | API-Key `sk-…`, Modell wählen, Base-URL leer |
| Groq (Cloud, kostenlos) | API-Key `gsk_…`, Base-URL `https://api.groq.com/openai/v1`, Modell z.B. `llama-3.3-70b-versatile` |
| Ollama (lokal) | Base-URL `http://ollama:11434/v1`, kein API-Key nötig |

---

## Admin-UI: Dashboard

| Element | Funktion |
|---------|----------|
| Suchbegriff-Sidebar | Hinzufügen, aktivieren/deaktivieren, löschen (inkl. Anzeigen), Preislimit pro Term, Filter-Klick |
| Plattform-Statustabelle | Status (✓ / ⟳ / deaktiviert), letzter Lauf, nächster Lauf, neue Anzeigen pro Plattform |
| Filter-Leiste | Sortierung, Altersfilter, Plattform, Entfernung, Gratis, Favoriten, Exclude-Freitext |
| Anzeigen-Karte | Bild, Titel, Preis, Standort, Entfernung, Badges; ★ Favorit, ✕ Dismiss, ↗ öffnen |
| Detail-Modal | Vollbild-Bild, Beschreibung, Notiz-Textarea, KI-Anfragetext-Generator |
| 🚀 Jetzt crawlen | Startet manuellen Crawl mit Live-Log; E-Mail bei neuen Treffern |
| 📊 Preisstatistik | Aufklappbare Tabelle mit Avg/Min/Max/Gratis pro Suchbegriff |
| Filter-Panel | Aus-/einklappbar; aktive Filter-Anzahl als Badge |

---

## Admin-UI: Einstellungen

Die Einstellungsseite ist in fünf Tabs gegliedert. Deaktivierte Plattformen werden optisch gedimmt. Der Speichern-Button ist sticky am Seitenende. Ungespeicherte Änderungen lösen einen Browser-Dialog beim Verlassen aus.

| Bereich | Tab | Konfigurierbar |
|---------|-----|---------------|
| Kleinanzeigen.de | Plattformen | Aktiviert, Max. Preis, Standort-Slug, Radius, Crawl-Intervall, Test-Button |
| Shpock | Plattformen | Aktiviert, Max. Preis, Standort, Radius (0 = kein Filter), Crawl-Intervall, Test-Button |
| Vinted | Plattformen | Aktiviert, Max. Preis, Standort, Radius (0 = kein Filter), Crawl-Intervall, Test-Button |
| eBay | Plattformen | Aktiviert, Max. Preis, Standort (PLZ oder Stadt), Radius, Crawl-Intervall, Test-Button |
| Willhaben.at | Plattformen | Aktiviert, Max. Preis, Standort, Radius, PayLivery-Only, Crawl-Intervall, Test-Button |
| markt.de | Plattformen | Aktiviert, Max. Preis, Standort, Radius, Crawl-Intervall, Test-Button |
| Facebook Marketplace | Plattformen | Aktiviert, Max. Preis, Standort, Crawl-Intervall |
| E-Mail | Benachrichtigungen | SMTP-Server/-Port, Absender, App-Passwort, Alert-Betreff, Digest-Betreff |
| Tages-Digest | Benachrichtigungen | Aktiviert (global), Digest-Betreff |
| Crawler | Crawler | Max. Ergebnisse pro Suche, Pause zwischen Anfragen (s), Blacklist, Sprachfilter, Heimstandort, Verfügbarkeits-Check |
| Datenverwaltung | 🗑️ Daten | Verfügbarkeits-Check starten, Bereinigen, Plattform löschen, Alle löschen, Alte Anzeigen löschen (Stunden), Geocache löschen, Aktivitäts-Log-Terminal |
| KI-Assistent | KI-Assistent | Aktiviert, API-Key, Modell (Selector + Live-Fetch), Persönliche Hinweise, Base-URL |
| Profile | Profile | Anlegen (Name + Emoji), umbenennen, löschen; pro Profil: E-Mail-Adresse, Modus, Alert-Intervall, Digest-Uhrzeit, Ruhezeit (Von/Bis) |

---

## API-Endpunkte

| Method | URL | Beschreibung |
|--------|-----|--------------|
| GET | `/` | Dashboard |
| GET | `/settings` | Einstellungsseite |
| POST | `/settings` | Einstellungen speichern |
| POST | `/terms` | Suchbegriff hinzufügen |
| POST | `/terms/<id>/delete` | Suchbegriff + Anzeigen löschen |
| POST | `/terms/<id>/toggle` | Aktivieren / Deaktivieren |
| POST | `/terms/<id>/max-price` | Preis-Schwelle setzen (`{"max_price": N}`) |
| POST | `/listings/<id>/favorite` | Favorit toggeln |
| POST | `/listings/<id>/dismiss` | Anzeige dauerhaft ausblenden |
| POST | `/listings/<id>/note` | Notiz setzen/löschen (`{"note": "..."}`) |
| GET | `/api/listings` | Anzeigen als JSON (`?term=`, `?platform=`, `?limit=`, `?offset=`, `?favorites=`, `?free=`, `?max_age=`, `?max_distance=`, `?sort=`, `?exclude=`) |
| GET | `/api/status` | Crawler-Status inkl. `platforms`-Array (Status, letzter/nächster Lauf, neue Anzeigen) |
| GET | `/api/stats` | Preisstatistik pro Suchbegriff (Avg/Min/Max/Gratis) |
| GET | `/api/platforms` | Distinct Plattformen der gespeicherten Anzeigen |
| GET | `/api/ai-models` | Modellliste vom konfigurierten Anbieter (Anthropic/OpenAI/Ollama) |
| POST | `/api/crawl` | Crawl manuell starten |
| POST | `/api/test-scraper` | Scraper-Verbindung testen (`{"platform": "kleinanzeigen"}`) |
| POST | `/api/listings/<id>/contact-text` | KI-Anfragetext generieren |
| POST | `/api/availability-check` | Verfügbarkeits-Check manuell starten |
| POST | `/api/cleanup-mismatched` | Nicht passende Anzeigen bereinigen + dismissen (JSON: `{"deleted": N}`) |
| POST | `/api/clear-listings-by-platform` | Anzeigen einer Plattform löschen + dismissen (`{"platform": "Willhaben"}`) |
| POST | `/api/clear-listings-by-age` | Anzeigen löschen + dismissen älter als X Stunden (`{"hours": N}`) |
| POST | `/api/clear-geocache` | Geocache leeren (`{"status": "ok", "deleted": N}`) |
| GET | `/api/check-updates` | GitHub-Update-Check; liefert `{status, updates, count, repo_url}` |
| GET | `/api/log` | Log-Puffer als JSON-Array (letzte 200 Zeilen) |
| GET | `/profiles/select` | Profil-Auswahl (nur wenn Profile existieren) |
| POST | `/profiles/select/<id>` | Profil aktivieren |
| POST | `/profiles/logout` | Session leeren |
| POST | `/profiles` | Neues Profil anlegen |
| POST | `/profiles/<id>/update` | Profil umbenennen / Emoji ändern |
| POST | `/profiles/<id>/delete` | Profil löschen |
| POST | `/profiles/<id>/notify` | Benachrichtigungseinstellungen setzen (JSON: `email`, `notify_mode`, `digest_time`, `alert_interval_minutes`) |

---

## Architektur

```
marktcrawler/
├── Dockerfile / docker-compose.yml / docker-compose.ollama.yml
├── requirements.txt / pytest.ini
├── run.py                  # Einstiegspunkt (Flask dev server + load_dotenv)
├── data/                   # Persistentes Volume (SQLite-DB, FB-Session)
├── docs/
│   └── screenshots/        # UI-Vorschaubilder
├── .github/workflows/
│   ├── ci.yml                          # Tests bei jedem Push/PR
│   ├── scraper-health-kleinanzeigen.yml  # Health Check 03:00 UTC
│   ├── scraper-health-ebay.yml           # Health Check 03:05 UTC
│   ├── scraper-health-shpock.yml         # Health Check 03:10 UTC
│   ├── scraper-health-vinted.yml         # Health Check 03:15 UTC
│   ├── scraper-health-willhaben.yml      # Health Check 03:20 UTC
│   └── scraper-health-marktde.yml        # Health Check 03:25 UTC
├── tests/                  # 630 Unit-Tests + 22 Playwright UI-Tests
│   ├── conftest.py
│   ├── test_crawler.py
│   ├── test_crawl_run.py
│   ├── test_database.py
│   ├── test_geo.py
│   ├── test_notifier.py
│   ├── test_routes.py
│   ├── test_scrapers.py
│   ├── test_checker.py
│   ├── test_ai.py
│   └── test_ui.py          # Playwright End-to-End
└── app/
    ├── __init__.py         # Flask App Factory, DB + Scheduler initialisieren; SECRET_KEY-Persistenz
    ├── database/           # SQLite-Schicht (kein ORM), versioniertes Migrations-Framework
    │   ├── __init__.py     # Re-Exports aller öffentlichen Symbole
    │   ├── core.py         # DB-Pfad, get_db(), init_db(), Migrations
    │   ├── listings.py     # save_listing(), get_listings(), claim_unnotified_listings()
    │   ├── geocache.py     # Geocoding-Cache (lowercase-normalisiert)
    │   └── …               # settings, search_terms, profiles, stats
    ├── routes/             # Alle Flask-Routen & REST-API (Blueprint "main")
    │   ├── __init__.py     # Blueprint-Definition
    │   ├── views.py        # HTML-Routen (Dashboard, Settings, …)
    │   ├── api.py          # REST-API (/api/*)
    │   ├── profiles.py     # /profiles/*-Routen
    │   └── _helpers.py     # Plattform-Konstanten, build_platform_stats()
    ├── crawler.py          # Crawl-Orchestrierung (Thread-safe, threading.Lock)
    ├── checker.py          # Verfügbarkeits-Check (HEAD-Requests, Running-Guard)
    ├── scheduler.py        # APScheduler: Pro-Plattform-Crawl + Notify-Job + Digest + Checker
    ├── notifier.py         # SMTP: gebündelter Alert + Sofort (manuell) + Digest
    ├── ai.py               # KI-Assistent: Anfragetext + Provider-Erkennung (Claude/OpenAI/Ollama)
    ├── geo.py              # Nominatim-Geocoding + Haversine + DB-Cache
    ├── scrapers/
    │   ├── base.py         # Listing-Dataclass, BaseScraper ABC, Hilfsfunktionen
    │   ├── kleinanzeigen.py  # requests + BeautifulSoup
    │   ├── shpock.py         # GraphQL-API
    │   ├── vinted.py         # REST-API mit Session-Cookie; Altersfilter via created_at_ts
    │   ├── ebay.py           # requests + BeautifulSoup; URL-Encoding mit quote_plus
    │   ├── willhaben.py      # __NEXT_DATA__ JSON-Parsing; PayLivery-Filter; Haversine-Radius
    │   ├── markt.py          # requests + BeautifulSoup; Umlaut-Slug für Stadt-URL
    │   └── facebook.py       # Playwright headless
    └── templates/
        ├── base.html              # Navbar, Flash-Messages, Tailwind
        ├── index.html             # Dashboard
        ├── settings.html          # Einstellungsformular (5 Tabs)
        ├── profiles_select.html   # Profil-Auswahl (Netflix-Stil)
        └── _listing_card.html     # Anzeigenkarte (Jinja2-Partial)
```

**Tech-Stack**: Python 3.12 · Flask 3 · APScheduler 3 · SQLite (kein ORM) · Tailwind CSS via CDN (kein Build-Step) · Gunicorn 1 Worker · Docker + docker-compose
