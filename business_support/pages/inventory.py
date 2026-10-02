"""Inventory & Stock Management — 30-day forecast, event prep factor, low-stock alerts, adjustments, usage history."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import query, execute, get_conn, get_active_event_multiplier, get_calendar_events


def show_inventory(multiplier=1.5):
    st.title("📦 Inventory & Stock Management")

    # ─── 30-DAY INVENTORY FORECAST ENGINE ─────────────────────
    st.subheader("📅 30-Day Stock & Depletion Forecast (Event Prep Factor Included)")
    st.caption("Takes into account calendar event prep windows (1.5x factor) to predict run-out dates")

    materials = query("SELECT id, name, quantity, unit, cost_per_unit FROM materials")

    if materials:
        # Get base daily consumption per material over last 7 days
        recent_usage = query(
            "SELECT material_id, COALESCE(SUM(quantity_used), 0) as total_used FROM cloth_usage WHERE date >= date('now', '-7 days') GROUP BY material_id"
        )
        usage_map = {r["material_id"]: r["total_used"] / 7.0 for r in recent_usage}

        # Fallback base consumption if no history exists (e.g. 5m/day)
        total_prod = query("SELECT COUNT(*) as cnt FROM kurti_production", fetchone=True).get("cnt", 0)
        default_daily_base = 5.0 if total_prod > 0 else 3.0

        forecast_rows = []
        depletion_dates = {}
        today = datetime.now().date()

        # Build 30-day daily projection chart data
        daily_projection = []

        for day_offset in range(30):
            current_day = today + timedelta(days=day_offset)
            day_str = current_day.strftime("%Y-%m-%d")
            day_mult = get_active_event_multiplier(day_str)

            row_data = {"Date": day_str, "Multiplier": f"{day_mult}x"}
            for mat in materials:
                m_id = mat["id"]
                m_name = mat["name"]
                base_used = usage_map.get(m_id, default_daily_base)
                day_usage = base_used * day_mult
                row_data[f"{m_name}_usage"] = day_usage
            daily_projection.append(row_data)

        # Compute stock depletion date for each material
        for mat in materials:
            m_id = mat["id"]
            m_name = mat["name"]
            current_stock = float(mat["quantity"])
            unit = mat["unit"]
            accumulated_usage = 0.0
            runout_date = None
            runout_in_prep_window = False

            for day_offset in range(30):
                current_day = today + timedelta(days=day_offset)
                day_str = current_day.strftime("%Y-%m-%d")
                day_mult = get_active_event_multiplier(day_str)
                base_used = usage_map.get(m_id, default_daily_base)
                daily_used = base_used * day_mult
                accumulated_usage += daily_used

                if accumulated_usage >= current_stock and runout_date is None:
                    runout_date = current_day
                    if day_mult > 1.0:
                        runout_in_prep_window = True

            days_left = (runout_date - today).days if runout_date else "> 30 days"
            status = "🚨 Critical (< 3 days)" if (isinstance(days_left, int) and days_left <= 3) else ("⚠️ Warning (< 7 days)" if (isinstance(days_left, int) and days_left <= 7) else "✅ Safe")

            forecast_rows.append(
                {
                    "Material": m_name,
                    "Current Stock": f"{current_stock:.1f} {unit}",
                    "Est. 30-Day Need": f"{accumulated_usage:.1f} {unit}",
                    "Run-Out Date": runout_date.strftime("%Y-%m-%d") if runout_date else "> 30 Days",
                    "Days Left": days_left,
                    "Status": status,
                    "During Event Prep?": "⚠️ YES (1.5x Demand)" if runout_in_prep_window else "No",
                }
            )

        df_forecast = pd.DataFrame(forecast_rows)
        st.dataframe(df_forecast, hide_index=True, use_container_width=True)

        # Plot 30-day cumulative consumption forecast curve
        fig_fore = go.Figure()
        days_x = [today + timedelta(days=i) for i in range(30)]
        for mat in materials:
            m_id = mat["id"]
            m_name = mat["name"]
            c_stock = float(mat["quantity"])
            cum_vals = []
            running_stock = c_stock
            base_used = usage_map.get(m_id, default_daily_base)
            for i in range(30):
                d_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
                mult = get_active_event_multiplier(d_str)
                running_stock = max(0, running_stock - (base_used * mult))
                cum_vals.append(running_stock)

            fig_fore.add_trace(go.Scatter(x=days_x, y=cum_vals, mode="lines+markers", name=f"{m_name} (Stock)"))

        fig_fore.update_layout(
            title="📉 Projected Stock Depletion Over Next 30 Days",
            xaxis_title="Date",
            yaxis_title="Projected Remaining Stock",
            template="plotly_dark",
            height=350,
        )
        st.plotly_chart(fig_fore, use_container_width=True)
    else:
        st.info("No materials available for forecasting.")

    st.divider()

    # ─── CURRENT INVENTORY ──────────────────────────────────
    st.subheader("📋 Current Material Inventory")
    inv_data = query("SELECT id, name, quantity, unit, cost_per_unit, supplier FROM materials ORDER BY name")

    if inv_data:
        df_inv = pd.DataFrame(
            [
                {
                    "Name": i["name"],
                    "Stock": f"{i['quantity']:.1f} {i['unit']}",
                    "Unit": i["unit"],
                    "Cost/Unit": f"₹{i['cost_per_unit']:.2f}" if i["cost_per_unit"] else "—",
                    "Supplier": i["supplier"] or "—",
                }
                for i in inv_data
            ]
        )
        st.dataframe(df_inv, hide_index=True, use_container_width=True)
    else:
        st.info("No materials in inventory yet.")

    # ─── INVENTORY ADJUSTMENT ───────────────────────────────
    st.subheader("✏️ Inventory Adjustment")
    adj_materials = query("SELECT id, name, quantity, unit FROM materials")

    if adj_materials:
        with st.form("inventory_adjustment_form"):
            mat_map = {m["name"]: m for m in adj_materials}
            selected_mat = st.selectbox("Material", options=list(mat_map.keys()))
            mat_row = mat_map[selected_mat]

            st.caption(f"Current stock: **{mat_row['quantity']:.1f} {mat_row['unit']}**")
            adjustment = st.number_input("Adjustment (+ to add, − to remove)", value=0.0, step=0.1)
            reason = st.text_input("Reason", placeholder="e.g., wastage, damage, counting error")

            if st.form_submit_button("Apply Adjustment"):
                new_stock = max(mat_row["quantity"] + adjustment, 0)
                execute("UPDATE materials SET quantity = ? WHERE id = ?", (new_stock, mat_row["id"]))
                st.success(f"✅ Stock adjusted! {selected_mat}: {mat_row['quantity']:.1f} → {new_stock:.1f} {mat_row['unit']}")
                st.rerun()