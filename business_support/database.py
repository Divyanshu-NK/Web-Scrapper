"""
Shared database module for Kurti Manufacturing Management System.
Uses cached connections and query helpers for fast performance.
Includes calendar-based events, 30-day inventory & cashflow forecasting, and Meesho dashboard tracking.
"""

import sqlite3
import os
from datetime import datetime, timedelta

# Resolve database path relative to this file
_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DIR, "kurti_business.db")


def get_conn():
    """Return a connection with Row factory and WAL mode for concurrent reads."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def query(sql, params=(), fetchone=False):
    """Execute a read query and return results as list of dicts."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        if fetchone:
            row = c.fetchone()
            return dict(row) if row else {}
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def execute(sql, params=()):
    """Execute a write query (INSERT/UPDATE/DELETE)."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def executemany(statements):
    """Execute multiple statements in a single transaction. Each is (sql, params)."""
    conn = get_conn()
    try:
        c = conn.cursor()
        for sql, params in statements:
            c.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all required tables if they don't exist."""
    conn = get_conn()
    c = conn.cursor()

    tables = [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT,
            email TEXT,
            setup_completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS event_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_name TEXT,
            start_date TEXT,
            end_date TEXT,
            demand_multiplier REAL DEFAULT 1.5,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (date('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            prep_days INTEGER DEFAULT 7,
            event_duration_days INTEGER DEFAULT 1,
            demand_factor REAL DEFAULT 1.5,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS meesho_dashboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            orders_count INTEGER DEFAULT 0,
            sold_qty INTEGER DEFAULT 0,
            gross_sales_amount REAL DEFAULT 0,
            meesho_commission_fees REAL DEFAULT 0,
            net_receivable_amount REAL DEFAULT 0,
            payout_status TEXT DEFAULT 'Pending',
            expected_payout_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT,
            quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'meters',
            supplier TEXT,
            cost_per_unit REAL DEFAULT 0,
            date_added TEXT DEFAULT (date('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            hourly_rate REAL DEFAULT 50,
            pieces_made INTEGER DEFAULT 0,
            hours_worked REAL DEFAULT 0,
            date TEXT DEFAULT (date('now')),
            daily_salary REAL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS kurti_production (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            design_name TEXT NOT NULL,
            material_id INTEGER,
            quantity_made INTEGER DEFAULT 1,
            cloth_used REAL DEFAULT 0,
            wastage_percent REAL DEFAULT 0,
            sale_price REAL DEFAULT 0,
            date TEXT DEFAULT (date('now')),
            revenue REAL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            design_name TEXT NOT NULL,
            quantity_sold INTEGER DEFAULT 1,
            price_per_unit REAL DEFAULT 0,
            total_revenue REAL DEFAULT 0,
            meshop_reference TEXT,
            date TEXT DEFAULT (date('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            to_whom TEXT NOT NULL,
            date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'pending'
        )""",
        """CREATE TABLE IF NOT EXISTS cloth_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER,
            kurti_id INTEGER DEFAULT 0,
            quantity_used REAL DEFAULT 0,
            date TEXT DEFAULT (date('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS business_params (
            param_key TEXT PRIMARY KEY,
            value TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            avg_cost_per_kurti REAL DEFAULT 0,
            date_added TEXT DEFAULT (date('now'))
        )""",
    ]

    for sql in tables:
        c.execute(sql)

    conn.commit()
    conn.close()


def reset_db():
    """Drop and recreate the database."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()


# ─── Helper functions ──────────────────────────────────────


def get_user():
    return query("SELECT * FROM users WHERE id = 1", fetchone=True)


def get_param(key, default=""):
    row = query("SELECT value FROM business_params WHERE param_key = ?", (key,), fetchone=True)
    return row.get("value", default) if row else default


def set_param(key, value):
    execute("INSERT OR REPLACE INTO business_params (param_key, value) VALUES (?, ?)", (key, str(value)))


def get_event_periods():
    return query("SELECT * FROM event_periods ORDER BY created_at DESC")


def save_event_period(name, start, end, multiplier, active=1):
    execute(
        "INSERT INTO event_periods (period_name, start_date, end_date, demand_multiplier, is_active) VALUES (?, ?, ?, ?, ?)",
        (name, start, end, multiplier, active),
    )


def delete_event_period(pid):
    execute("DELETE FROM event_periods WHERE id = ?", (pid,))


def update_event_period(pid, name, start, end, multiplier, active):
    execute(
        "UPDATE event_periods SET period_name=?, start_date=?, end_date=?, demand_multiplier=?, is_active=? WHERE id=?",
        (name, start, end, multiplier, active, pid),
    )


# ─── CALENDAR EVENTS HELPERS ────────────────────────────────


def get_calendar_events():
    return query("SELECT * FROM calendar_events ORDER BY event_date ASC")


def save_calendar_event(event_name, event_date, prep_days=7, event_duration_days=1, demand_factor=1.5, notes=""):
    return execute(
        "INSERT INTO calendar_events (event_name, event_date, prep_days, event_duration_days, demand_factor, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (event_name, event_date, prep_days, event_duration_days, demand_factor, notes),
    )


def delete_calendar_event(event_id):
    execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))


def get_active_event_multiplier(date_str=None):
    """
    Calculate demand multiplier for a given date (default today).
    Checks both calendar_events (with 1-week prep window & custom prep days) and event_periods.
    Returns the maximum multiplier found (default 1.0 if no event active).
    """
    if date_str is None:
        target_date = datetime.now().date()
    elif isinstance(date_str, datetime):
        target_date = date_str.date()
    else:
        try:
            target_date = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.now().date()

    max_factor = 1.0

    # 1. Check calendar events (prep window + event duration)
    events = query("SELECT * FROM calendar_events")
    for ev in events:
        try:
            edate = datetime.strptime(ev["event_date"], "%Y-%m-%d").date()
            prep_days = int(ev.get("prep_days", 7))
            duration = int(ev.get("event_duration_days", 1))
            prep_start = edate - timedelta(days=prep_days)
            event_end = edate + timedelta(days=duration - 1)
            if prep_start <= target_date <= event_end:
                factor = float(ev.get("demand_factor", 1.5))
                if factor > max_factor:
                    max_factor = factor
        except (ValueError, TypeError):
            continue

    # 2. Check legacy event_periods
    periods = query("SELECT * FROM event_periods WHERE is_active = 1")
    for p in periods:
        try:
            s = datetime.strptime(p["start_date"], "%Y-%m-%d").date()
            e = datetime.strptime(p["end_date"], "%Y-%m-%d").date()
            if s <= target_date <= e:
                factor = float(p["demand_multiplier"])
                if factor > max_factor:
                    max_factor = factor
        except (ValueError, TypeError):
            continue

    return max_factor


def calculate_demand_multiplier(today_str=None):
    return get_active_event_multiplier(today_str)


# ─── MEESHO HELPERS ─────────────────────────────────────────


def get_meesho_entries():
    return query("SELECT * FROM meesho_dashboard ORDER BY date DESC")


def save_meesho_entry(
    date, orders_count, sold_qty, gross_sales_amount, meesho_commission_fees, net_receivable_amount, expected_payout_date, payout_status="Pending", notes=""
):
    return execute(
        "INSERT INTO meesho_dashboard (date, orders_count, sold_qty, gross_sales_amount, meesho_commission_fees, net_receivable_amount, expected_payout_date, payout_status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (date, orders_count, sold_qty, gross_sales_amount, meesho_commission_fees, net_receivable_amount, expected_payout_date, payout_status, notes),
    )
