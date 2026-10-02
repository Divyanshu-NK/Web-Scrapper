"""Sales & Meshop Integration — record sales, Meesho supplier dashboard inputs, payout tracking."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import query, execute, get_conn, get_param, save_meesho_entry, get_meesho_entries


def show_sales(multiplier=1.5):
    st.title("💰 Sales & Meesho Integration")

    # ─── MEESHO SUPPLIER DASHBOARD INPUT ──────────────────────
    st.subheader("🛍️ Meesho Supplier Dashboard Input Logger")
    st.caption("Directly record Meesho sales dashboard reports to track receivables and payout dates")

    with st.form("meesho_input_form"):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            meesho_date = st.date_input("Report Date", value=datetime.now())
            orders_cnt = st.number_input("Total Orders Count", min_value=1, value=10, step=1)
            sold_qty = st.number_input("Sold Quantity (Pieces)", min_value=1, value=10, step=1)
        with col_m2:
            gross_amount = st.number_input("Gross Sales Amount (₹)", min_value=0.0, value=5000.0, step=100.0)
            commission_fee = st.number_input("Meesho Commission & Fees (₹)", min_value=0.0, value=750.0, step=50.0)

        # Auto-compute net receivable
        net_receivable = max(0.0, gross_amount - commission_fee)

        # Auto-compute payout date based on cycle
        cycle_days = int(get_param("meesho_payout_cycle_days", "15"))
        default_payout = meesho_date + timedelta(days=cycle_days)

        col_m3, col_m4 = st.columns(2)
        with col_m3:
            expected_payout_date = st.date_input("Expected Payout Release Date", value=default_payout)
        with col_m4:
            st.info(f"Net Receivable: **₹{net_receivable:,.2f}** (Payout in {cycle_days} days)")

        meesho_notes = st.text_input("Notes / Order Ref IDs (optional)", placeholder="e.g. Order batch #1042")

        if st.form_submit_button("🚀 Log Meesho Dashboard Entry", type="primary"):
            save_meesho_entry(
                date=meesho_date.strftime("%Y-%m-%d"),
                orders_count=orders_cnt,
                sold_qty=sold_qty,
                gross_sales_amount=gross_amount,
                meesho_commission_fees=commission_fee,
                net_receivable_amount=net_receivable,
                expected_payout_date=expected_payout_date.strftime("%Y-%m-%d"),
                payout_status="Pending",
                notes=meesho_notes,
            )
            st.success(f"✅ Logged Meesho Entry: {sold_qty} pcs | Net Receivable: ₹{net_receivable:,.2f} on {expected_payout_date}")
            st.rerun()

    # ─── MEESHO RECEIVABLES LEDGER ────────────────────────────
    meesho_entries = get_meesho_entries()
    if meesho_entries:
        st.write("#### 📑 Meesho Sales & Receivables Ledger")

        table_data = []
        for m in meesho_entries:
            table_data.append(
                {
                    "ID": m["id"],
                    "Date": m["date"],
                    "Orders": m["orders_count"],
                    "Sold Qty": m["sold_qty"],
                    "Gross (₹)": f"₹{m['gross_sales_amount']:,.2f}",
                    "Fees (₹)": f"₹{m['meesho_commission_fees']:,.2f}",
                    "Net Receivable (₹)": f"₹{m['net_receivable_amount']:,.2f}",
                    "Payout Date": m["expected_payout_date"],
                    "Status": m["payout_status"],
                }
            )

        df_m = pd.DataFrame(table_data)
        st.dataframe(df_m, hide_index=True, use_container_width=True)

        # Toggle Payout Status button for pending entries
        pending_entries = [m for m in meesho_entries if m["payout_status"] == "Pending"]
        if pending_entries:
            col_t1, col_t2 = st.columns([3, 1])
            with col_t1:
                sel_m_id = st.selectbox("Select Pending Payout to Mark Received", options=[m["id"] for m in pending_entries], format_func=lambda x: f"ID #{x} (Payout ₹{next(m['net_receivable_amount'] for m in pending_entries if m['id']==x):,.2f})")
            with col_t2:
                if st.button("✅ Mark Received"):
                    execute("UPDATE meesho_dashboard SET payout_status = 'Received' WHERE id = ?", (sel_m_id,))
                    st.success("✅ Payout status updated to Received!")
                    st.rerun()

    st.divider()

    # ─── ENTER REGULAR DAILY SALES ───────────────────────────
    st.subheader("➕ Enter Direct / Offline Sales")
    with st.form("sales_form"):
        designs = [r["design_name"] for r in query("SELECT DISTINCT design_name FROM kurti_production ORDER BY design_name")]

        col1, col2 = st.columns(2)
        with col1:
            design_name = st.selectbox("Kurti Design Sold", options=designs if designs else ["-- No designs yet --"])
        with col2:
            quantity_sold = st.number_input("Quantity Sold", min_value=1, value=1, step=1)

        col3, col4 = st.columns(2)
        with col3:
            price_per_unit = st.number_input("Price per Unit (₹)", min_value=0, value=500, step=10)
        with col4:
            total_revenue = quantity_sold * price_per_unit
            st.info(f"Total Revenue: ₹{total_revenue:,.2f}")

        meshop_ref = st.text_input("Order Reference ID (optional)")
        sale_date = st.date_input("Sale Date", value=datetime.now())

        submitted = st.form_submit_button("Record Direct Sale")

        if submitted and design_name and design_name != "-- No designs yet --":
            execute(
                "INSERT INTO sales (design_name, quantity_sold, price_per_unit, total_revenue, meshop_reference, date) VALUES (?, ?, ?, ?, ?, ?)",
                (design_name, quantity_sold, price_per_unit, total_revenue, meshop_ref, sale_date.strftime("%Y-%m-%d")),
            )
            st.success(f"✅ Sale recorded: {quantity_sold} × {design_name} @ ₹{price_per_unit}/unit = ₹{total_revenue:,.2f}")
            st.rerun()

    # ─── SALES SUMMARY ──────────────────────────────────────
    st.subheader("📊 Combined Sales Analytics")
    overall_sales = query("SELECT design_name, SUM(quantity_sold) as total_sold, SUM(total_revenue) as total_rev FROM sales GROUP BY design_name ORDER BY total_rev DESC")

    if overall_sales:
        df_overall = pd.DataFrame(overall_sales)
        st.dataframe(df_overall, hide_index=True, use_container_width=True)

        fig_s = px.bar(df_overall, x="design_name", y="total_rev", title="Revenue by Kurti Design", color_discrete_sequence=["#e74c3c"])
        st.plotly_chart(fig_s, use_container_width=True)