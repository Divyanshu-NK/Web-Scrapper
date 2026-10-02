"""Settings & Business Rules — event periods, business params, user profile, help."""

import streamlit as st
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_conn


def show_settings(multiplier=1.5):
    st.title("⚙️ Settings & Business Rules")

    # ─── EVENT PERIOD MANAGEMENT ────────────────────────────
    st.subheader("📅 Event Periods & Demand Multipliers")
    st.caption("Set event periods to adjust demand forecasting. Default multiplier: 1.5x")

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM event_periods ORDER BY created_at")
    periods = c.fetchall()
    conn.close()

    st.write("**Current Event Periods:**")
    if periods:
        for p in periods:
            active_label = "✅ Active" if p["is_active"] else "❌ Inactive"
            st.caption(
                f"**{p['period_name']}**: {p['start_date']} to {p['end_date']} | "
                f"Demand Multiplier: **{p['demand_multiplier']}x** | {active_label}"
            )

            col_t, col_e = st.columns(2)
            with col_t:
                if st.button(f"Toggle Active", key=f"sp_toggle_{p['id']}"):
                    conn = get_conn()
                    c = conn.cursor()
                    new_status = 0 if p["is_active"] else 1
                    c.execute("UPDATE event_periods SET is_active = ? WHERE id = ?", (new_status, p["id"]))
                    conn.commit()
                    conn.close()
                    st.rerun()

            with st.expander(f"Edit {p['period_name']} details"):
                new_name = st.text_input("Period Name", value=p["period_name"], key=f"sp_name_{p['id']}")
                c1, c2 = st.columns(2)
                with c1:
                    try:
                        start_val = datetime.strptime(p["start_date"], "%Y-%m-%d")
                    except (ValueError, TypeError):
                        start_val = datetime.now()
                    new_start = st.date_input("Start Date", value=start_val, key=f"sp_start_{p['id']}")
                with c2:
                    try:
                        end_val = datetime.strptime(p["end_date"], "%Y-%m-%d")
                    except (ValueError, TypeError):
                        end_val = datetime.now() + timedelta(days=90)
                    new_end = st.date_input("End Date", value=end_val, key=f"sp_end_{p['id']}")
                new_multiplier = st.slider(
                    "Demand Multiplier", 1.0, 3.0, float(p["demand_multiplier"]), 0.1, key=f"sp_multiplier_{p['id']}"
                )

                if st.button(f"Update {p['period_name']}", key=f"sp_update_{p['id']}"):
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute(
                        "UPDATE event_periods SET period_name=?, start_date=?, end_date=?, demand_multiplier=? WHERE id=?",
                        (new_name, new_start.strftime("%Y-%m-%d"), new_end.strftime("%Y-%m-%d"), new_multiplier, p["id"]),
                    )
                    conn.commit()
                    conn.close()
                    st.success("✅ Period updated!")
                    st.rerun()
    else:
        st.info("No event periods defined.")

    # Add new period
    st.write("**Add New Event Period:**")
    with st.form("settings_add_period_form"):
        p_name = st.text_input("Period Name", value="", key="sp_new_name")
        c1, c2 = st.columns(2)
        with c1:
            p_start = st.date_input("Start Date", value=datetime.now(), key="sp_new_start")
        with c2:
            p_end = st.date_input("End Date", value=datetime.now() + timedelta(days=90), key="sp_new_end")
        p_multiplier = st.slider("Demand Multiplier", 1.0, 3.0, 1.5, 0.1, key="sp_new_mult")
        p_submitted = st.form_submit_button("Add Period")

        if p_submitted and p_name:
            conn = get_conn()
            c = conn.cursor()
            c.execute(
                "INSERT INTO event_periods (period_name, start_date, end_date, demand_multiplier, is_active) VALUES (?, ?, ?, ?, 1)",
                (p_name, p_start.strftime("%Y-%m-%d"), p_end.strftime("%Y-%m-%d"), p_multiplier),
            )
            conn.commit()
            conn.close()
            st.success("✅ Event period added!")
            st.rerun()

    # ─── BUSINESS PARAMETERS ────────────────────────────────
    st.subheader("📋 Business Configuration Parameters")

    conn = get_conn()
    c = conn.cursor()

    def _get_param(key, default):
        c.execute("SELECT value FROM business_params WHERE param_key = ?", (key,))
        row = c.fetchone()
        return row["value"] if row else default

    cloth_per_kurti = _get_param("cloth_per_kurti", "2.5")
    piece_rate = _get_param("piece_rate", "20")
    low_stock_threshold = _get_param("low_stock_threshold", "3")
    hourly_rate_default = _get_param("hourly_rate_default", "50")

    conn.close()

    with st.form("business_params_form"):
        st.write("**Adjust Core Business Parameters:**")

        new_cloth_per_kurti = st.number_input(
            "Cloth per Kurti (meters)",
            min_value=0.5, max_value=10.0, value=float(cloth_per_kurti), step=0.1,
            help="How much cloth is needed to make one kurti",
        )
        new_piece_rate = st.number_input(
            "Piece Rate per Worker (₹ per piece)",
            min_value=0, max_value=100, value=int(float(piece_rate)), step=1,
            help="Bonus amount given to worker per kurti produced",
        )
        new_low_stock_threshold = st.number_input(
            "Low Stock Alert Threshold (days)",
            min_value=1, max_value=14, value=int(float(low_stock_threshold)),
            help="Alert when stock will run out in this many days",
        )
        new_hourly_rate = st.number_input(
            "Default Hourly Rate for Workers (₹)",
            min_value=10, max_value=500, value=int(float(hourly_rate_default)), step=5,
            help="Base hourly rate for salary calculation",
        )

        submitted = st.form_submit_button("Save Parameters")

        if submitted:
            conn = get_conn()
            c = conn.cursor()
            params = {
                "cloth_per_kurti": str(new_cloth_per_kurti),
                "piece_rate": str(new_piece_rate),
                "low_stock_threshold": str(new_low_stock_threshold),
                "hourly_rate_default": str(new_hourly_rate),
            }
            for k, v in params.items():
                c.execute("INSERT OR REPLACE INTO business_params (param_key, value) VALUES (?, ?)", (k, v))
            conn.commit()
            conn.close()
            st.success("✅ Business parameters saved successfully!")
            st.rerun()

    # ─── USER PROFILE ───────────────────────────────────────
    st.subheader("👤 User Profile")

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = 1")
    user = c.fetchone()
    conn.close()

    if user:
        st.write(f"**Name:** {user['name'] or 'Not set'}")
        st.write(f"**Email:** {user['email'] or 'Not set'}")
        st.write(f"**Role:** {user['role']}")

        with st.expander("Update Profile"):
            with st.form("update_profile_form"):
                new_name = st.text_input("Full Name", value=user["name"] or "")
                new_email = st.text_input("Email", value=user["email"] or "")

                if st.form_submit_button("Update Profile"):
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("UPDATE users SET name = ?, email = ? WHERE id = 1", (new_name, new_email))
                    conn.commit()
                    conn.close()
                    st.success("✅ Profile updated!")
                    st.rerun()

    # ─── DANGER ZONE ────────────────────────────────────────
    st.subheader("🔴 Danger Zone")
    with st.expander("⚠️ Reset Database", expanded=False):
        st.warning("This will delete ALL data and start fresh. This cannot be undone!")
        if st.button("🗑️ Reset Everything", type="primary"):
            from database import reset_db
            reset_db()
            st.session_state.clear()
            st.success("Database reset. Reloading...")
            st.rerun()

    # ─── HELP ───────────────────────────────────────────────
    st.subheader("❓ How-to & Guidelines")
    st.markdown(
        """
**Quick Guide:**

1. **Event Periods**: Define seasonal periods (festive, off-season, etc.) with demand multipliers
   - Default: 1.5x during event periods
   - Toggle on/off as seasons change

2. **Daily Operations**:
   - Log worker hours & pieces made at day-end
   - Record kurti production with cloth consumption
   - Enter meshop sales data daily
   - System auto-calculates salaries & inventory

3. **Inventory Management**:
   - System tracks cloth consumption automatically
   - Low stock alerts trigger 3 days in advance
   - Adjust stock manually if needed

4. **Payments**:
   - Worker salaries: (hours × rate) + (pieces × piece_rate)
   - Vendor payments tracked per order
   - Payment history maintained for audit

5. **Reports**:
   - Daily summaries auto-generated
   - Weekly analytics with charts
   - Profit & loss analysis
   - Export to CSV
"""
    )