# Aarsi (aarsi.shop) Catalog Tracker

A small, two-script pipeline that turns Aarsi's public product feed into a
weekly factual report: new launches, stock/price changes, best-seller rank
changes, and style-keyword counts. Everything in the report is a direct
read of Shopify's own data — nothing is proxied, estimated, or inferred.

## Why this approach, not HTML scraping

Aarsi runs on Shopify. Every Shopify storefront exposes its catalog as
structured JSON at `/collections/<handle>/products.json` — the same data
that renders the page, with no login and no CSS selectors to keep patching
every time their theme changes. That's what `scraper.py` pulls from. It's
faster, more stable, and returns fields (creation date, per-variant stock,
compare-at price) that aren't reliably visible in the rendered HTML at all.

## What each of your 4 asks actually maps to — real data only

Nothing below is estimated, weighted, or substituted. Where real data
doesn't exist publicly, the report says so and stops, rather than filling
the gap with a proxy.

| You asked for | Available as real data? | What it actually is |
|---|---|---|
| **New launches** | Yes | `created_at`/`published_at` per product, diffed between two snapshots |
| **Article performance week-over-week** | Partially | Only the parts that are literal facts: availability flips (sold out ↔ in stock), price changes, and Shopify's own best-seller rank order (see below). No sales figures, no "performance" scoring |
| **Trending styles** | Partially | A raw count of how many *current* product titles/tags contain each style keyword — this is catalog composition, not a claim about what's popular or trending |
| **Most-searched keywords** | **No** | Left out entirely — see below |

**On "most searched keywords":** the data doesn't exist anywhere public.
Shopify logs on-site search terms in the store's own
**Analytics → Search & Discovery** dashboard, visible only to whoever has
admin access to that Shopify account. No storefront page, sitemap, or JSON
feed exposes it. This report doesn't include a substitute for it — if you
have (or can get) admin access to this store, that dashboard is the only
real source.

**On "week-over-week performance":** actual units sold / revenue is
private, admin-only data. What Shopify *does* expose publicly is the
**rank order** under `?sort_by=best-selling` — that's Shopify's own
computed ranking, built from their real sales data. Scrape with
`--sort best-selling` on a schedule and `analyze.py` reports the rank
number changes as-is, with no scoring or weighting applied on top.

## Setup

```bash
pip install -r requirements.txt
```

## Dashboard (recommended way to run this)

```bash
python app.py
# then open http://127.0.0.1:5000
```

A local page that:
- lists exactly what's live right now (same table as above, kept honest — a
  capability shows "conditional" or "unavailable" right on the card, it
  never claims more than the scripts actually do)
- lets you trigger a scrape or a report generation with a button, with the
  console output streamed back live
- shows the latest snapshot's stats and the latest report, refreshed
  automatically when a run finishes

It's a thin wrapper — `app.py` just runs `scraper.py`/`analyze.py` as
subprocesses in the background and polls their output. All the actual
logic still lives in those two files; nothing new talks to aarsi.shop.

Note: this has to run somewhere that can actually reach `aarsi.shop` —
your own machine, not a network-locked sandbox. If a scrape fails, the
error shows up directly in the console panel rather than hanging.

## Command-line usage (if you'd rather not use the dashboard)

Run once a week (or whatever cadence you want to track):

```bash
# Core catalog, default (Featured) order
python scraper.py

# Also capture best-seller rank + pull New Arrivals in the same run
python scraper.py --sort best-selling --also-new-arrivals
```

Then generate the report:

```bash
python analyze.py --collection all-products --out report.md
```

The first run just seeds the database — you need at least two snapshots
before there's anything to diff. From the second run onward you get:

- New launches since the last snapshot
- Delisted products
- Availability changes (sold out ↔ restocked), stated as fact
- Price changes, stated as fact
- Best-seller rank changes (only if scraped with `--sort best-selling`)
- Style-keyword count table (raw counts, no weighting)
- A note on what's left out and why (search keywords)

## Scheduling it weekly (cron)

```cron
0 9 * * 1 cd /path/to/aarsi-scraper && python3 scraper.py --sort best-selling --also-new-arrivals && python3 analyze.py --out reports/$(date +\%F).md
```

## Data storage

Everything lands in `aarsi_tracker.db` (SQLite), two tables: `snapshots`
(one row per scrape run) and `product_snapshots` (one row per product per
run). Nothing external — you own the file, easy to back up or drop into
pandas/BigQuery later if you want to build on it.

## Being a good citizen about it

- `REQUEST_DELAY_SECONDS` in `scraper.py` throttles requests — don't set
  it to 0. This is public data but it's still someone else's server.
- The `User-Agent` string identifies the bot and has a placeholder contact
  email — put a real one in if you're running this on a recurring
  schedule, standard practice for anything automated.
- Worth a skim of `https://aarsi.shop/robots.txt` and their Terms of
  Service before scheduling this long-term, particularly if the output
  will ever be used commercially rather than for personal research.
- This pulls product/catalog data only — no checkout, no account data, no
  attempt to access anything not already public on the site.

## Extending it

- `STYLE_KEYWORDS` in `analyze.py` is a plain list — add/remove terms as
  Aarsi's catalog language shifts (new fabric names, cuts, etc.).
- Want size/color-level sellout tracking instead of product-level? The
  `variants` array in `normalize_product()` (scraper.py) already has
  per-variant `available` — currently collapsed to "any variant in
  stock"; split it out if you need finer granularity.
- Want this for other Shopify stores? Both scripts only assume the
  `/collections/<handle>/products.json` shape, which is store-agnostic —
  just change `BASE_URL`.
