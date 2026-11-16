"""Erzeugt die Dashboard-Seite aus der Vorlage und den Einstellungen.

Aufruf:  python dashboard_vorbereiten.py

Ergebnis:
- export/dashboard/index.html   fertige Seite (zum Ansehen)
- export/dashboard/seite.json   Dokument für files/index.html im Dashboard-Artefakt ({"text": ..., "edit": ...})
- export/dashboard/datenquellen.json   Titel und Beschreibung der Datenquellen (ohne Dateiadresse)

Nach jeder Änderung an einstellungen.ini neu ausführen und seite.json erneut ins Dashboard schreiben.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from einstellungen import lade

ROOT = Path(__file__).parent
VORLAGE = ROOT / "dashboard" / "index.vorlage.html"
QUELLEN = ROOT / "dashboard" / "datasets.json"
OUT = ROOT / "export" / "dashboard"


def de_datum(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def main() -> None:
    e = lade()
    jahr = e["steuerjahr"]
    ab = e["regelbesteuert_ab"]
    if ab and ab[:4] < jahr:
        ab = f"{jahr}-01-01"  # schon vor dem Steuerjahr regelbesteuert
    if not ab or ab[:4] > jahr:
        werte = {
            "UST_MONAT": "9999-12",
            "UST_AB_KURZ": "(nicht fällig)",
            "UST_SATZ": f"Kleinunternehmer (§ 19 UStG) im ganzen Jahr {jahr}: keine Umsatzsteuer, kein Vorsteuerabzug.",
        }
    else:
        werte = {
            "UST_MONAT": ab[:7],
            "UST_AB_KURZ": f"ab {de_datum(ab)}",
            "UST_SATZ": (f"Regelbesteuerung ab {de_datum(ab)}" + (", davor Kleinunternehmer." if ab[5:] != "01-01" else ".")),
        }
    werte.update(SHOP_NAME=e["shop_name"] or "Mein Shop", STEUERJAHR=jahr)
    html = VORLAGE.read_text(encoding="utf-8")
    for k, v in werte.items():
        html = html.replace("{{" + k + "}}", v)
    if "{{" in html:
        sys.exit("Fehler: In der Vorlage sind noch Platzhalter übrig.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (OUT / "seite.json").write_text(json.dumps({"text": html, "edit": {"via": "claude", "at": now}}, ensure_ascii=False),
                                    encoding="utf-8")
    q = json.loads(QUELLEN.read_text(encoding="utf-8"))
    for v in q.values():
        v["title"] = v["title"].replace("{{STEUERJAHR}}", jahr)
    (OUT / "datenquellen.json").write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dashboard für „{werte['SHOP_NAME']}“, Steuerjahr {jahr}: {werte['UST_SATZ']}")
    print(f"-> {OUT / 'seite.json'} und {OUT / 'datenquellen.json'}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
