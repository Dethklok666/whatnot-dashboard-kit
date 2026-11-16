"""Shows & Umsatz: holt alle beendeten Shows samt Kennzahlen und exportiert sie als CSV.

Aufruf:
    python shows_umsatz.py                 # alle beendeten Shows
    python shows_umsatz.py --seit 2026-10-01
    python shows_umsatz.py --tage 30

Ergebnis: Zusammenfassung in der Konsole + export/shows_umsatz_<datum>.csv (fuer Excel).
Nur lesende Zugriffe (read:shows, read:reports).
"""
import argparse
import csv
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from whatnot_client import ApiError, WhatnotClient

EXPORT_DIR = Path(__file__).with_name("export")

# (Spaltenname im CSV, Feld in der API-Antwort, Typ)
COLUMNS = [
    ("Datum", "start_time", "datum"),
    ("Show", "title", "text"),
    ("Umsatz", "sales", "geld"),
    ("Geschätzter Erlös", "estimated_earnings", "geld"),
    ("Bestellungen", "orders_count", "zahl"),
    ("Ø Bestellwert", "average_order_value", "geld"),
    ("Käufer", "buyers_count", "zahl"),
    ("Neukäufer", "first_time_buyers_count", "zahl"),
    ("Stammkäufer", "returning_buyers_count", "zahl"),
    ("Giveaways", "giveaway_orders_count", "zahl"),
    ("Giveaway-Kosten", "giveaway_spend", "geld"),
    ("Stream-Minuten", "stream_minutes", "zahl"),
    ("Max. Zuschauer gleichzeitig", "max_concurrent_viewers", "zahl"),
    ("Aufrufe gesamt", "total_views", "zahl"),
    ("Einzelne Zuschauer", "distinct_viewers_count", "zahl"),
    ("Impressionen", "show_impression_count", "zahl"),
    ("Klickrate %", "show_clickthrough_rate", "dezimal"),
    ("Geteilt", "buyer_shares_count", "zahl"),
    ("Bewertung", "average_rating", "dezimal"),
    ("Status Kennzahlen", "calculation_status", "text"),
    ("Show-ID", "show_id", "text"),
]


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def money(value) -> Decimal | None:
    return Decimal(value["amount"]) if value else None


def de_num(value) -> str:
    """Zahl im deutschen Format fuer Excel (Komma als Dezimaltrenner)."""
    return "" if value is None else str(value).replace(".", ",")


def fmt_eur(value: Decimal) -> str:
    s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def fetch_ended_shows(client: WhatnotClient, since: datetime | None) -> list[dict]:
    shows, cursor = [], None
    while True:
        page = client.get("/shows", status="ended", limit=50, cursor=cursor)
        stop = False
        for show in page["data"]:
            start = parse_ts(show["scheduled_start_at"])
            if since and start < since:
                stop = True  # neueste zuerst -> aeltere brauchen wir nicht mehr
                break
            shows.append(show)
        cursor = page.get("next_cursor")
        if stop or not cursor or not page["data"]:
            return shows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seit", help="nur Shows ab diesem Datum (JJJJ-MM-TT)")
    ap.add_argument("--tage", type=int, help="nur Shows der letzten N Tage")
    ap.add_argument("--mit-privaten", action="store_true", help="private Test-Shows nicht ausblenden")
    args = ap.parse_args()

    since = None
    if args.seit:
        since = datetime.fromisoformat(args.seit).replace(tzinfo=timezone.utc)
    elif args.tage:
        since = datetime.now(timezone.utc) - timedelta(days=args.tage)

    client = WhatnotClient()
    print("Lade Shows ...")
    shows = fetch_ended_shows(client, since)
    if not args.mit_privaten:
        shows = [s for s in shows if s["visibility"] != "private"]
    print(f"{len(shows)} beendete Shows gefunden. Lade Kennzahlen ...")

    rows = []
    for i, show in enumerate(shows, 1):
        try:
            rows.append(client.get(f"/analytics/shows/{show['id']}"))
        except ApiError as e:
            print(f"  Warnung: Kennzahlen fuer '{show['title']}' nicht abrufbar ({e.status}).")
        if i % 25 == 0:
            print(f"  {i}/{len(shows)}")
        time.sleep(0.12)  # unter 10 Anfragen/Sekunde bleiben

    # --- CSV-Export ---
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"shows_umsatz_{date.today().isoformat()}.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([c[0] for c in COLUMNS])
        for r in rows:
            line = []
            for _, field, kind in COLUMNS:
                v = r.get(field)
                if kind == "datum":
                    line.append(parse_ts(v).astimezone().strftime("%d.%m.%Y %H:%M") if v else "")
                elif kind == "geld":
                    line.append(de_num(money(v)))
                elif kind in ("zahl", "dezimal"):
                    line.append(de_num(v))
                else:
                    line.append(v or "")
            w.writerow(line)

    # --- Zusammenfassung ---
    done = [r for r in rows if r.get("calculation_status") == "GENERATED"]
    pending = len(rows) - len(done)
    total_sales = sum((money(r["sales"]) or 0 for r in done), Decimal(0))
    total_earn = sum((money(r["estimated_earnings"]) or 0 for r in done), Decimal(0))
    total_orders = sum(r["orders_count"] or 0 for r in done)
    total_minutes = sum(r["stream_minutes"] or 0 for r in done)

    print("\n=== Gesamt ===")
    print(f"Shows mit Kennzahlen: {len(done)}" + (f"  (noch ohne Kennzahlen: {pending})" if pending else ""))
    print(f"Umsatz:               {fmt_eur(total_sales)}")
    print(f"Geschätzter Erlös:    {fmt_eur(total_earn)}")
    print(f"Bestellungen:         {total_orders}")
    if total_orders:
        print(f"Ø Bestellwert:        {fmt_eur(total_sales / total_orders)}")
    if total_minutes:
        print(f"Stream-Stunden:       {total_minutes / 60:.1f}  ->  {fmt_eur(total_sales / total_minutes * 60)} Umsatz/Stunde")

    by_month = defaultdict(lambda: [0, Decimal(0), Decimal(0), 0])
    for r in done:
        m = by_month[parse_ts(r["start_time"]).astimezone().strftime("%Y-%m")]
        m[0] += 1
        m[1] += money(r["sales"]) or 0
        m[2] += money(r["estimated_earnings"]) or 0
        m[3] += r["orders_count"] or 0
    print("\n=== Pro Monat ===")
    print(f"{'Monat':<8} {'Shows':>5} {'Umsatz':>14} {'Erlös':>14} {'Bestell.':>8}")
    for month in sorted(by_month):
        n, s, e, o = by_month[month]
        print(f"{month:<8} {n:>5} {fmt_eur(s):>14} {fmt_eur(e):>14} {o:>8}")

    print("\n=== Top 5 Shows nach Umsatz ===")
    for r in sorted(done, key=lambda r: money(r["sales"]) or 0, reverse=True)[:5]:
        d = parse_ts(r["start_time"]).astimezone().strftime("%d.%m.%Y")
        print(f"{d}  {fmt_eur(money(r['sales']) or Decimal(0)):>12}  {r['orders_count'] or 0:>4} Best.  {r['title']}")

    print(f"\nCSV gespeichert: {out}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
