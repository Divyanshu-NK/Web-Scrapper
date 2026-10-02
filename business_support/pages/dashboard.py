"""Dashboard — key metrics, calendar events scheduler, alerts, projections."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import query, execute, get_active_event_multiplier, get_calendar_events, save_calendar_event, delete_calendar_event


def show_dashboard(multiplier=1.5):
    st.header("📊 Daily Dashboard")

    today_str = datetime.now().strftime("%Y-%m-%d")

    # ─── CALENDAR-BASED EVENT SCHEDULER ─────────────────────
    st.subheader("🗓️ Calendar Event Scheduler & Prep Time Tracker")
    st.caption("Mark upcoming events on the calendar — standard 1-week prep window applies 1.5x demand factor automatically")

    cal_events = get_calendar_events()

    # Form to add calendar event
    with st.expander("➕ Add / Mark Calendar Event", expanded=(not cal_events)):
        with st.form("add_calendar_event_form"):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                e_name = st.text_input("Event Name", placeholder="e.g., Diwali Rush, Festive Sale, Wedding Season")
                e_date = st.date_input("Event Date", value=datetime.now() + timedelta(days=14))
            with col_e2:
                e_prep_days = st.number_input("Event Prep Time (Days)", min_value=1, max_value=30, value=7, help="Standard is 1 week (7 days) before event date")
                e_factor = st.number_input("Demand Factor (Multiplier)", min_value=1.0, max_value=5.0, value=1.5, step=0.1, help="Applied during prep window and event day")

            e_notes = st.text_input("Notes (optional)", placeholder="e.g. Target 500 Kurtis stock")

            if st.form_submit_button("📅 Mark Event on Calendar", type="primary") and e_name:
                save_calendar_event(
                    event_name=e_name,
                    event_date=e_date.strftime("%Y-%m-%d"),
                    prep_days=e_prep_days,
                    event_duration_days=1,
                    demand_factor=e_factor,
                    notes=e_notes,
                )
                st.success(f"✅ Marked '{e_name}' on {e_date} (Prep Window: {e_prep_days} days @ {e_factor}x factor)")
                st.rerun()

    # Display active & upcoming calendar events
    if cal_events:
        today_date = datetime.now().date()
        st.write("#### 📌 Scheduled Calendar Events & Prep Windows")

        event_cards = []
        for ev in cal_events:
            try:
                ev_date = datetime.strptime(ev["event_date"], "%Y-%m-%d").date()
                prep_days = int(ev.get("prep_days", 7))
                prep_start = ev_date - timedelta(days=prep_days)

                is_in_prep = prep_start <= today_date <= ev_date
                status_pill = "🔥 ACTIVE PREP WINDOW (1.5x)" if is_in_prep else ("⏰ Upcoming" if today_date < prep_start else "✅ Passed")

                event_cards.append(
                    {
                        "ID": ev["id"],
                        "Event": ev["event_name"],
                        "Event Date": ev["event_date"],
                        "Prep Start Date": prep_start.strftime("%Y-%m-%d"),
                        "Prep Time": f"{prep_days} days",
                        "Factor": f"{ev.get('demand_factor', 1.5)}x",
                        "Status": status_pill,
                        "Notes": ev.get("notes") or "—",
                    }
                )
            except (ValueError, TypeError):
                continue

        df_ev = pd.DataFrame(event_cards)
        st.dataframe(df_ev, hide_index=True, use_container_width=True)

        # Quick delete event dropdown
        del_col1, del_col2 = st.columns([3, 1])
        with del_col1:
            ev_to_del = st.selectbox("Select event to remove", options=[ev["id"] for ev in cal_events], format_func=lambda x: next(e["event_name"] for e in cal_events if e["id"]==x))
        with del_col2:
            if st.button("🗑️ Delete Event"):
                delete_calendar_event(ev_to_del)
                st.success("Deleted event!")
                st.rerun()

    st.divider()

    # ── Fetch all metrics in minimal queries ──
    prod = query(
        "SELECT COALESCE(SUM(quantity_made),0) as made, COALESCE(SUM(revenue),0) as rev, COALESCE(SUM(cloth_used),0) as cloth FROM kurti_production WHERE date=?",
        (today_str,), fetchone=True,
    )
    sales = query(
        "SELECT COALESCE(SUM(quantity_sold),0) as sold, COALESCE(SUM(total_revenue),0) as rev FROM sales WHERE date=?",
        (today_str,), fetchone=True,
    )
    wk = query(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(hours_worked),0) as hrs, COALESCE(SUM(pieces_made),0) as pcs, COALESCE(SUM(daily_salary),0) as sal FROM workers",
        fetchone=True,
    )

    # ── Metrics row 1 ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kurtis Made Today", prod.get("made", 0))
    c2.metric("Revenue Today", f"₹{prod.get('rev', 0):,.0f}")
    c3.metric("Cloth Used Today", f"{prod.get('cloth', 0):.1f} m")
    c4.metric("Workers Active", wk.get("cnt", 0), f"{wk.get('hrs', 0):.0f} hrs")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Kurtis Sold Today", sales.get("sold", 0))
    c6.metric("Sales Revenue Today", f"₹{sales.get('rev', 0):,.0f}")
    cnt = max(wk.get("cnt", 1), 1)
    c7.metric("Avg Hrs/Worker", f"{wk.get('hrs', 0) / cnt:.1f}")
    c8.metric("Avg Pcs/Worker", f"{wk.get('pcs', 0) / cnt:.1f}")

    # ── Charts (lazy import) ──
    st.subheader("📈 Last 7 Days Analytics")
    col_a, col_b = st.columns(2)

    sales_7d = query("SELECT date, SUM(total_revenue) as rev FROM sales GROUP BY date ORDER BY date DESC LIMIT 7")
    prod_7d = query("SELECT date, SUM(quantity_made) as qty FROM kurti_production GROUP BY date ORDER BY date DESC LIMIT 7")

    if sales_7d or prod_7d:
        import plotly.express as px

        with col_a:
            if sales_7d:
                df = pd.DataFrame(sales_7d)
                fig = px.bar(df, x="date", y="rev", title="Sales Revenue", color_discrete_sequence=["#2ecc71"])
                fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=250, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No sales data yet")

        with col_b:
            if prod_7d:
                df = pd.DataFrame(prod_7d)
                fig = px.bar(df, x="date", y="qty", title="Production Quantity", color_discrete_sequence=["#3498db"])
                fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=250, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No production data yet")
    else:
        st.info("Start recording production and sales to see analytics here.")