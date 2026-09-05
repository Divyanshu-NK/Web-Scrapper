#!/usr/bin/env python3
"""
scraper.py — Aarsi (aarsi.shop) catalog tracker

Aarsi runs on Shopify. Instead of scraping HTML (slow, brittle, breaks the
moment a theme changes), this pulls Shopify's *public* JSON product feed —
the same data the storefront renders from. No login, no API key, no
headless browser needed.

Endpoint used:
    https://aarsi.shop/collections/<handle>/products.json?limit=250&page=N

Each run saves a timestamped snapshot into a local SQLite database
(aarsi_tracker.db). Run this on a schedule (weekly via cron is the
intended cadence — see README.md) and analyze.py will diff snapshots
against each other to surface new launches, stock/price changes, and
style trends.

Usage:
    python scraper.py                          # scrape "all-products", default sort
    python scraper.py --sort best-selling       # also capture best-seller rank
    python scraper.py --collection new-arrival   # target a specific collection handle
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

BASE_URL = "https://aarsi.shop"
DB_PATH = Path(__file__).parent / "aarsi_tracker.db"

# Identify yourself honestly and don't hammer their server. Swap in a real
# contact if you're going to run this on a recurring schedule — it's the
# polite/standard convention for automated traffic and costs you nothing.
USER_AGENT = "aarsi-market-research-bot/1.0 (personal research; contact: you@example.com)"
REQUEST_DELAY_SECONDS = 1.5
PAGE_SIZE = 250  # Shopify's hard cap per request


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


def fetch_collection_products(
    session: requests.Session,
    collection_handle: str = "all-products",
    sort_by: Optional[str] = None,
) -> list[dict]:
    """
    Pull every product from a Shopify collection via its public JSON feed,
    paginating until an empty page is returned.

    sort_by, if given, is passed straight through to Shopify (e.g.
    'best-selling', 'created-descending', 'price-ascending'). This mirrors
    the sort dropdown on the actual collection page. Position in the
    returned list = rank under that sort.
    """
    products: list[dict] = []
    page = 1
    while True:
        url = f"{BASE_URL}/collections/{collection_handle}/products.json"
        params = {"limit": PAGE_SIZE, "page": page}
        if sort_by:
            params["sort_by"] = sort_by

        resp = session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        batch = resp.json().get("products", [])
        if not batch:
            break

        products.extend(batch)
        print(f"  page {page}: {len(batch)} products", file=sys.stderr)
        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return products


def normalize_product(raw: dict, rank: Optional[int] = None) -> dict:
    """Flatten a Shopify product JSON object into the row shape we store."""
    variants = raw.get("variants", [])
    prices = [float(v["price"]) for v in variants if v.get("price") is not None]
    compare_prices = [
        float(v["compare_at_price"])
        for v in variants
        if v.get("compare_at_price")
    ]
    any_available = any(v.get("available") for v in variants)
    sizes = sorted({v.get("title") for v in variants if v.get("title")})

    return {
        "product_id": raw["id"],
        "handle": raw.get("handle"),
        "title": raw.get("title"),
        "vendor": raw.get("vendor"),
        "product_type": raw.get("product_type"),
        "tags": ", ".join(raw.get("tags", [])) if isinstance(raw.get("tags"), list) else raw.get("tags", ""),
        "created_at": raw.get("created_at"),
        "published_at": raw.get("published_at"),
        "updated_at": raw.get("updated_at"),
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "compare_at_price_max": max(compare_prices) if compare_prices else None,
        "available": any_available,
        "num_variants": len(variants),
        "sizes": ", ".join(sizes),
        "num_images": len(raw.get("images", [])),
        "rank": rank,  # position under whatever sort_by was requested this run
    }


SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at      TEXT NOT NULL,
    collection      TEXT NOT NULL,
    sort_by         TEXT
);

CREATE TABLE IF NOT EXISTS product_snapshots (
    snapshot_id           INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    product_id            INTEGER NOT NULL,
    handle                TEXT,
    title                 TEXT,
    vendor                TEXT,
    product_type          TEXT,
    tags                  TEXT,
    created_at            TEXT,
    published_at          TEXT,
    updated_at            TEXT,
    price_min             REAL,
    price_max             REAL,
    compare_at_price_max  REAL,
    available             INTEGER,
    num_variants          INTEGER,
    sizes                 TEXT,
    num_images            INTEGER,
    rank                  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_ps_snapshot ON product_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_ps_product ON product_snapshots(product_id);
"""


def save_snapshot(products: list[dict], collection: str, sort_by: Optional[str]) -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    scraped_at = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO snapshots (scraped_at, collection, sort_by) VALUES (?, ?, ?)",
        (scraped_at, collection, sort_by),
    )
    snapshot_id = cur.lastrowid

    rows = []
    for i, raw in enumerate(products, start=1):
        row = normalize_product(raw, rank=i if sort_by else None)
        rows.append((
            snapshot_id, row["product_id"], row["handle"], row["title"], row["vendor"],
            row["product_type"], row["tags"], row["created_at"], row["published_at"],
            row["updated_at"], row["price_min"], row["price_max"], row["compare_at_price_max"],
            int(row["available"]), row["num_variants"], row["sizes"], row["num_images"], row["rank"],
        ))

    conn.executemany(
        """INSERT INTO product_snapshots (
            snapshot_id, product_id, handle, title, vendor, product_type, tags,
            created_at, published_at, updated_at, price_min, price_max,
            compare_at_price_max, available, num_variants, sizes, num_images, rank
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    conn.close()
    return snapshot_id


def main():
    parser = argparse.ArgumentParser(description="Scrape aarsi.shop's public product feed into a local DB.")
    parser.add_argument("--collection", default="all-products", help="Shopify collection handle to scrape")
    parser.add_argument(
        "--sort",
        default=None,
        help="Shopify sort_by value to capture ranking under, e.g. best-selling, created-descending",
    )
    parser.add_argument("--also-new-arrivals", action="store_true",
                         help="Also scrape the 'new-arrival' collection in the same run")
    args = parser.parse_args()

    session = get_session()

    print(f"Fetching collection '{args.collection}' (sort_by={args.sort or 'default'})...", file=sys.stderr)
    products = fetch_collection_products(session, args.collection, args.sort)
    snap_id = save_snapshot(products, args.collection, args.sort)
    print(f"Saved snapshot #{snap_id}: {len(products)} products from '{args.collection}'.", file=sys.stderr)

    if args.also_new_arrivals and args.collection != "new-arrival":
        print("Fetching 'new-arrival' collection...", file=sys.stderr)
        na_products = fetch_collection_products(session, "new-arrival", None)
        na_snap_id = save_snapshot(na_products, "new-arrival", None)
        print(f"Saved snapshot #{na_snap_id}: {len(na_products)} products from 'new-arrival'.", file=sys.stderr)

    print(f"\nDone. Data stored in {DB_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
