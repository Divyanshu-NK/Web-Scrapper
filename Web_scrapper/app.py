#!/usr/bin/env python3
"""
app.py — local dashboard for the Aarsi catalog tracker

A thin UI over scraper.py / analyze.py. All the real work still happens
in those two scripts, run as subprocesses — this just:
  - lists exactly what's live right now (kept honest, matches README)
  - lets you trigger a scrape or a report generation from the browser
  - streams that run's console output back to the page
  - shows the latest snapshot summary and the latest report

Nothing in this file talks to aarsi.shop directly.

Run:
    pip install -r requirements.txt
    python app.py
    # then open http://127.0.0.1:5000
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "aarsi_tracker.db"
REPORT_PATH = BASE_DIR / "report.md"

app = Flask(__name__)

# Kept in one place so the UI can never claim more than the scripts
# actually do. "conditional" = only live if you pass the right flag.
# "unavailable" = not obtainable from outside the store, by design.
CAPABILITIES = [
    {
        "name": "New launches",
        "status": "live",
        "detail": "Products in the latest snapshot that weren't in the previous one \u2014 from created_at/published_at.",
    },
    {
        "name": "Delisted products",
        "status": "live",
        "detail": "Products that were in the previous snapshot and are gone now.",
    },
    {
        "name": "Stock changes",
        "status": "live",
        "detail": "Availability flips \u2014 sold out \u2194 in stock \u2014 between two snapshots, stated as fact.",
    },
    {
        "name": "Price changes",
        "status": "live",
        "detail": "Listed price differences between two snapshots.",
    },
    {
        "name": "Best-seller rank",
        "status": "conditional",
        "detail": "Shopify's own computed ranking. Only captured if you scrape with sort = best-selling.",
    },
    {
        "name": "Style keyword counts",
        "status": "live",
        "detail": "Raw count of current titles/tags containing catalog style keywords. Composition, not popularity.",
    },
    {
        "name": "Most-searched keywords",
        "status": "unavailable",
        "detail": "Lives only in Shopify's own Search & Discovery analytics \u2014 not exposed publicly.",
    },
]

SORT_OPTIONS = [
    ("", "Featured (default)"),
    ("best-selling", "Best selling"),
    ("created-descending", "Newest first"),
    ("price-ascending", "Price: low to high"),
    ("price-descending", "Price: high to low"),
]

# ---- in-memory run state — single-user local tool, so this is enough ----
_lock = threading.Lock()
_state = {
    "running": False,
    "job": None,        # "scrape" | "analyze"
    "log": [],
    "started_at": None,
    "finished_at": None,
    "returncode": None,
}


def _run_subprocess(cmd: list[str], job_name: str) -> None:
    with _lock:
        _state.update(
            running=True, job=job_name, log=[],
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None, returncode=None,
        )
    try:
        proc = subprocess.Popen(
            cmd, cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            with _lock:
                _state["log"].append(line.rstrip())
        proc.wait()
        returncode = proc.returncode
    except Exception as exc:  # e.g. interpreter not found — surface it, don't hang
        with _lock:
            _state["log"].append(f"[dashboard] failed to launch: {exc}")
        returncode = -1

    with _lock:
        _state.update(running=False, finished_at=datetime.now(timezone.utc).isoformat(), returncode=returncode)


def _latest_snapshot_summary() -> dict:
    if not DB_PATH.exists():
        return {"exists": False}
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT snapshot_id, scraped_at, collection, sort_by FROM snapshots ORDER BY snapshot_id DESC LIMIT 1"
    ).fetchone()
    if not row:
        conn.close()
        return {"exists": False}
    snapshot_id, scraped_at, collection, sort_by = row
    product_count = conn.execute(
        "SELECT COUNT(*) FROM product_snapshots WHERE snapshot_id = ?", (snapshot_id,)
    ).fetchone()[0]
    total_snapshots = conn.execute(
        "SELECT COUNT(*) FROM snapshots WHERE collection = ?", (collection,)
    ).fetchone()[0]
    conn.close()
    return {
        "exists": True,
        "scraped_at": scraped_at,
        "collection": collection,
        "sort_by": sort_by,
        "product_count": product_count,
        "total_snapshots": total_snapshots,
        "ready_to_diff": total_snapshots >= 2,
    }


@app.route("/")
def index():
    return render_template(
        "index.html",
        capabilities=CAPABILITIES,
        sort_options=SORT_OPTIONS,
        snapshot=_latest_snapshot_summary(),
        report=REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else None,
    )


@app.route("/status")
def status():
    with _lock:
        return jsonify(dict(_state))


@app.route("/snapshot")
def snapshot():
    return jsonify(_latest_snapshot_summary())


@app.route("/report")
def report():
    if REPORT_PATH.exists():
        return jsonify({"report": REPORT_PATH.read_text(encoding="utf-8")})
    return jsonify({"report": None})


@app.route("/run/scrape", methods=["POST"])
def run_scrape():
    with _lock:
        if _state["running"]:
            return jsonify({"error": "A job is already running."}), 409

    collection = (request.form.get("collection") or "all-products").strip() or "all-products"
    sort_by = (request.form.get("sort") or "").strip()
    also_new = request.form.get("also_new_arrivals") == "on"

    cmd = [sys.executable, "scraper.py", "--collection", collection]
    if sort_by:
        cmd += ["--sort", sort_by]
    if also_new:
        cmd += ["--also-new-arrivals"]

    threading.Thread(target=_run_subprocess, args=(cmd, "scrape"), daemon=True).start()
    return jsonify({"started": True})


@app.route("/run/analyze", methods=["POST"])
def run_analyze():
    with _lock:
        if _state["running"]:
            return jsonify({"error": "A job is already running."}), 409

    collection = (request.form.get("collection") or "all-products").strip() or "all-products"
    cmd = [sys.executable, "analyze.py", "--collection", collection, "--out", str(REPORT_PATH)]
    threading.Thread(target=_run_subprocess, args=(cmd, "analyze"), daemon=True).start()
    return jsonify({"started": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
