# 🔍 Marktcrawler

Siehst du eine Anzeige für einen günstigen Kinderwagen — aber immer zu spät? **Marktcrawler** durchsucht Kleinanzeigen.de, Shpock, Vinted, eBay, Willhaben.at, markt.de und Facebook Marketplace automatisch nach deinen Suchbegriffen und schickt dir eine E-Mail, sobald neue Treffer auftauchen.

Selbst gehostet und Docker-ready — läuft im Hintergrund auf einem Server, NAS oder Raspberry Pi.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?logo=flask)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-Installer-0078D4?logo=windows&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-663%20passed-brightgreen?logo=pytest)
![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)
[![Kleinanzeigen](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-kleinanzeigen.yml/badge.svg)](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-kleinanzeigen.yml)
[![eBay](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-ebay.yml/badge.svg)](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-ebay.yml)
[![Shpock](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-shpock.yml/badge.svg)](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-shpock.yml)
[![Vinted](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-vinted.yml/badge.svg)](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-vinted.yml)
[![Willhaben](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-willhaben.yml/badge.svg)](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-willhaben.yml)
[![markt.de](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-marktde.yml/badge.svg)](https://github.com/descipar/marktcrawler/actions/workflows/scraper-health-marktde.yml)

---

<img src="docs/screenshots/dashboard.png" width="700" alt="Dashboard">

📁 [Alle Screenshots ansehen](docs/screenshots/)

---

## ✨ Features

### Suche & Crawler
- **7 Plattformen gleichzeitig** — Kleinanzeigen.de, Shpock, Vinted, eBay, Willhaben.at, markt.de, Facebook Marketplace; jede mit eigenem Crawl-Intervall
- **Suchbegriffe** mit optionalem Preislimit pro Begriff; Blacklist für Ausschluss-Keywords (z.B. „defekt", „bastler")
- **Radius-Filter** mit Standort-Geocoding via OpenStreetMap; Radius 0 = kein Filter

### Benachrichtigungen
- **E-Mail-Alert (gebündelt)** — alle neuen Anzeigen alle 15 Min. kompakt per E-Mail, strukturiert nach Plattform und Suchbegriff
- **Tages-Digest** — tägliche Zusammenfassung zur konfigurierten Uhrzeit pro Profil
- **Per-Profil-Benachrichtigungen** — jedes Profil hat eigene E-Mail, Modus (Sofort / Digest / beides / stumm) und Alert-Intervall (min. 15 Min.); kein globales Empfänger-Feld

### Anzeigen & KI
- **✨ KI-Anfragetext** — generiert per Klick einen Kontakttext an den Verkäufer; bei VB-Anzeigen mit automatischem Preisvorschlag
- **⭐ Favoriten & Notizen** — Anzeigen markieren und kommentieren; Favoriten werden nie automatisch gelöscht
- **👤 Mehrbenutzer-Profile** — jedes Profil sieht „✨ Neu"-Badge für Anzeigen seit dem letzten Besuch; eigene E-Mail-Benachrichtigungen pro Profil
- **Duplikat-Erkennung & Verfügbarkeits-Check** — plattformübergreifende Duplikaterkennung; veraltete Anzeigen automatisch entfernen

📄 [Alle Features](docs/features.md)

---

## 🤖 KI-Assistent einrichten

Der KI-Assistent generiert im Anzeigen-Modal per Klick auf „✨ Generieren" einen fertigen Anfragetext an den Verkäufer. Bei VB-Anzeigen schlägt er automatisch einen Preis vor — basierend auf dem Durchschnitt der eigenen gesammelten Daten. Der Text erscheint immer in einer **editierbaren Textarea** und wird nie automatisch gesendet.

### Option 1: Cloud-API (empfohlen)

Günstig und ohne lokale Ressourcen. Ein Anfragetext kostet ca. **0,00005 €** mit Claude Haiku.

**Anthropic (Claude):**
1. API-Key erstellen: [console.anthropic.com](https://console.anthropic.com)
2. In **Einstellungen → KI-Assistent** eintragen:
   - API-Key: `sk-ant-…`
   - Modell: aus Dropdown wählen oder „🔄 Laden" für aktuelle Liste
   - Base-URL: *(leer lassen)*

**OpenAI:**
- API-Key: `sk-…` · Modell: `gpt-4o-mini` · Base-URL: *(leer lassen)*

**Groq (kostenlos, sehr schnell):**

Kostenloser Tier, ~1–3s Antwortzeit mit leistungsstarken Modellen wie `llama-3.3-70b`.

1. API-Key erstellen: [console.groq.com](https://console.groq.com)
2. In **Einstellungen → KI-Assistent** eintragen:
   - API-Key: `gsk_…`
   - Base-URL: `https://api.groq.com/openai/v1`
   - Modell: `llama-3.3-70b-versatile` oder „🔄 Laden" für aktuelle Liste

### Option 2: Lokal via Ollama

Vollständig offline, kein API-Key nötig.

> ⚠️ **Nicht für Raspberry Pi 4 geeignet.** CPU-only bedeutet 2–5 Min. pro Antwort. Für den RPi4 empfehlen wir Option 1.

```bash
# Ollama als zweiten Container starten
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d

# Modell laden (einmalig, ~1,6 GB)
docker exec marktcrawler-ollama ollama pull gemma2:2b
```

Dann in **Einstellungen → KI-Assistent**: Modell `gemma2:2b`, Base-URL `http://ollama:11434/v1`, API-Key leer.

| Modell | Größe | RAM-Bedarf |
|--------|-------|------------|
| `gemma2:2b` | 1,6 GB | 4 GB |
| `phi3:mini` | 2,3 GB | 6 GB |
| `qwen2.5:0.5b` | 400 MB | 2 GB |

---

## 📧 E-Mail einrichten

### Gmail

1. [App-Passwort erstellen](https://myaccount.google.com/apppasswords) (2FA muss aktiv sein)
2. In **Einstellungen → Benachrichtigungen** eintragen:
   - SMTP-Server: `smtp.gmail.com` · Port: `587`
   - Absender: `deine-adresse@gmail.com`
   - App-Passwort: *(das erzeugte App-Passwort)*
3. E-Mail-Empfänger werden **pro Profil** vergeben: **Einstellungen → Profile** → E-Mail-Adresse und Benachrichtigungsmodus pro Person einstellen

### Weitere Anbieter

| Anbieter | SMTP-Server | Port |
|----------|-------------|------|
| GMX | mail.gmx.net | 587 |
| Web.de | smtp.web.de | 587 |
| Outlook | smtp.office365.com | 587 |

---

## 🚀 Deployment

### Docker (empfohlen)

Läuft auf jedem Server, NAS oder Raspberry Pi (4/5, ~5 Watt, 24/7).

```bash
git clone https://github.com/descipar/marktcrawler.git
cd marktcrawler
docker compose up -d --build   # Starten
docker compose logs -f          # Logs ansehen
docker compose down             # Stoppen
git pull && docker compose up -d --build  # Update
```

Auf einem frischen Raspberry Pi zuerst Docker installieren:

```bash
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER
```

### Windows (Installer)

Für nicht-technische Nutzer: fertige `MarktcrawlerSetup.exe` aus den [Releases](https://github.com/descipar/marktcrawler/releases/latest) herunterladen und ausführen.

- Installations-Wizard auf Deutsch
- Desktop-Verknüpfung wird angelegt
- Klick auf Icon → Browser öffnet sich automatisch auf `http://localhost:5000`
- Tray-Icon in der Taskleiste (Rechtsklick → Beenden)
- Daten liegen in `%APPDATA%\Marktcrawler\` und überleben Updates

> ⚠️ Facebook Marketplace ist in der Windows-Version nicht verfügbar (benötigt Playwright).

### Lokal (ohne Docker)

```bash
git clone https://github.com/descipar/marktcrawler.git
cd marktcrawler
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py                   # http://localhost:5000
```

### Facebook Marketplace (optional)

Einmaliger interaktiver Login nötig:

```bash
docker exec -it marktcrawler python -c \
  "from app.scrapers.facebook import FacebookScraper; FacebookScraper({}).interactive_login()"
```

> ⚠️ Das automatische Auslesen von Facebook widerspricht den Nutzungsbedingungen. Nur für den privaten Gebrauch.

---

## 🔧 Entwicklung & Tests

```bash
python -m pytest tests/ -v                       # alle 640 Tests (inkl. Playwright UI-Tests)
python -m pytest tests/ --ignore=tests/test_ui.py  # nur Unit/Integration-Tests
python -m pytest tests/test_database.py -v          # einzelne Datei
```

Alle Tests laufen ohne externe Abhängigkeiten (HTTP und DB werden gemockt).

**Tech-Stack**: Python 3.12 · Flask 3 · APScheduler 3 · SQLite · Tailwind CSS (CDN) · Docker + Gunicorn

---

## 💾 Backup

```bash
cp ./data/baby_crawler.db ./backup_$(date +%Y%m%d).db
```

Anzeigen älter als 30 Tage werden automatisch bereinigt. **Favoriten werden dabei nie gelöscht.**

---

## 🧹 Datenpflege

`scripts/cleanup_mismatched_listings.py` bereinigt bestehende Anzeigen nach zwei Kriterien:

**AND-Filter** — Bei Mehrwort-Suchbegriffen (z.B. „baby werder") müssen alle Wörter in Titel oder Beschreibung stehen. Anzeigen die nur eines der Wörter enthalten werden entfernt.

**Sprachfilter** — Fremdsprachige Anzeigen (z.B. italienische Vinted-Listings) werden anhand der Beschreibung erkannt und entfernt. Fehlt eine ausreichend lange Beschreibung, wird zusätzlich der Titel mit einer strengeren Sicherheitsschwelle geprüft. Nur aktiv wenn `--lang` angegeben oder der Sprachfilter in den Einstellungen aktiviert ist.

```bash
# Bericht (kein Löschen)
DATA_DIR=./data python scripts/cleanup_mismatched_listings.py

# AND-Filter + konfigurierten Sprachfilter anwenden und löschen
DATA_DIR=./data python scripts/cleanup_mismatched_listings.py --delete

# Sprachfilter manuell erzwingen (unabhängig von DB-Einstellung)
DATA_DIR=./data python scripts/cleanup_mismatched_listings.py --lang de --delete
```

Gelöschte Anzeigen werden in `dismissed_listings` eingetragen und tauchen beim nächsten Crawl nicht erneut auf.

---

## 📄 Lizenz

[Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)

Frei nutzbar für private und nicht-kommerzielle Zwecke. Kommerzielle Nutzung nicht gestattet.

---

*Viel Erfolg bei der Schnäppchenjagd! 🔍*
