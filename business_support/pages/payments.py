"""Payment Management — worker salaries, vendor debt, Meesho payout rollout, 30-day cashflow forecast."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import query, execute, get_conn, get_param, set_param, get_calendar_events, get_meesho_entries


def show_payments(multiplier=1.5):
    st.title("💳 Payment & Cashflow Management")

    # ─── FINANCIAL POSITION OVERVIEW ─────────────────────────
    st.subheader("💰 Financial Position & Debt Tracker")

    sales_summary = query("SELECT COALESCE(SUM(quantity_sold), 0) as total_qty, COALESCE(SUM(total_revenue), 0) as total_rev FROM sales", fetchone=True)
    meesho_summary = query("SELECT COALESCE(SUM(sold_qty), 0) as total_qty, COALESCE(SUM(gross_sales_amount), 0) as gross, COALESCE(SUM(net_receivable_amount), 0) as receivable FROM meesho_dashboard", fetchone=True)
    paid_summary = query("SELECT COALESCE(SUM(amount), 0) as total_paid FROM payments WHERE status = 'paid'", fetchone=True)
    vendor_debt_param = float(get_param("vendor_debt_remaining", "0"))
    worker_pending = query("SELECT COALESCE(SUM(daily_salary), 0) as total FROM workers", fetchone=True).get("total", 0)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Total Sales Revenue", f"₹{sales_summary['total_rev'] + meesho_summary['gross']:,.2f}")
    with col_m2:
        st.metric("Meesho Receivables", f"₹{meesho_summary['receivable']:,.2f}")
    with col_m3:
        st.metric("Remaining Vendor Debt", f"₹{vendor_debt_param:,.2f}")
    with col_m4:
        st.metric("Pending Worker Pay", f"₹{worker_pending:,.2f}")

    # Update Vendor Debt form
    with st.expander("✏️ Update Remaining Vendor Debt"):
        with st.form("update_vendor_debt"):
            new_debt = st.number_input("Remaining Vendor Debt (₹)", min_value=0.0, value=vendor_debt_param, step=100.0)
            if st.form_submit_button("Save Debt Amount"):
                set_param("vendor_debt_remaining", str(new_debt))
                st.success("✅ Remaining vendor debt updated!")
                st.rerun()

    st.divider()

    # ─── 30-DAY CASHFLOW & ROLLOUT TIMING FORECAST ───────────
    st.subheader("📊 30-Day Cashflow & Rollout Timing Forecast")
    st.caption("Forecasts Meesho payment rollouts, worker paydays, vendor due dates, and net balance")

    # Configurable payout parameters
    c_col1, c_col2, c_col3 = st.columns(3)
    with c_col1:
        meesho_payout_days = st.number_input("Meesho Payout Cycle (Days)", min_value=1, max_value=60, value=int(get_param("meesho_payout_cycle_days", "15")), step=1)
        set_param("meesho_payout_cycle_days", str(meesho_payout_days))
    with c_col2:
        worker_payday = st.selectbox("Worker Salary Payday", ["Weekly (Saturday)", "Weekly (Sunday)", "Daily"], index=0)
    with c_col3:
        vendor_lead_days = st.number_input("Vendor Payment Lead Time (Days)", min_value=1, max_value=30, value=int(get_param("vendor_lead_days", "7")), step=1)
        set_param("vendor_lead_days", str(vendor_lead_days))

    # Forecast Engine over 30 days
    today = datetime.now().date()
    meesho_pending = query("SELECT * FROM meesho_dashboard WHERE payout_status = 'Pending'")
    cal_events = get_calendar_events()

    cashflow_records = []
    accumulated_net = 0.0

    for i in range(30):
        c_date = today + timedelta(days=i)
        c_date_str = c_date.strftime("%Y-%m-%d")

        # Inflow: Expected Meesho payouts for this date
        inflow = 0.0
        inflow_notes = []
        for me in meesho_pending:
            if me.get("expected_payout_date") == c_date_str:
                amt = float(me.get("net_receivable_amount", 0))
                inflow += amt
                inflow_notes.append(f"Meesho Payout (₹{amt:,.0f})")

        # Outflow: Worker paydays (e.g. every Saturday)
        outflow = 0.0
        outflow_notes = []
        if worker_payday == "Daily" or (worker_payday.startswith("Weekly (Saturday)") and c_date.weekday() == 5) or (worker_payday.startswith("Weekly (Sunday)") and c_date.weekday() == 6):
            if worker_pending > 0 and i < 7:
                outflow += worker_pending / (1 if worker_payday == "Daily" else 1)
                outflow_notes.append(f"Worker Salaries (₹{outflow:,.0f})")

        # Outflow: Vendor due dates (before calendar event prep windows)
        for ev in cal_events:
            try:
                ev_date = datetime.strptime(ev["event_date"], "%Y-%m-%d").date()
                prep_days = int(ev.get("prep_days", 7))
                due_date = ev_date - timedelta(days=prep_days)
                if c_date == due_date and vendor_debt_param > 0:
                    v_pay = min(vendor_debt_param, vendor_debt_param / max(1, len(cal_events)))
                    outflow += v_pay
                    outflow_notes.append(f"Vendor Event Due: {ev['event_name']} (₹{v_pay:,.0f})")
            except (ValueError, TypeError):
                continue

        net_day = inflow - outflow
        accumulated_net += net_day

        if inflow > 0 or outflow > 0:
            cashflow_records.append(
                {
                    "Date": c_date_str,
                    "Day": c_date.strftime("%a"),
                    "Inflow (₹)": inflow,
                    "Outflow (₹)": outflow,
                    "Net (₹)": net_day,
                    "Cumul. Cash (₹)": accumulated_net,
                    "Details": "; ".join(inflow_notes + outflow_notes),
                }
            )

    if cashflow_records:
        df_cf = pd.DataFrame(cashflow_records)
        st.dataframe(df_cf, hide_index=True, use_container_width=True)

        fig_cf = go.Figure()
        fig_cf.add_trace(go.Bar(x=df_cf["Date"], y=df_cf["Inflow (₹)"], name="Inflow (Meesho Payouts)", marker_color="#2ecc71"))
        fig_cf.add_trace(go.Bar(x=df_cf["Date"], y=df_cf["Outflow (₹)"], name="Outflow (Workers/Vendors)", marker_color="#e74c3c"))
        fig_cf.add_trace(go.Scatter(x=df_cf["Date"], y=df_cf["Cumul. Cash (₹)"], name="Cumulative Cash", mode="lines+markers", line=dict(color="#f1c40f", width=3)))

        fig_cf.update_layout(title="📈 30-Day Projected Cashflow & Payout Rollout", barmode="group", template="plotly_dark", height=380)
        st.plotly_chart(fig_cf, use_container_width=True)
    else:
        st.info("No upcoming scheduled payouts or debts in the next 30 days. Log Meesho entries or calendar events to generate cashflow forecasts.")

    st.divider()

    # ─── WORKER SALARIES ────────────────────────────────────
    st.subheader("👥 Log / Verify Worker Salaries")
    workers = query("SELECT id, name, hourly_rate, pieces_made, hours_worked, daily_salary FROM workers ORDER BY name")
    pr_row = get_param("piece_rate", "20")
    piece_rate = float(pr_row)

    if workers:
        for w in workers:
            st.write(f"**{w['name']}** (₹{w['hourly_rate']}/hr)")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.caption(f"Hours: {w['hours_worked']} | Pieces: {w['pieces_made']}")
            with col2:
                basic = w["hours_worked"] * w["hourly_rate"]
                piece_bonus = w["pieces_made"] * piece_rate
                calc_salary = basic + piece_bonus
                st.info(f"Calculated: ₹{calc_salary:.2f}")
            with col3:
                if st.button(f"✅ Mark Paid", key=f"pay_{w['id']}"):
                    execute(
                        "INSERT INTO payments (type, amount, to_whom, date, status) VALUES (?, ?, ?, ?, ?)",
                        ("worker", calc_salary, w["name"], datetime.now().strftime("%Y-%m-%d"), "paid"),
                    )
                    execute("UPDATE workers SET daily_salary = 0, hours_worked = 0, pieces_made = 0 WHERE id = ?", (w["id"],))
                    st.success(f"✅ Paid ₹{calc_salary:.2f} to {w['name']}")
                    st.rerun()

    # ─── VENDOR PAYMENTS ────────────────────────────────────
    st.divider()
    st.subheader("🏪 Record Vendor Payment")
    vendors = query("SELECT id, name FROM vendors")
    vendor_payments = query("SELECT * FROM payments WHERE type = 'vendor' ORDER BY date DESC LIMIT 10")

    with st.form("vendor_payment_form"):
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            v_name = st.text_input("Vendor Name", placeholder="e.g. Fabric Supplier Co.")
        with col_v2:
            v_amount = st.number_input("Amount Paid (₹)", min_value=0.0, value=0.0, step=100.0)

        v_date = st.date_input("Payment Date", value=datetime.now())
        if st.form_submit_button("Record Vendor Payment") and v_name and v_amount > 0:
            execute("INSERT OR IGNORE INTO vendors (name) VALUES (?)", (v_name,))
            execute(
                "INSERT INTO payments (type, amount, to_whom, date, status) VALUES (?, ?, ?, ?, ?)",
                ("vendor", v_amount, v_name, v_date.strftime("%Y-%m-%d"), "paid"),
            )
            # Reduce remaining vendor debt
            current_debt = float(get_param("vendor_debt_remaining", "0"))
            set_param("vendor_debt_remaining", str(max(0.0, current_debt - v_amount)))
            st.success(f"✅ Vendor payment of ₹{v_amount:,.2f} recorded for {v_name}")
            st.rerun()

    if vendor_payments:
        st.write("#### Recent Vendor Payments")
        st.dataframe(pd.DataFrame(vendor_payments), hide_index=True, use_container_width=True)