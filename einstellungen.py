"""Liest einstellungen.ini (Shopname, Datenbeginn, Steuerjahr, Beginn der Regelbesteuerung)."""
import configparser
import re
import sys
from pathlib import Path

DATEI = Path(__file__).with_name("einstellungen.ini")


def lade() -> dict:
    if not DATEI.exists():
        sys.exit("Fehler: einstellungen.ini fehlt. Bitte einstellungen.ini.beispiel kopieren und ausfüllen.")
    cp = configparser.ConfigParser()
    cp.read(DATEI, encoding="utf-8")
    e = {
        "shop_name": cp.get("shop", "name", fallback="").strip(),
        "daten_ab": cp.get("daten", "daten_ab", fallback="").strip(),
        "steuerjahr": cp.get("steuern", "steuerjahr", fallback="").strip(),
        "regelbesteuert_ab": cp.get("steuern", "regelbesteuert_ab", fallback="").strip(),
    }
    if not e["shop_name"] or e["shop_name"] == "Mein Shop":
        print("Hinweis: In einstellungen.ini ist noch kein Shopname eingetragen.")
    for k in ("daten_ab", "regelbesteuert_ab"):
        if e[k] and not re.fullmatch(r"\d{4}-\d\d-\d\d", e[k]):
            sys.exit(f"Fehler: {k} in einstellungen.ini muss das Format JJJJ-MM-TT haben (oder leer sein).")
    if not re.fullmatch(r"\d{4}", e["steuerjahr"]):
        sys.exit("Fehler: steuerjahr in einstellungen.ini muss eine Jahreszahl sein, z. B. 2026.")
    if not e["daten_ab"]:
        e["daten_ab"] = f"{int(e['steuerjahr']) - 1}-01-01"
    # Ohne Datum: ganzes Jahr Kleinunternehmer -> Datum, das nie erreicht wird
    e["ust_start"] = e["regelbesteuert_ab"] or "9999-12-31"
    return e
