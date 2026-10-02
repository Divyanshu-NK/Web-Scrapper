"""Production tracking page — record kurtis, track cloth consumption and revenue."""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_conn


def show_production(multiplier=1.5):
    st.title("🏭 Kurti Production Tracker")

    # ─── RECORD PRODUCTION ──────────────────────────────────
    st.subheader("➕ Record New Production")
    with st.form("production_form"):
        conn = get_conn()
        c = conn.cursor()

        # Get available designs (from past production + common defaults)
        c.execute("SELECT DISTINCT design_name FROM kurti_production ORDER BY design_name")
        existing_designs = [r["design_name"] for r in c.fetchall()]
        default_designs = ["Anarkali", "A-line", "Straight", "Palazzo", "Shirt Style", "Asymmetric"]
        all_designs = list(dict.fromkeys(existing_designs + default_designs))  # unique, ordered

        c.execute("SELECT id, name FROM materials")
        materials = c.fetchall()
        mat_options = {m["name"]: m["id"] for m in materials}

        conn.close()

        col1, col2 = st.columns(2)
        with col1:
            design_name = st.selectbox("Kurti Design", options=all_designs)
            custom_design = st.text_input("Or enter new design name", placeholder="Custom design...")
            if custom_design:
                design_name = custom_design
        with col2:
            quantity_made = st.number_input("Quantity Made Today", min_value=1, value=1, step=1)

        col3, col4 = st.columns(2)
        with col3:
            mat_names_list = list(mat_options.keys()) if mat_options else ["None — add materials first"]
            selected_mat_name = st.selectbox("Material Used", options=mat_names_list)
            material_id = mat_options.get(selected_mat_name, None)
        with col4:
            cloth_used = st.number_input("Cloth Used per Piece (m)", min_value=0.0, value=2.5, step=0.1)
            wastage_percent = st.number_input("Wastage %", min_value=0.0, max_value=50.0, value=0.0, step=0.5)

        col5, col6 = st.columns(2)
        with col5:
            sale_price = st.number_input("Sale Price per Kurti (₹)", min_value=0, value=500, step=10)
        with col6:
            total_cloth = cloth_used * quantity_made
            revenue = quantity_made * sale_price
            st.info(f"Total cloth: {total_cloth:.1f}m | Revenue: ₹{revenue:,.2f}")

        submit = st.form_submit_button("Record Production")

        if submit:
            conn = get_conn()
            c = conn.cursor()

            # Record production
            c.execute(
                "INSERT INTO kurti_production (design_name, material_id, quantity_made, cloth_used, wastage_percent, sale_price, revenue, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (design_name, material_id, quantity_made, total_cloth, wastage_percent, sale_price, revenue, datetime.now().strftime("%Y-%m-%d")),
            )

            # Update material stock
            if material_id:
                c.execute("SELECT quantity FROM materials WHERE id = ?", (material_id,))
                mat = c.fetchone()
                if mat:
                    new_stock = max(mat["quantity"] - total_cloth, 0)
                    c.execute("UPDATE materials SET quantity = ? WHERE id = ?", (new_stock, material_id))

                # Record cloth usage
                c.execute(
                    "INSERT INTO cloth_usage (material_id, kurti_id, quantity_used, date) VALUES (?, ?, ?, ?)",
                    (material_id, 0, total_cloth, datetime.now().strftime("%Y-%m-%d")),
                )

            conn.commit()
            conn.close()
            st.success(
                f"✅ Recorded: {quantity_made} × {design_name} | "
                f"Cloth: {total_cloth:.1f}m | Revenue: ₹{revenue:,.2f}"
            )
            st.rerun()

    # ─── PRODUCTION SUMMARY ─────────────────────────────────
    st.subheader("📊 Production Summary")

    conn = get_conn()
    c = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    c.execute(
        "SELECT design_name, SUM(quantity_made) as cnt FROM kurti_production WHERE date = ? GROUP BY design_name",
        (today,),
    )
    today_production = c.fetchall()

    c.execute(
        "SELECT COALESCE(SUM(quantity_made), 0) as total_made, COALESCE(SUM(revenue), 0) as total_rev, COALESCE(SUM(cloth_used), 0) as total_cloth FROM kurti_production"
    )
    overall = c.fetchone()

    c.execute(
        "SELECT design_name, SUM(quantity_made) as count, SUM(revenue) as rev, SUM(cloth_used) as cloth FROM kurti_production GROUP BY design_name ORDER BY rev DESC"
    )
    by_design = c.fetchall()

    conn.close()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Kurtis Made (All Time)", overall["total_made"])
    with col2:
        st.metric("Total Revenue (₹)", f"₹{overall['total_rev']:,.2f}")
    with col3:
        st.metric("Total Cloth Used (m)", f"{overall['total_cloth']:.1f}")

    # By design
    if by_design:
        st.write("**Production by Design:**")
        for d in by_design:
            st.caption(f"**{d['design_name']}**: {d['count']} pieces, ₹{d['rev']:,.2f} revenue, {d['cloth']:.1f}m cloth")

    # Today
    st.write(f"**Today ({today}):**")
    if today_production:
        for p in today_production:
            st.caption(f"{p['design_name']}: {p['cnt']} pieces")
    else:
        st.caption("No production recorded today")

    # ─── DESIGN PERFORMANCE ANALYTICS ───────────────────────
    st.subheader("📈 Design Performance")

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT design_name, SUM(quantity_made) as made, SUM(revenue) as revenue, SUM(cloth_used) as cloth, AVG(sale_price) as avg_price "
        "FROM kurti_production GROUP BY design_name ORDER BY revenue DESC"
    )
    design_perf = c.fetchall()
    conn.close()

    if design_perf:
        perf_data = []
        for d in design_perf:
            perf_data.append(
                {
                    "Design": d["design_name"],
                    "Pieces Made": d["made"],
                    "Total Revenue (₹)": f"₹{d['revenue']:,.2f}",
                    "Cloth Used (m)": f"{d['cloth']:.1f}",
                    "Avg Price (₹)": f"₹{d['avg_price']:.0f}",
                }
            )

        df_perf = pd.DataFrame(perf_data)
        st.dataframe(df_perf, hide_index=True, use_container_width=True)

        # Revenue chart
        chart_df = pd.DataFrame(
            {"Design": [d["design_name"] for d in design_perf], "Revenue": [d["revenue"] for d in design_perf]}
        )
        fig = px.bar(chart_df, x="Design", y="Revenue", title="Revenue by Design", color_discrete_sequence=["#9b59b6"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No production data for analytics yet.")