Aktualisiere das Dashboard "{{SHOP_NAME}} Cockpit" mit frischen Daten aus der Whatnot Seller API. Antworte am Ende auf Deutsch.

Dashboard (Claude-Artefakt vom Typ Dashboard): {{DASHBOARD_URL}}
Projektordner: {{ORDNER}}

Wichtig: Öffne oder lies NIEMALS die Datei {{ORDNER}}\.env und gib den API-Token nirgends aus. Das Skript liest ihn selbst.

Schritte:

1. Daten abrufen: Führe im Projektordner `python dashboard_daten.py` aus. Das Skript greift fast nur lesend zu und erzeugt nur Whatnot-Berichte. Es kann einige Minuten dauern, nimm einen Timeout von 10 Minuten. Es schreibt acht CSV-Dateien nach {{ORDNER}}\export\dashboard\.
   - Bricht es mit HTTP 401 ab, ist der Token abgelaufen. Lade dann nichts hoch und ändere nichts am Dashboard. Melde, dass unter https://www.whatnot.com/dashboard/developer?tab=tokens ein neuer Token erzeugt und in die .env eingetragen werden muss.
   - Bei anderen Fehlern ebenfalls abbrechen und den Fehler melden.

2. Dateien hochladen: Lade jede der acht Dateien einzeln (eine Datei pro Aufruf) mit dem Artifact-Tool in den Asset-Speicher des Dashboards: action "publish", url = Dashboard-URL, asset: true, file_path = die Datei. Merke dir die neue Adresse "/_blob/<id>" jeder Datei. Datenquelle -> Datei in {{ORDNER}}\export\dashboard\:
   shows -> shows.csv, upcoming -> upcoming.csv, orders -> orders.csv, order_items -> order_items.csv, shipments -> shipments.csv, products -> products.csv, daily -> daily.csv, finance -> finance.csv

3. Datenquellen umstellen:
   - Lies mit dem ArtifactData-Tool (action "list", collection "datasets", url = Dashboard-URL) die acht Dokumente. Notiere von jedem die "version" und die alte Adresse in source.url.
   - Schreibe dann EINEN ArtifactData-Aufruf mit action "batch". Er bekommt je Datenquelle einen Eintrag {op: "update", collection: "datasets", doc_id: <id>, if_version: <gelesene version>, data: {source: {url: "<neue /_blob/-Adresse>"}, updated: {at: <jetzt, UTC ISO>, by: "Geplante Aufgabe (Whatnot Seller API)"}, edit: {via: "claude", at: <jetzt, UTC ISO>}}}.
   - Ändere sonst nichts an den Dokumenten. Ändere niemals files/index.html und keine anderen Dokumente, auch nicht die Datenquellen belege und ausgang.

4. Aufräumen: Erst wenn der Batch erfolgreich war, lösche die acht alten, jetzt ersetzten Dateien aus dem Asset-Speicher (Artifact-Tool, action "delete", url = Dashboard-URL, path = die 32-stellige id aus der alten Adresse nach "/_blob/"). Lösche nichts anderes. Ist der Batch fehlgeschlagen, lösche nichts.

5. Ergebnis melden, in 2–3 Sätzen: der neueste Bestellzeitpunkt im Datenstand, die Anzahl Zeilen je Datei (aus der Skriptausgabe) und ob alles geklappt hat.
