"""Worker Management — log hours/pieces, salary calc."""

import streamlit as st
from datetime import datetime
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import query, execute, get_param


def show_workers(multiplier=1.5):
    st.header("👥 Workers")

    piece_rate = int(float(get_param("piece_rate", "20")))
    today = datetime.now().strftime("%Y-%m-%d")

    # ── Add Worker ──
    with st.expander("➕ Add Worker", expanded=False):
        with st.form("add_w"):
            c1, c2 = st.columns(2)
            with c1:
                w_name = st.text_input("Name")
            with c2:
                w_rate = st.number_input("Hourly Rate (₹)", min_value=10, value=50, step=5)
            if st.form_submit_button("Add") and w_name:
                execute("INSERT INTO workers (name, hourly_rate, date) VALUES (?,?,?)", (w_name, w_rate, today))
                st.success(f"✅ {w_name} added!")
                st.rerun()

    # ── Daily Log ──
    workers = query("SELECT id, name, hourly_rate, hours_worked, pieces_made, daily_salary FROM workers ORDER BY name")

    if not workers:
        st.info("No workers yet — add your first worker above.")
        return

    st.subheader("🕒 Daily Log")

    for w in workers:
        with st.container():
            c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1.5])
            with c1:
                st.markdown(f"**{w['name']}** · ₹{w['hourly_rate']}/hr")
            with c2:
                hrs = st.number_input("Hours", 0.0, 24.0, float(w["hours_worked"] or 0), 0.5, key=f"h_{w['id']}")
            with c3:
                pcs = st.number_input("Pieces", 0, 200, int(w["pieces_made"] or 0), 1, key=f"p_{w['id']}")
            with c4:
                sal = hrs * w["hourly_rate"] + pcs * piece_rate
                st.metric("Salary", f"₹{sal:.0f}")

            # Auto-save
            if hrs != w["hours_worked"] or pcs != w["pieces_made"]:
                execute("UPDATE workers SET hours_worked=?, pieces_made=?, daily_salary=?, date=? WHERE id=?",
                        (hrs, pcs, sal, today, w["id"]))

    # ── Summary ──
    st.divider()
    total_hrs = sum(w["hours_worked"] or 0 for w in workers)
    total_pcs = sum(w["pieces_made"] or 0 for w in workers)
    total_sal = sum((w["hours_worked"] or 0) * w["hourly_rate"] + (w["pieces_made"] or 0) * piece_rate for w in workers)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Hours", f"{total_hrs:.1f}")
    c2.metric("Total Pieces", total_pcs)
    c3.metric("Total Salary", f"₹{total_sal:,.0f}")

    # ── Payment History ──
    with st.expander("📜 Payment History"):
        payments = query("SELECT to_whom, amount, date, status FROM payments WHERE type='worker' ORDER BY date DESC LIMIT 20")
        if payments:
            import pandas as pd
            st.dataframe(pd.DataFrame(payments), hide_index=True, use_container_width=True)
        else:
            st.caption("No payments recorded yet.")