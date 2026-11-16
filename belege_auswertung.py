"""Wertet alle Eingangsbelege in belege/ aus und schreibt export/dashboard/belege.csv.

Aufruf:  python belege_auswertung.py

Eingangsbelege (Einkauf, Kosten) liegen in belege/ (auch Unterordner),
eigene Rechnungen außerhalb von Whatnot in rechnungen_ausgehend/.

- Rechnungen von TCG Index GmbH und Finom sowie mit Finom erstellte eigene Rechnungen
  werden automatisch aus dem PDF-Text gelesen
  (braucht pdftotext, z. B. aus Git for Windows: /mingw64/bin/pdftotext).
- Alle anderen Belege stehen in belege_manuell.csv, andere eigene Rechnungen in
  ausgang_manuell.csv (eine Zeile pro Datei; Claude kann sie aus den PDFs ausfüllen).
- Das Skript meldet Dateien, die in keiner der beiden Quellen vorkommen.

Regeln (Schätzung, keine Steuerberatung):
- Umsatzsteuerpflicht ab UST_START. Vorsteuer aus Belegen davor ist nicht abziehbar.
- vorsteuer          = USt-Betrag bei Status "abziehbar" ab UST_START
- vorsteuer_pruefen  = USt-Betrag bei Status "prüfen" ab UST_START (unsicher)
- kosten (Gewinn)    = netto ab UST_START bei abziehbar/prüfen, sonst brutto
"""
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

from einstellungen import lade

ROOT = Path(__file__).parent
BELEGE = ROOT / "belege"
MANUELL = ROOT / "belege_manuell.csv"
OUT = ROOT / "export" / "dashboard" / "belege.csv"
UST_START = lade()["ust_start"]  # Beginn der Regelbesteuerung aus einstellungen.ini

PDFTOTEXT = shutil.which("pdftotext") or r"C:\Program Files\Git\mingw64\bin\pdftotext.exe"


def de(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def iso(d: str) -> str:
    dd, mm, yy = d.split(".")
    return f"{yy}-{mm}-{dd}"


def pdf_text(p: Path) -> str:
    r = subprocess.run([PDFTOTEXT, "-enc", "UTF-8", "-layout", str(p), "-"], capture_output=True)
    return r.stdout.decode("utf-8", "replace")


def parse_tcg(t: str):
    T = re.sub(r"[ \t]+", " ", t)
    m = re.search(r"(RE\d{4}-\d+) \d+ (\d\d\.\d\d\.\d{4})", T)
    if not m:
        return None
    no, datum = m.group(1), iso(m.group(2))
    vs = re.findall(r"Im Gesamtbetrag von ([\d.,]+) ?€? \(Netto: ([\d.,]+) ?€?\) sind USt (\d+) ?% \(([\d.,]+) ?€?\)", T)
    if vs:
        brutto = sum(de(v[0]) for v in vs)
        netto = sum(de(v[1]) for v in vs)
        ust = sum(de(v[3]) for v in vs)
    else:  # neueres Layout: Zwischensumme (netto) / Umsatzsteuer / Gesamtbetrag
        n = re.search(r"([\d.,]+)\s*\n\s*Zwischensumme \(netto\)", T)
        u = re.search(r"Umsatzsteuer 19 % ([\d.,]+)", T)
        g = re.search(r"Gesamtbetrag ([\d.,]+)", T)
        if not (n and u and g):
            return None
        netto, ust, brutto = de(n.group(1)), de(u.group(1)), de(g.group(1))
    diff = "25a" in T
    return dict(datum=datum, lieferant="TCG Index GmbH", nummer=no, kategorie="Wareneinkauf",
                netto=netto, ust=ust, brutto=brutto,
                status="keine USt" if diff or ust == 0 else "abziehbar",
                hinweis="Differenzbesteuerung (§ 25a UStG)" if diff else "")


def parse_finom(t: str):
    T = re.sub(r"[ \t]+", " ", t)
    no = re.search(r"Rechnung Nr\. (\S+)", T)
    d = re.search(r"Rechnungsdatum: (\S+)", T)
    g = re.search(r"Gesamt ([\d.,]+) ?€? ([\d.,]+) ?€? ([\d.,]+)", T)
    if not (no and d and g):
        return None
    what = "Buchhaltungs-Add-on" if "Accounting" in T else "Basic-Tarif"
    return dict(datum=iso(d.group(1)), lieferant="Finom (PNL Fintech B.V., NL)", nummer=no.group(1),
                kategorie="Software & Gebühren", netto=de(g.group(1)), ust=de(g.group(2)), brutto=de(g.group(3)),
                status="prüfen" if de(g.group(2)) else "keine USt",
                hinweis=f"{what}; niederländischer Anbieter berechnet 19 % USt – Steuerberater fragen")


AUSGANG = ROOT / "rechnungen_ausgehend"
AUSGANG_MANUELL = ROOT / "ausgang_manuell.csv"
OUT_AUSGANG = ROOT / "export" / "dashboard" / "ausgang.csv"
LEGAL = re.compile(r"Kleinunternehmer|UStG|Steuerfrei|Differenzbesteuert|Ausfuhrlieferung|Leistung|Nettobetrag|Rabatt$")


def parse_ausgang(t: str, rel: str):
    """Eigene Rechnungen (Finom-Rechnungsprogramm). Kundennamen und Adressen werden nicht übernommen."""
    no = re.search(r"Rechnung Nr\. (\d+)", t)
    d = re.search(r"Rechnungsdatum:\s+(\d\d\.\d\d\.\d{4})", t)
    n = re.search(r"Nettobetrag\s+([\d.,]+) €", t)
    u = re.search(r"USt\. \((\d+)%\)\s+([\d.,]+) €", t)
    if not (no and d and n and u):
        return None
    after = t[u.end():]
    g = re.search(r"([\d.,]+) €", after)
    netto, satz, ust = de(n.group(1)), int(u.group(1)), de(u.group(2))
    brutto = de(g.group(1)) if g else netto + ust
    block = t[t.find("Leistung"):n.start()]
    items = []
    for line in block.splitlines():
        line = re.sub(r"\s+\d+\s+Stück.*$", "", line).strip()
        if line and not LEGAL.search(line) and not re.fullmatch(r"[\d.,\s€%]+", line):
            items.append(re.sub(r"\s{2,}", " ", line))
    datum = iso(d.group(1))
    hinweis, status = "", "ok"
    if "Ausfuhrlieferung" in t and "Differenzbesteuert" in t:
        status, hinweis = "prüfen", "Rechnung nennt steuerfreie Ausfuhr UND Differenzbesteuerung ohne USt – bei Inlandskunde ggf. 19 % geschuldet"
    elif datum >= UST_START and ust == 0:
        status, hinweis = "prüfen", "nach Beginn der USt-Pflicht ohne USt ausgestellt"
    elif datum < UST_START and satz == 0:
        hinweis = "Kleinunternehmer (§ 19 UStG)"
    return dict(datum=datum, nummer=no.group(1), artikel="; ".join(items)[:200], netto=netto, ust_satz=satz,
                ust=ust, brutto=round(brutto, 2), status=status, hinweis=hinweis, datei=rel)


def ausgang() -> None:
    AUSGANG.mkdir(exist_ok=True)
    rows, bad = [], []
    manual = {}
    if not AUSGANG_MANUELL.exists():
        AUSGANG_MANUELL.write_text("datei;datum;nummer;artikel;netto;ust_satz;ust;brutto;status;hinweis\n", encoding="utf-8")
    if AUSGANG_MANUELL.exists():
        with AUSGANG_MANUELL.open(encoding="utf-8") as f:
            for m in csv.DictReader(f, delimiter=";"):
                manual[m["datei"].replace("\\", "/")] = m
    for p in sorted(x for x in AUSGANG.rglob("*") if x.is_file() and not x.name.startswith("LIESMICH")):
        rel = p.relative_to(AUSGANG).as_posix()
        if rel in manual:
            m = manual[rel]
            r = dict(datum=m["datum"], nummer=m["nummer"], artikel=m["artikel"], netto=float(m["netto"]),
                     ust_satz=int(float(m["ust_satz"] or 0)), ust=float(m["ust"]), brutto=float(m["brutto"]),
                     status=m["status"] or "ok", hinweis=m["hinweis"], datei=rel)
        else:
            r = parse_ausgang(pdf_text(p), rel) if p.suffix.lower() == ".pdf" else None
        (rows.append(r) if r else bad.append(rel))
    rows.sort(key=lambda r: (r["datum"], r["nummer"]))
    nums = sorted(int(r["nummer"]) for r in rows if str(r["nummer"]).isdigit())
    gaps = [str(i) for i in range(nums[0], nums[-1]) if i not in nums] if nums else []
    cols = ["datum", "nummer", "artikel", "netto", "ust_satz", "ust", "brutto", "status", "hinweis", "datei"]
    with OUT_AUSGANG.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
    print(f"Ausgangsrechnungen: {len(rows)} -> {OUT_AUSGANG}; netto {sum(r['netto'] for r in rows):.2f}, "
          f"USt {sum(r['ust'] for r in rows):.2f}")
    if gaps:
        print("Fehlende Rechnungsnummern:", ", ".join(gaps))
    for b in bad:
        print("NICHT ERKANNT (bitte in ausgang_manuell.csv eintragen):", b)


def main() -> None:
    BELEGE.mkdir(exist_ok=True)
    files = sorted(p for p in BELEGE.rglob("*") if p.is_file() and not p.name.startswith("LIESMICH"))
    manual = {}
    if not MANUELL.exists():
        MANUELL.write_text("datei;datum;lieferant;nummer;kategorie;netto;ust;brutto;status;hinweis\n", encoding="utf-8")
    with MANUELL.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            manual[r["datei"].replace("\\", "/")] = r

    rows, missing, dup_nos = [], [], set()
    for p in files:
        rel = p.relative_to(BELEGE).as_posix()
        rec = None
        if rel in manual:
            m = manual[rel]
            rec = dict(datum=m["datum"], lieferant=m["lieferant"], nummer=m["nummer"], kategorie=m["kategorie"],
                       netto=float(m["netto"]), ust=float(m["ust"]), brutto=float(m["brutto"]),
                       status=m["status"], hinweis=m["hinweis"])
        elif p.suffix.lower() == ".pdf":
            t = pdf_text(p)
            if "DE455347852" in t:
                rec = parse_tcg(t)
            elif "NL859799189B01" in t:
                rec = parse_finom(t)
        if rec is None:
            missing.append(rel)
            continue
        key = (rec["lieferant"], rec["nummer"])
        if rec["status"] != "Duplikat" and key in dup_nos and rec["brutto"]:
            rec.update(status="Duplikat", hinweis="Rechnungsnummer kommt doppelt vor", netto=0, ust=0, brutto=0)
        dup_nos.add(key)
        if rec["brutto"] == 0 and rec["status"] not in ("Duplikat",):
            rec["status"] = "keine USt"
        ab = rec["datum"] >= UST_START
        rec["ab_ust_pflicht"] = "ja" if ab else "nein"
        rec["vorsteuer"] = round(rec["ust"], 2) if ab and rec["status"] == "abziehbar" else 0
        rec["vorsteuer_pruefen"] = round(rec["ust"], 2) if ab and rec["status"] == "prüfen" else 0
        if rec["status"] == "Duplikat":
            rec["kosten"] = 0
        elif ab and rec["status"] in ("abziehbar", "prüfen"):
            rec["kosten"] = round(rec["netto"], 2)
        else:
            rec["kosten"] = round(rec["brutto"], 2)
        rec["datei"] = rel
        rows.append(rec)

    rows.sort(key=lambda r: (r["datum"], r["lieferant"]))
    cols = ["datum", "lieferant", "nummer", "kategorie", "netto", "ust", "brutto", "status", "hinweis",
            "ab_ust_pflicht", "vorsteuer", "vorsteuer_pruefen", "kosten", "datei"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([round(r[c], 2) if isinstance(r[c], float) else r[c] for c in cols])

    print(f"{len(files)} Dateien, {len(rows)} ausgewertet -> {OUT}")
    if missing:
        print("NICHT ERKANNT (bitte in belege_manuell.csv eintragen):")
        for m in missing:
            print("  ", m)
    unused = set(manual) - {p.relative_to(BELEGE).as_posix() for p in files}
    if unused:
        print("In belege_manuell.csv, aber Datei fehlt:", *sorted(unused), sep="\n   ")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
    ausgang()
