# Whatnot-Dashboard-Kit

Ein persönliches Cockpit für deinen Whatnot-Shop, gebaut mit Claude Code. Es zeigt:

- **Kennzahlen** der letzten 30 Tage und Umsatz pro Monat
- **Sendungen prüfen**: welche Sendungen ein Problem haben, mit Details und Sendungsverfolgung
- **Monat im Detail**: Tage, Top-Artikel, Top-Kunden und Shows eines Monats
- **Finanzen und Gebühren**, Bestseller, Kunden, Shows, Publikum, Versand und Sortiment
- **Steuern und Gewinn** (optional): Umsatzsteuer, Vorsteuer aus deinen Belegen, voraussichtliche Zahllast und Gewinn

Die Daten kommen über die offizielle Whatnot Seller API. Das Dashboard ist ein privates Claude-Artefakt in deinem Konto und wird auf Wunsch jeden Morgen automatisch aktualisiert.

## Was du brauchst

- Einen Whatnot-Verkäuferaccount mit Zugang zur Seller API und einem persönlichen Token, zu finden unter https://www.whatnot.com/dashboard/developer?tab=tokens
- Die Claude-Desktop-App mit Claude Code (Code-Tab)
- Python 3.10 oder neuer
- Für das Auslesen von PDF-Belegen: `pdftotext`, bei Git for Windows schon dabei (optional)

## So geht's

**Am einfachsten:** Öffne in der Claude-Desktop-App den Code-Tab mit einem leeren Ordner, zum Beispiel `C:\WhatnotDashboard`, und schreib:

> Klone https://github.com/Dethklok666/whatnot-dashboard-kit in diesen Ordner und richte das Whatnot-Dashboard ein.

**Oder von Hand:**

```bash
git clone https://github.com/Dethklok666/whatnot-dashboard-kit.git
```

Öffne danach den Ordner im Code-Tab und tippe `/einrichten`. Mit `/belege` wertest du später neue Belege aus.

Claude führt dich durch alles, was in `CLAUDE.md` steht:

- den Token eintragen (das machst du selbst in der Datei `.env`; Claude liest sie nicht)
- Shopname, Startdatum und Steuerstatus festlegen
- Daten holen
- Belege auswerten
- das Dashboard anlegen
- die tägliche Aktualisierung einrichten

## Wichtig

- **Dein Token gehört nur dir.** Gib die `.env` nie weiter, auch nicht mit diesem Ordner.
- **Belege bleiben auf deinem Rechner.** Ins Dashboard kommen nur Datum, Lieferant und Beträge, keine Kundennamen und keine Adressen.
- **Im Dashboard stehen Whatnot-Benutzernamen deiner Käufer.** Teile den Dashboard-Link nur mit Leuten, die das sehen dürfen.
- **Die Steuerzahlen sind Schätzungen, keine Steuerberatung.** Lass sie vor der Voranmeldung von deinem Steuerberater prüfen.
- **Die tägliche Aktualisierung läuft nur, wenn die Claude-App geöffnet ist.**

## Dateien

| Datei | Zweck |
|---|---|
| `CLAUDE.md` | Anleitung für Claude (Einrichtung und Pflege) |
| `einstellungen.ini.beispiel` | Vorlage für Shopname, Datenbeginn und Steuerstatus |
| `.env.example` | Vorlage für den API-Token |
| `test_verbindung.py` | Prüft, ob der Token funktioniert |
| `dashboard_daten.py` | Holt alle Daten von Whatnot nach `export/dashboard/` |
| `belege_auswertung.py` | Wertet Belege und eigene Rechnungen aus |
| `dashboard_vorbereiten.py` | Erzeugt die Dashboard-Seite aus der Vorlage |
| `shows_umsatz.py` | Export der Show-Kennzahlen als CSV für Excel |
| `dashboard/` | Seitenvorlage, Beschreibung der Datenquellen und Vorlage für die geplante Aufgabe |
| `belege/`, `rechnungen_ausgehend/` | Hier legst du deine Belege ab |
| `.claude/commands/` | Befehle `/einrichten` und `/belege` für Claude Code |

## Datenschutz im Repo

Die `.gitignore` hält Token, Einstellungen, Exportdaten, Belege und die `*_manuell.csv` aus Git heraus. Wenn du deinen eigenen Fork pflegst, prüf trotzdem vor jedem `git push` mit `git status`, dass keine persönlichen Dateien dabei sind.

## Lizenz

MIT. Siehe `LICENSE`. Nutzung auf eigene Verantwortung, die Steuerberechnung ersetzt keine Steuerberatung.
