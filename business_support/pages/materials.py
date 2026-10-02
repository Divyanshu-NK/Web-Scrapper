"""Materials Management — add, edit, record usage."""

import streamlit as st
from datetime import datetime
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import query, execute


def show_materials(multiplier=1.5):
    st.header("🧵 Materials")

    # ── Add Material ──
    with st.expander("➕ Add New Material", expanded=False):
        with st.form("add_mat"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name", placeholder="e.g. Cotton White")
                mat_type = st.selectbox("Type", ["Cotton", "Silk", "Printed", "Linen", "Polyester", "Georgette", "Chiffon", "Rayon", "Other"])
            with c2:
                qty = st.number_input("Quantity", min_value=0.0, value=100.0, step=1.0)
                unit = st.selectbox("Unit", ["meters", "kg", "pieces", "yards"])
            c3, c4 = st.columns(2)
            with c3:
                supplier = st.text_input("Supplier", placeholder="e.g. Surat Fabrics")
            with c4:
                cost = st.number_input("Cost/Unit (₹)", min_value=0.0, value=50.0, step=1.0)

            if st.form_submit_button("Add Material") and name:
                execute("INSERT INTO materials (name,type,quantity,unit,supplier,cost_per_unit) VALUES (?,?,?,?,?,?)",
                        (name, mat_type, qty, unit, supplier, cost))
                st.success(f"✅ {name} added!")
                st.rerun()

    # ── Current Stock ──
    materials = query("SELECT * FROM materials ORDER BY name")
    if materials:
        import pandas as pd
        df = pd.DataFrame([{
            "Name": m["name"], "Type": m["type"] or "—",
            "Stock": f"{m['quantity']:.0f} {m['unit']}",
            "Cost/Unit": f"₹{m['cost_per_unit']:.0f}" if m["cost_per_unit"] else "—",
            "Supplier": m["supplier"] or "—",
        } for m in materials])
        st.dataframe(df, hide_index=True, use_container_width=True)

        # Stock chart
        import plotly.express as px
        chart_df = pd.DataFrame({"Material": [m["name"] for m in materials], "Stock": [m["quantity"] for m in materials]})
        fig = px.bar(chart_df, x="Material", y="Stock", color_discrete_sequence=["#3498db"])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=250, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No materials yet — add your first material above.")

    # ── Record Usage ──
    if materials:
        st.subheader("✂️ Record Cloth Usage")
        with st.form("usage_form"):
            mat_map = {m["name"]: m["id"] for m in materials}
            c1, c2 = st.columns(2)
            with c1:
                sel = st.selectbox("Material", list(mat_map.keys()))
            with c2:
                qty_used = st.number_input("Qty Used", min_value=0.1, value=2.5, step=0.1)

            if st.form_submit_button("Record Usage"):
                mid = mat_map[sel]
                execute("INSERT INTO cloth_usage (material_id, quantity_used, date) VALUES (?,?,?)",
                        (mid, qty_used, datetime.now().strftime("%Y-%m-%d")))
                cur = query("SELECT quantity FROM materials WHERE id=?", (mid,), fetchone=True)
                new_stock = max(cur.get("quantity", 0) - qty_used, 0)
                execute("UPDATE materials SET quantity=? WHERE id=?", (new_stock, mid))
                st.success(f"✅ Recorded {qty_used} used from {sel}")
                st.rerun()

    # ── Usage History ──
    usage = query("""SELECT cu.date, m.name, cu.quantity_used FROM cloth_usage cu
                     LEFT JOIN materials m ON cu.material_id=m.id ORDER BY cu.date DESC LIMIT 20""")
    if usage:
        st.subheader("📊 Recent Usage")
        import pandas as pd
        st.dataframe(pd.DataFrame([{"Date": u["date"], "Material": u["name"] or "?", "Used": u["quantity_used"]} for u in usage]),
                     hide_index=True, use_container_width=True)

    # ── Edit/Delete ──
    if materials:
        with st.expander("✏️ Edit / Delete Material"):
            mat_map2 = {m["name"]: m for m in materials}
            chosen = st.selectbox("Select", list(mat_map2.keys()), key="edit_sel")
            m = mat_map2[chosen]
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑️ Delete", key=f"del_{m['id']}"):
                    execute("DELETE FROM materials WHERE id=?", (m["id"],))
                    st.rerun()
            with c2:
                new_qty = st.number_input("Adjust Stock", value=float(m["quantity"]), step=1.0, key=f"adj_{m['id']}")
                if st.button("💾 Update", key=f"upd_{m['id']}"):
                    execute("UPDATE materials SET quantity=? WHERE id=?", (new_qty, m["id"]))
                    st.success("Updated!")
                    st.rerun()
