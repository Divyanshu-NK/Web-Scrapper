#!/usr/bin/env python3
"""
analyze.py — turn scraped snapshots into a factual report

Reads aarsi_tracker.db (built by scraper.py) and reports only things that
are directly, verifiably true from Shopify's own data — no proxies, no
inferred "demand" or "trend" narratives layered on top:

  1. New launches   — products present in the latest snapshot that weren't
                       in the previous one (fact: created_at/published_at)
  2. Delisted        — products present before, gone now (fact: presence/absence)
  3. Stock changes   — variants that flipped from available to unavailable
                       or back, between two snapshot dates (fact, stated as
                       exactly that — not interpreted as "demand")
  4. Price changes   — price_min that differs between two snapshots (fact)
  5. Best-seller rank — ONLY present if you scraped with --sort best-selling.
                       This is Shopify's own computed ranking, built from
                       real sales data on their end — we're reading it, not
                       inferring it. Rank movement is reported as a plain
                       number change.
  6. Style keyword counts — a literal count of how many current product
                       titles/tags contain each keyword. This is catalog
                       composition, not a trend claim — it says nothing
                       about what's selling or being searched for.

What's explicitly NOT in here: no external search-interest data, no
"weighted trend scores", no language implying popularity or demand beyond
what the raw numbers state. See the final section for what's genuinely
unavailable and why.

Usage:
    python analyze.py                     # report on 'all-products'
    python analyze.py --collection all-products --out report.md
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "aarsi_tracker.db"

# Style/attribute vocabulary tuned to Aarsi's catalog (kurtis, co-ords,
# western dresses). Extend this list freely as their catalog evolves —
# it's just a keyword count, not a model.
STYLE_KEYWORDS = [
    "kurti", "kurta", "tunic", "co-ord", "coord", "set", "maxi dress",
    "mini dress", "pajama", "pyjama", "robe", "corset", "halter",
    "side-tie", "side tie", "front-tie", "front tie", "criss-cross",
    "lace-up", "peplum", "wrap", "angrakhi", "strapless", "sleeveless",
    "full sleeve", "puff sleeve", "flared sleeve", "belted",
    "square neck", "boat neck", "floral", "block print", "chevron",
    "dot", "stripe", "solid", "resort", "western",
]


def load_snapshots(collection: str) -> list[tuple[int, str]]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT snapshot_id, scraped_at FROM snapshots WHERE collection = ? ORDER BY scraped_at",
        (collection,),
    ).fetchall()
    conn.close()
    return rows


def load_products(snapshot_id: int) -> dict[int, dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM product_snapshots WHERE snapshot_id = ?", (snapshot_id,)
    ).fetchall()
    conn.close()
    return {row["product_id"]: dict(row) for row in rows}


def extract_style_keywords(text: str) -> list[str]:
    text = text.lower()
    found = []
    for kw in STYLE_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text):
            found.append(kw)
    return found


def build_report(collection: str) -> str:
    snaps = load_snapshots(collection)
    if not snaps:
        return f"No snapshots found for collection '{collection}'. Run scraper.py first."

    lines = []
    lines.append(f"# Aarsi ({collection}) — Trend Report")
    lines.append(f"_Generated {datetime.now().isoformat(timespec='minutes')}_\n")

    latest_id, latest_time = snaps[-1]
    latest = load_products(latest_id)
    lines.append(f"Latest snapshot: **{latest_time}** — {len(latest)} products live.\n")

    # ---------- 1 & 2: New launches + week-over-week moves ----------
    if len(snaps) >= 2:
        prev_id, prev_time = snaps[-2]
        prev = load_products(prev_id)

        new_ids = set(latest) - set(prev)
        removed_ids = set(prev) - set(latest)
        common_ids = set(latest) & set(prev)

        lines.append(f"## New launches since {prev_time}")
        if new_ids:
            for pid in new_ids:
                p = latest[pid]
                lines.append(f"- **{p['title']}** — ₹{p['price_min']:.0f} — https://aarsi.shop/products/{p['handle']}")
        else:
            lines.append("_None — no new products since the last snapshot._")
        lines.append("")

        if removed_ids:
            lines.append(f"## Delisted since {prev_time}")
            for pid in removed_ids:
                p = prev[pid]
                lines.append(f"- {p['title']}")
            lines.append("")

        lines.append(f"## Stock changes since {prev_time}")
        lines.append("Literal availability flips between the two snapshot dates — stated as fact, not interpreted:")
        restocked, sold_out = [], []
        for pid in common_ids:
            a, b = prev[pid], latest[pid]
            if not a["available"] and b["available"]:
                restocked.append(b["title"])
            elif a["available"] and not b["available"]:
                sold_out.append(b["title"])

        if sold_out:
            lines.append(f"\n**Went from in-stock to sold out** ({len(sold_out)}):")
            lines += [f"- {t}" for t in sold_out]
        if restocked:
            lines.append(f"\n**Went from sold out to in-stock** ({len(restocked)}):")
            lines += [f"- {t}" for t in restocked]
        if not (sold_out or restocked):
            lines.append("\n_No availability changes between these two snapshots._")
        lines.append("")

        lines.append(f"## Price changes since {prev_time}")
        price_changed = []
        for pid in common_ids:
            a, b = prev[pid], latest[pid]
            if a["price_min"] != b["price_min"]:
                price_changed.append(f"{b['title']}: ₹{a['price_min']:.0f} → ₹{b['price_min']:.0f}")
        if price_changed:
            lines += [f"- {t}" for t in price_changed]
        else:
            lines.append("_No price changes between these two snapshots._")
        lines.append("")

        # Best-seller rank movement, only if both snapshots captured rank.
        # This is Shopify's own computed ranking (from their real sales
        # data) — we're reading it as-is, not inferring or weighting it.
        if all(latest[pid]["rank"] for pid in common_ids if latest[pid]["rank"]) and \
           any(prev[pid]["rank"] for pid in common_ids):
            movers = []
            for pid in common_ids:
                r_prev, r_now = prev[pid]["rank"], latest[pid]["rank"]
                if r_prev and r_now:
                    movers.append((r_prev - r_now, latest[pid]["title"], r_prev, r_now))
            movers.sort(reverse=True)
            moved = [m for m in movers if m[0] != 0][:15]
            if moved:
                lines.append("## Best-seller rank changes (Shopify's own ranking, sort_by=best-selling)")
                for delta, title, r_prev, r_now in moved:
                    lines.append(f"- {title}: #{r_prev} → #{r_now}")
                lines.append("")
    else:
        lines.append("## New launches / week-over-week moves")
        lines.append(
            "_Only one snapshot so far — nothing to diff yet. Run scraper.py again next week "
            "and re-run this report._\n"
        )

    # ---------- Style keyword counts (raw catalog composition, no inference) ----------
    lines.append("## Style keyword counts (current catalog)")
    lines.append(
        "A literal count of how many live products' titles/tags contain each keyword. "
        "This describes what's currently *listed*, nothing about what's selling or being searched for."
    )
    counter = Counter()
    for p in latest.values():
        for kw in set(extract_style_keywords(f"{p['title']} {p['tags']}")):
            counter[kw] += 1

    if counter:
        lines.append("\n| Style keyword | Product count |")
        lines.append("|---|---|")
        for kw, count in counter.most_common(15):
            lines.append(f"| {kw} | {count} |")
    else:
        lines.append("_No keywords from STYLE_KEYWORDS matched any current title/tag._")
    lines.append("")

    # ---------- Most-searched keywords: not included, on purpose ----------
    lines.append("## Most-searched keywords")
    lines.append(
        "Deliberately left out of this report rather than filled with a substitute. "
        "On-site search terms are logged in Shopify's own **Analytics → Search & Discovery**, "
        "visible only to whoever has admin access to this store — nothing public exposes them, "
        "so there's no real data to report here from outside the store."
    )
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate a factual report from scraped Aarsi snapshots.")
    parser.add_argument("--collection", default="all-products")
    parser.add_argument("--out", default=None, help="Write report to this file instead of stdout")
    args = parser.parse_args()

    report = build_report(args.collection)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"Report written to {args.out}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
