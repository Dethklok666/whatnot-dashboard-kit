"""Sammelt ALLE verfuegbaren Daten fuer das Dashboard aus der Whatnot Seller API.

Aufruf:  python dashboard_daten.py
Ergebnis: export/dashboard/*.csv (Komma-getrennt, Punkt als Dezimaltrenner)

Zugriffe: lesend, ausser dass Whatnot-Reports erzeugt werden (POST /reports,
nur Berichtserstellung, aendert nichts am Shop).

Datenschutz: orders.csv enthaelt den Whatnot-Benutzernamen
und Anzeigenamen der Kaeufer (wie im Seller-Bereich sichtbar). Adressen und
Nachrichtentexte werden NICHT gespeichert. buyer_key bleibt der stabile Schluessel.

Zwischenspeicher: export/cache/ (Artikel je Bestellung, Verkaufsformat je
Produkt), damit taegliche Laeufe nur Neues abfragen.
"""
import csv
import hashlib
import io
import json
import secrets
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from einstellungen import lade
from whatnot_client import ApiError, WhatnotClient

ROOT = Path(__file__).with_name("export")
OUT = ROOT / "dashboard"
CACHE = ROOT / "cache"
START = lade()["daten_ab"] + "T00:00:00.000Z"  # aus einstellungen.ini
PAUSE = 0.11  # unter 10 Anfragen/Sekunde bleiben
MERCH_MAX_AGE = timedelta(days=7)


def log(msg: str) -> None:
    print(msg, flush=True)


def all_pages(c: WhatnotClient, path: str, **params) -> list[dict]:
    out, cursor = [], None
    while True:
        page = c.get(path, limit=50, cursor=cursor, **params)
        out += page["data"]
        cursor = page.get("next_cursor")
        if not cursor or not page["data"]:
            return out
        time.sleep(PAUSE)


def amt(m):
    """Betrag aus {"amount": "1.23", ...}; manche Felder sind eine Ebene tiefer verschachtelt."""
    while isinstance(m, dict):
        m = m.get("amount")
    return m if m is not None else ""


def write_csv(name: str, header: list[str], rows: list[list]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    log(f"  {name}: {len(rows)} Zeilen")


def load_json(name: str, default):
    p = CACHE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(name: str, data) -> None:
    (CACHE / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def buyer_keyer():
    salt_file = CACHE / "pseudonym_salt.txt"
    if not salt_file.exists():
        salt_file.write_text(secrets.token_hex(16), encoding="utf-8")
    salt = salt_file.read_text(encoding="utf-8").strip()
    return lambda buyer_id: hashlib.sha256(f"{salt}:{buyer_id}".encode()).hexdigest()[:12] if buyer_id else ""


def now_iso_ms() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def run_report(c: WhatnotClient, params: dict) -> list[dict]:
    """Erzeugt einen Whatnot-Report, wartet auf Fertigstellung und laedt die CSV."""
    run = c.post("/reports", {"report_parameters": params})
    for _ in range(60):
        if run["status"] == "completed":
            break
        if run["status"] in ("failed", "cancelled"):
            raise RuntimeError(f"Report {params['report_type']} ist {run['status']}")
        time.sleep(5)
        run = c.get(f"/reports/{run['id']}")
    else:
        raise RuntimeError(f"Report {params['report_type']} nicht rechtzeitig fertig")
    # Signierte Download-Adresse von Whatnot; bewusst OHNE API-Token abrufen.
    with urllib.request.urlopen(run["report_url"], timeout=120) as resp:
        text = resp.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    c = WhatnotClient()
    key = buyer_keyer()

    # ---------------- Shows ----------------
    log("Shows ...")
    ended = [s for s in all_pages(c, "/shows", status="ended") if s["visibility"] != "private"]
    rows = []
    for s in ended:
        try:
            a = c.get(f"/analytics/shows/{s['id']}")
        except ApiError as e:
            log(f"  Warnung: {s['title']} ({e.status})")
            continue
        rows.append([
            a["show_id"], a["start_time"], s.get("ended_at") or "", a["title"], a["calculation_status"],
            amt(a["sales"]), amt(a["estimated_earnings"]), a["orders_count"] or "",
            amt(a["average_order_value"]), a["buyers_count"] or "", a["first_time_buyers_count"] or "",
            a["returning_buyers_count"] or "", a["giveaway_orders_count"] or "", amt(a["giveaway_spend"]),
            a["giveaway_winners_count"] or "", a["stream_minutes"] or "", a["max_concurrent_viewers"] or "",
            a["total_views"] or "", a["distinct_viewers_count"] or "", a["show_impression_count"] or "",
            a["show_clickthrough_rate"] if a["show_clickthrough_rate"] is not None else "",
            a["buyer_shares_count"] or "", a["average_rating"] if a["average_rating"] is not None else "",
        ])
        time.sleep(PAUSE)
    write_csv("shows.csv", [
        "show_id", "start_time", "ended_at", "title", "calculation_status", "sales_eur", "earnings_eur",
        "orders", "avg_order_eur", "buyers", "new_buyers", "returning_buyers", "giveaways",
        "giveaway_spend_eur", "giveaway_winners", "stream_minutes", "peak_viewers", "total_views",
        "distinct_viewers", "impressions", "clickthrough_pct", "shares", "avg_rating",
    ], rows)

    upcoming = all_pages(c, "/shows", status="scheduled")
    write_csv("upcoming.csv", ["show_id", "scheduled_start_at", "title", "visibility", "url"],
              [[s["id"], s["scheduled_start_at"], s["title"], s["visibility"], s["url"]] for s in upcoming])

    # ---------------- Bestellungen ----------------
    log("Bestellungen ...")
    orders = all_pages(c, "/orders")
    write_csv("orders.csv", [
        "order_id", "created_at", "status", "show_id", "transaction_type", "buyer_key", "buyer_username",
        "buyer_name", "subtotal_eur",
        "shipping_eur", "tax_eur", "discount_eur", "total_eur", "cancelled_at",
    ], [[
        o["id"], o["created_at"], o["status"], o.get("show_id") or "", o.get("transaction_type") or "",
        key((o.get("buyer") or {}).get("id")),
        (o.get("buyer") or {}).get("username") or "", (o.get("buyer") or {}).get("display_name") or "",
        amt(o["amounts"]["subtotal"]), amt(o["amounts"]["shipping"]), amt(o["amounts"]["tax"]),
        amt(o["amounts"]["applied_discount"]), amt(o["amounts"]["total"]), o.get("cancelled_at") or "",
    ] for o in orders])

    # ---------------- Artikel je Bestellung (mit Zwischenspeicher) ----------------
    item_cache = load_json("order_items.json", {})
    todo = [o for o in orders if o["status"] != "failed"
            and item_cache.get(o["id"], {}).get("updated_at") != o["updated_at"]]
    log(f"Artikel je Bestellung: {len(todo)} von {len(orders)} Bestellungen abzufragen ...")
    for i, o in enumerate(todo, 1):
        try:
            items = all_pages(c, f"/orders/{o['id']}/items")
        except ApiError as e:
            log(f"  Warnung: Artikel zu Bestellung {o['id']} nicht abrufbar ({e.status})")
            continue
        item_cache[o["id"]] = {"updated_at": o["updated_at"], "items": [{
            "id": it["id"], "product_id": it.get("product_id") or "",
            "title": (it.get("purchased_item") or {}).get("title") or "",
            "quantity": it.get("quantity") or 0, "unit_price": amt(it.get("unit_price")),
            "shipment_id": it.get("shipment_id") or "",
        } for it in items]}
        if i % 500 == 0:
            save_json("order_items.json", item_cache)
            log(f"  {i}/{len(todo)}")
        time.sleep(PAUSE)
    save_json("order_items.json", item_cache)
    by_id = {o["id"]: o for o in orders}
    item_rows = []
    for oid, entry in item_cache.items():
        o = by_id.get(oid)
        if not o:
            continue
        for it in entry["items"]:
            item_rows.append([it["id"], oid, o["created_at"], o["status"], o.get("transaction_type") or "",
                              o.get("show_id") or "", it["product_id"], it["title"], it["quantity"],
                              it["unit_price"], it["shipment_id"]])
    write_csv("order_items.csv", [
        "item_id", "order_id", "created_at", "order_status", "transaction_type", "show_id", "product_id",
        "title", "quantity", "unit_price_eur", "shipment_id",
    ], item_rows)

    # ---------------- Sendungen ----------------
    log("Sendungen ...")
    ships = all_pages(c, "/shipments")
    write_csv("shipments.csv", [
        "shipment_id", "created_at", "status", "method", "carrier", "service", "weight_g", "length_cm",
        "width_cm", "height_cm", "dropoff_due", "has_tracking", "seller_paid_eur", "insured",
        "signature_required", "open_actions", "replacement_shipment_id", "url",
        "updated_at", "tracking_code", "buyer_key", "buyer_username", "buyer_name", "required_actions",
    ], [[
        s["id"], s["created_at"], s["status"], s.get("fulfillment_method") or "",
        (s.get("tracking") or {}).get("carrier") or "", (s.get("tracking") or {}).get("service") or "",
        (s.get("weight") or {}).get("value") or "",
        (s.get("dimensions") or {}).get("length") or "", (s.get("dimensions") or {}).get("width") or "",
        (s.get("dimensions") or {}).get("height") or "", s.get("dropoff_due") or "",
        "yes" if (s.get("tracking") or {}).get("tracking_code") else "no",
        amt(s.get("seller_paid_shipping_cost")), "yes" if s.get("insurance") else "no",
        "yes" if s.get("signature_required") else "no", len(s.get("required_actions") or []),
        s.get("replacement_shipment_id") or "", s["url"],
        s.get("updated_at") or "", (s.get("tracking") or {}).get("tracking_code") or "",
        key((s.get("recipient") or {}).get("id")), (s.get("recipient") or {}).get("username") or "",
        (s.get("recipient") or {}).get("display_name") or "",
        " | ".join(str(a.get("type") or a.get("name") or a) if isinstance(a, dict) else str(a)
                   for a in (s.get("required_actions") or [])),
    ] for s in ships])

    # ---------------- Produkte + Verkaufsformat (mit Zwischenspeicher) ----------------
    log("Produkte ...")
    prods = all_pages(c, "/products")
    merch_cache = load_json("merchandising.json", {})
    cutoff = (datetime.now(timezone.utc) - MERCH_MAX_AGE).isoformat()
    todo = [p for p in prods if merch_cache.get(p["id"], {}).get("fetched_at", "") < cutoff
            or merch_cache[p["id"]].get("product_updated_at") != p["updated_at"]]
    log(f"Verkaufsformat: {len(todo)} von {len(prods)} Produkten abzufragen ...")
    for i, p in enumerate(todo, 1):
        try:
            m = c.get(f"/merchandising/products/{p['id']}")
        except ApiError as e:
            log(f"  Warnung: Verkaufsformat zu Produkt {p['id']} nicht abrufbar ({e.status})")
            continue
        merch_cache[p["id"]] = {"fetched_at": datetime.now(timezone.utc).isoformat(),
                                "product_updated_at": p["updated_at"], **m}
        if i % 500 == 0:
            save_json("merchandising.json", merch_cache)
            log(f"  {i}/{len(todo)}")
        time.sleep(PAUSE)
    save_json("merchandising.json", merch_cache)
    write_csv("products.csv", [
        "product_id", "created_at", "updated_at", "category", "dimension_profile", "title",
        "sale_format", "reserved_for_live", "active_in_shows",
    ], [[
        p["id"], p["created_at"], p["updated_at"], (p.get("category") or {}).get("name") or "ohne Kategorie",
        (p.get("dimension_profile") or {}).get("name") or "", p["title"],
        merch_cache.get(p["id"], {}).get("transaction_type") or "ohne",
        "yes" if merch_cache.get(p["id"], {}).get("reserved_for_live") else "no",
        "yes" if merch_cache.get(p["id"], {}).get("active_in_shows") else "no",
    ] for p in prods])

    # ---------------- Reports ----------------
    end = now_iso_ms()
    log("Report: Tageswerte ...")
    daily = run_report(c, {"report_type": "analytics_overview_report", "start_at": START, "end_at": end})
    cols = ["date", "estimated_sales", "in_show_estimated_sales", "marketplace_estimated_sales",
            "estimated_earnings", "orders_count", "in_show_orders_count", "marketplace_orders_count",
            "giveaway_orders_count", "average_order_value", "buyers_count", "new_buyers_count",
            "returning_buyers_count", "follows_count", "referral_follows_count", "non_referral_follows_count",
            "livestreams_count", "stream_minutes", "viewers_per_hour", "average_watch_time_seconds"]
    write_csv("daily.csv", cols, [[r.get(k, "") for k in cols] for r in daily])

    log("Report: Finanzbericht ...")
    fin = run_report(c, {"report_type": "seller_financial_report", "start_date": START, "end_date": end})
    cols = ["transaction_completed_at_utc", "order_placed_at_utc", "transaction_type", "order_id",
            "listing_title", "product_category", "buy_format", "sale_type", "quantity_sold", "livestream_id",
            "buyer_state", "buyer_country", "transaction_amount", "buyer_paid", "original_item_price",
            "coupon_cost", "post_coupon_price", "seller_shipping_charge", "commission_fee", "commission_tax",
            "processing_fee", "processing_fee_tax", "ledger_transaction_id"]  # ohne buyer_name / Nachricht
    write_csv("finance.csv", cols, [[r.get(k, "") for k in cols] for r in fin])

    log(f"Fertig. Dateien in {OUT}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
