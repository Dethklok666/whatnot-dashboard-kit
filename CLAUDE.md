# Whatnot-Dashboard-Kit: Anleitung für Claude

Dieser Ordner holt Daten eines Whatnot-Shops über die Whatnot Seller API und zeigt sie in einem Claude-Dashboard-Artefakt an. Dazu gehören Kennzahlen, Sendungen, Monatsansicht, Finanzen, Kunden und Shows. Optional berechnet er aus den Belegen Umsatzsteuer, Vorsteuer und Gewinn (deutsches Steuerrecht). Antworte dem Nutzer auf Deutsch, in einfachen Worten.

## Regeln, die immer gelten

- **Öffne, lies oder zeige niemals `.env`.** Gib den Token nirgends aus. Der Nutzer trägt ihn selbst ein, die Skripte lesen ihn.
- **Belege und eigene Rechnungen enthalten persönliche Daten.** Das sind die Ordner `belege/`, `rechnungen_ausgehend/` und die `*_manuell.csv`.
  - Sie bleiben lokal. Lade nie PDFs oder Bilder ins Dashboard hoch, nur die erzeugten CSVs `belege.csv` und `ausgang.csv`.
  - Diese CSVs enthalten keine Kundennamen und keine Adressen. Trag in `ausgang_manuell.csv` deshalb nie Kundennamen ein.
- **Käuferadressen und Nachrichten werden nicht gespeichert.** Whatnot-Benutzername und Anzeigename stehen in `orders.csv` und `shipments.csv`. Weise den Nutzer darauf hin, dass jeder mit Zugriff auf das Dashboard sie sieht.
- **Steuerzahlen sind Schätzungen, keine Steuerberatung.** Sag das jedes Mal dazu, wenn du sie nennst.
- **Skripte immer mit `python -X utf8 <skript>` im Projektordner starten**, nicht mit `-I`, sonst finden sie ihre Module nicht. Sie brauchen nur die Standardbibliothek, Python 3.10 oder neuer.

## Ersteinrichtung

Arbeite die Schritte der Reihe nach ab und frag nach, wo der Nutzer etwas tun oder entscheiden muss.

1. **Voraussetzungen prüfen.**
   - `python --version` muss 3.10 oder neuer sein.
   - Für das Auslesen von PDF-Belegen braucht es `pdftotext`. Es ist bei Git for Windows unter `C:\Program Files\Git\mingw64\bin\pdftotext.exe` dabei, sonst über Poppler. Fehlt es, funktioniert der Rest trotzdem. Belege trägst du dann von Hand in die `*_manuell.csv` ein.
   - Dashboard und tägliche Aktualisierung brauchen die Claude-Desktop-App (Code-Tab) mit Artefakten und geplanten Aufgaben.

2. **Token.**
   - Der Nutzer erzeugt im Whatnot Developer-Dashboard unter https://www.whatnot.com/dashboard/developer?tab=tokens einen persönlichen Token. Er braucht Leserechte für Bestellungen, Sendungen, Produkte, Shows und Berichte sowie das Recht, Berichte zu erstellen.
   - Dann kopiert er `.env.example` zu `.env` und ersetzt `HIER_TOKEN_EINFUEGEN` durch den Token. Das macht er selbst, du fasst die Datei nicht an.
   - Prüfe danach mit `python -X utf8 test_verbindung.py`. Erwartet wird HTTP 200 und das eigene Whatnot-Profil.

3. **Einstellungen.** Kopiere `einstellungen.ini.beispiel` zu `einstellungen.ini` und frag den Nutzer:
   - Wie soll der Shop im Dashboard heißen?
   - Seit wann verkauft er auf Whatnot? Das ergibt `daten_ab`.
   - Welches Steuerjahr soll berechnet werden?
   - Ist er Kleinunternehmer, regelbesteuert, oder ab einem bestimmten Datum regelbesteuert? Das ergibt `regelbesteuert_ab`. Frag nach, ob das mit Finanzamt oder Steuerberater abgestimmt ist.

4. **Daten holen:** `python -X utf8 dashboard_daten.py`.
   - Der erste Lauf kann 10–20 Minuten dauern. Starte ihn im Hintergrund mit Timeout.
   - Danach liegen acht CSVs in `export/dashboard/`.
   - Bei HTTP 403 fehlt dem Token ein Recht.

5. **Belege (optional, für Steuern und Gewinn).**
   - Der Nutzer legt Eingangsrechnungen in `belege/` ab, Unterordner sind erlaubt. Eigene Rechnungen außerhalb von Whatnot kommen nach `rechnungen_ausgehend/`.
   - Dann `python -X utf8 belege_auswertung.py`.
   - Für jede Datei, die unter „NICHT ERKANNT“ steht: Lies den Beleg (`pdftotext -enc UTF-8 -layout`, bei Scans das Bild) und trag eine Zeile in `belege_manuell.csv` bzw. `ausgang_manuell.csv` ein. Das Skript legt beide Dateien beim ersten Lauf an. Die Dateien sind mit Semikolon getrennt und haben Punkt als Dezimalzeichen. `datei` ist der Pfad relativ zum jeweiligen Ordner.
   - Danach das Skript erneut ausführen, bis nichts mehr fehlt.
   - **Kategorien:** Wareneinkauf; Zubehör & Verpackung; Porto; Messe & Events; Werbung & Druck; Technik & Ausstattung; Software & Gebühren.
   - **Status:**
     - `abziehbar`: ordentliche Rechnung mit ausgewiesener deutscher USt und Steuernummer oder USt-ID des Lieferanten.
     - `prüfen`: USt ist unsicher, zum Beispiel keine Steuernummer, Bestellbestätigung statt Rechnung, Proforma, ausländische USt oder privater Anteil. Schreib den Grund in `hinweis`.
     - `keine USt`: Privatkauf, Kleinunternehmer, Differenzbesteuerung (§ 25a) oder 0 %.
     - `nicht abziehbar`: zum Beispiel Bewirtung privat.
     - `Duplikat`: Beleg liegt doppelt vor. Beträge auf 0 setzen.
   - Schreib bei `ausgang_manuell.csv` keine Kundennamen in `artikel` oder `hinweis`.
   - Auch ohne Belege muss das Skript einmal laufen. Es erzeugt dann leere `belege.csv` und `ausgang.csv`, die das Dashboard braucht.

6. **Seite erzeugen:** `python -X utf8 dashboard_vorbereiten.py`. Das erzeugt `export/dashboard/seite.json` und `export/dashboard/datenquellen.json`.

7. **Dashboard-Artefakt anlegen.**
   - Rufe das Artifact-Tool mit `action: "quickstart"` und `intent: "other"` auf und lege ein Artefakt vom Dashboard-Typ an. Titel: „<Shopname> Cockpit“. Folge den Anweisungen, die der Typ beim Anlegen mitgibt.
   - Wenn es keinen Dashboard-Typ gibt, sag das dem Nutzer. Dann geht nur die lokale Ansicht `export/dashboard/index.html`, und die braucht trotzdem die Artefakt-Laufzeit.
   - Lade jede der zehn CSVs aus `export/dashboard/` einzeln als Asset hoch (`asset: true`, eine Datei pro Aufruf). Es sind: shows, upcoming, orders, order_items, shipments, products, daily, finance, belege, ausgang.
   - Lege mit EINEM ArtifactData-`batch` an:
     - je Datenquelle ein Dokument `datasets/<id>`. Die Felder kommen aus `datenquellen.json` (title, description, schedule, staleAfterHours). Dazu kommen `source: {format: "csv", kind: "file", name: <Datei>, url: "/_blob/<id>"}`, `updated: {at, by}` und `edit: {via: "claude", at}`.
     - `files/index.html` aus `seite.json`, per `file_path`. Wenn das Dokument schon existiert, mit dessen `if_version`.
   - Öffne das Dashboard und prüf, dass `data/users/me/check` den Status `passed` bekommt. Bei `failed` lies die Meldung und behebe den Fehler.
   - Leg die Dashboard-URL in `einstellungen.ini` als Kommentar ab, damit du sie später wiederfindest.

8. **Tägliche Aktualisierung.**
   - Fülle `dashboard/geplante_aufgabe.vorlage.md` aus: `{{SHOP_NAME}}`, `{{DASHBOARD_URL}}` und `{{ORDNER}}`, also den absoluten Pfad dieses Ordners.
   - Leg damit eine geplante Aufgabe an, zum Beispiel täglich um 7 Uhr. Sie läuft nur, wenn die Claude-App geöffnet ist.
   - Frag vorher, ob der Nutzer das will und zu welcher Uhrzeit.

## Später

- **Neue Belege:** Aktualisiere Belege und eigene Rechnungen in drei Schritten.
  1. Führe `belege_auswertung.py` aus und ergänze, was es nicht erkannt hat.
  2. Lade `belege.csv` und `ausgang.csv` neu hoch.
  3. Stelle `datasets/belege` und `datasets/ausgang` per `update` mit `if_version` auf die neuen Adressen um und lösch danach die alten Assets.
- **Einstellungen geändert**, zum Beispiel neues Steuerjahr oder Beginn der Regelbesteuerung: `dashboard_vorbereiten.py` ausführen und `files/index.html` mit `seite.json` und `if_version` neu schreiben.
- **Token abgelaufen** (HTTP 401): Der Nutzer erzeugt einen neuen Token und trägt ihn selbst in die `.env` ein.
- **Einzelauswertung der Shows als Excel-CSV:** `python -X utf8 shows_umsatz.py --tage 30`.

## Was die Steuerberechnung annimmt

- **Umsatzsteuer:**
  - Whatnot-Verkäufe: 19/119 aus dem Verkaufspreis nach Gutschein, nach Bestelldatum (Soll-Versteuerung), ohne Differenzbesteuerung.
  - Eigene Rechnungen: die ausgewiesene USt.
- **Vorsteuer:** nur Belege ab Beginn der Regelbesteuerung mit Status `abziehbar`. `prüfen`-Beträge stehen getrennt.
- **Whatnot-Gebühren:** vermutlich Reverse Charge. USt und Vorsteuer heben sich auf, die Gebühren zählen nur als Kosten.
- **Gewinn** (Einnahmen-Überschuss-Rechnung, Lager nicht bewertet):
  - Einnahmen: Verkäufe (als Kleinunternehmer brutto, mit Regelbesteuerung netto) plus Trinkgeld.
  - Abzüge: Whatnot-Gebühren, selbst getragener Versand und Belegkosten (mit Vorsteuerabzug netto, sonst brutto).
