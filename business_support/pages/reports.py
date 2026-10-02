"""Reports & Analytics — daily/weekly summaries, P&L, KPIs, CSV export."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_conn


def show_reports(multiplier=1.5):
    st.title("📈 Reports & Analytics")

    # ─── DAILY SUMMARY ──────────────────────────────────────
    st.subheader("📅 Daily Business Summary")

    report_date = st.date_input("Select Date for Report", value=datetime.now())
    report_str = report_date.strftime("%Y-%m-%d")

    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT COALESCE(SUM(quantity_made), 0) as made, COALESCE(SUM(revenue), 0) as rev, COALESCE(SUM(cloth_used), 0) as cloth "
        "FROM kurti_production WHERE date = ?",
        (report_str,),
    )
    prod_today = c.fetchone()

    c.execute(
        "SELECT COALESCE(SUM(quantity_sold), 0) as sold, COALESCE(SUM(total_revenue), 0) as rev FROM sales WHERE date = ?",
        (report_str,),
    )
    sales_today = c.fetchone()

    c.execute(
        "SELECT COUNT(*) as workers, COALESCE(SUM(hours_worked), 0) as hours, "
        "COALESCE(SUM(pieces_made), 0) as pieces, COALESCE(SUM(daily_salary), 0) as salary "
        "FROM workers"
    )
    workers_today = c.fetchone()

    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Kurtis Produced", prod_today["made"])
    with col2:
        st.metric("Revenue Generated (₹)", f"₹{prod_today['rev']:,.2f}")
    with col3:
        st.metric("Cloth Consumed (m)", f"{prod_today['cloth']:.1f}")
    with col4:
        st.metric("Workers Active", workers_today["workers"])

    col5, col6, col7 = st.columns(3)
    with col5:
        st.metric("Sales Quantity", sales_today["sold"])
    with col6:
        st.metric("Sales Revenue (₹)", f"₹{sales_today['rev']:,.2f}")
    with col7:
        st.metric("Worker Salaries (₹)", f"₹{workers_today['salary']:,.2f}")

    # ─── WEEKLY ANALYTICS ──────────────────────────────────
    st.subheader("📊 Weekly Analytics")

    conn = get_conn()
    c = conn.cursor()

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    c.execute(
        "SELECT date, SUM(quantity_made) as made, SUM(revenue) as rev, SUM(cloth_used) as cloth "
        "FROM kurti_production WHERE date >= ? GROUP BY date ORDER BY date",
        (week_ago,),
    )
    weekly_prod = c.fetchall()

    c.execute(
        "SELECT date, SUM(quantity_sold) as sold, SUM(total_revenue) as rev "
        "FROM sales WHERE date >= ? GROUP BY date ORDER BY date",
        (week_ago,),
    )
    weekly_sales = c.fetchall()

    conn.close()

    st.write("**Weekly Production:**")
    if weekly_prod:
        fig_prod = go.Figure()
        fig_prod.add_trace(
            go.Bar(x=[p["date"] for p in weekly_prod], y=[p["made"] for p in weekly_prod], name="Kurtis Made", marker_color="#3498db")
        )
        fig_prod.add_trace(
            go.Bar(x=[p["date"] for p in weekly_prod], y=[p["rev"] for p in weekly_prod], name="Revenue (₹)", marker_color="#2ecc71")
        )
        fig_prod.update_layout(barmode="group", title="Weekly Production & Revenue")
        st.plotly_chart(fig_prod, use_container_width=True)
    else:
        st.info("No weekly production data")

    col_a, col_b = st.columns(2)
    with col_a:
        st.write("**Weekly Sales:**")
        if weekly_sales:
            fig_sales = go.Figure()
            fig_sales.add_trace(
                go.Bar(x=[s["date"] for s in weekly_sales], y=[s["rev"] for s in weekly_sales], name="Revenue (₹)", marker_color="#e74c3c")
            )
            fig_sales.update_layout(title="Weekly Sales Revenue")
            st.plotly_chart(fig_sales, use_container_width=True)
        else:
            st.info("No weekly sales data")

    with col_b:
        st.write("**Weekly Cloth Consumption:**")
        if weekly_prod:
            fig_cloth = go.Figure()
            fig_cloth.add_trace(
                go.Bar(x=[p["date"] for p in weekly_prod], y=[p["cloth"] for p in weekly_prod], name="Cloth (m)", marker_color="#f1c40f")
            )
            fig_cloth.update_layout(title="Weekly Cloth Usage")
            st.plotly_chart(fig_cloth, use_container_width=True)
        else:
            st.info("No cloth data")

    # ─── PROFIT & LOSS ──────────────────────────────────────
    st.subheader("💰 Profit & Loss Analysis")

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COALESCE(SUM(total_revenue), 0) FROM sales")
    total_revenue = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(revenue), 0) FROM kurti_production")
    prod_revenue = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(quantity * cost_per_unit), 0) FROM materials")
    material_cost = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'paid' AND type = 'worker'")
    worker_paid = c.fetchone()[0]

    gross_profit = total_revenue - material_cost - worker_paid
    profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

    conn.close()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Sales Revenue (₹)", f"₹{total_revenue:,.2f}")
    with col2:
        st.metric("Production Revenue (₹)", f"₹{prod_revenue:,.2f}")
    with col3:
        delta_color = "normal" if gross_profit >= 0 else "inverse"
        st.metric("Gross Profit (₹)", f"₹{gross_profit:,.2f}", f"{profit_margin:.1f}% margin")

    # ─── KPIs ───────────────────────────────────────────────
    st.subheader("🎯 Key Performance Indicators (KPIs)")

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COALESCE(SUM(revenue)/NULLIF(SUM(cloth_used),0), 0) as rev_per_meter FROM kurti_production")
    rev_per_meter = c.fetchone()["rev_per_meter"]

    c.execute("SELECT COALESCE(AVG(pieces_made), 0) as avg_pcs FROM workers")
    avg_pieces_worker = c.fetchone()["avg_pcs"]

    c.execute("SELECT COALESCE(AVG(hours_worked), 0) as avg_hrs FROM workers")
    avg_hours_worker = c.fetchone()["avg_hrs"]

    c.execute("SELECT COALESCE(AVG(wastage_percent), 0) as avg_wastage FROM kurti_production")
    avg_wastage = c.fetchone()["avg_wastage"]

    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Rev per Meter (₹)", f"₹{rev_per_meter:.2f}")
    with col2:
        st.metric("Avg Pieces/Worker", f"{avg_pieces_worker:.1f}")
    with col3:
        st.metric("Avg Hours/Worker", f"{avg_hours_worker:.1f}")
    with col4:
        st.metric("Avg Wastage %", f"{avg_wastage:.1f}%")

    # ─── EXPORT DATA ────────────────────────────────────────
    st.subheader("📤 Export Data")

    if st.button("📥 Generate Complete Report (CSV)"):
        conn = get_conn()

        prod_df = pd.read_sql_query("SELECT * FROM kurti_production", conn)
        sales_df = pd.read_sql_query("SELECT * FROM sales", conn)
        workers_df = pd.read_sql_query("SELECT * FROM workers", conn)
        materials_df = pd.read_sql_query("SELECT * FROM materials", conn)

        conn.close()

        csv_content = f"KURTI BUSINESS REPORT\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        csv_content += "=== PRODUCTION ===\n"
        csv_content += prod_df.to_csv(index=False) + "\n"

        csv_content += "=== SALES ===\n"
        csv_content += sales_df.to_csv(index=False) + "\n"

        csv_content += "=== WORKERS ===\n"
        csv_content += workers_df.to_csv(index=False) + "\n"

        csv_content += "=== MATERIALS ===\n"
        csv_content += materials_df.to_csv(index=False) + "\n"

        st.download_button(
            label="⬇️ Download CSV Report",
            data=csv_content,
            file_name=f"kurti_report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )