import streamlit as st
import os
import sys
from datetime import datetime, timedelta

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from database import (
    init_db, get_user, get_event_periods, save_event_period,
    delete_event_period, update_event_period, calculate_demand_multiplier,
    execute, query, get_param, set_param,
)

# ─── PAGE CONFIG (must be first st call) ────────────────────
st.set_page_config(page_title="Kurti Manufacturing Pro", page_icon="🧵", layout="wide")

# ─── CUSTOM CSS ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Base */
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* Hide Streamlit extras */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Top bar gradient */
.main .block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 1400px; }

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] {
    background: linear-gradient(135deg, #1a1f3a 0%, #0f1225 100%);
    border-radius: 16px;
    padding: 6px;
    gap: 4px;
    border: 1px solid rgba(255,255,255,0.06);
    overflow-x: auto;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 12px;
    padding: 8px 16px;
    font-weight: 500;
    font-size: 13px;
    color: #8892b0;
    background: transparent;
    border: none;
    white-space: nowrap;
    transition: all 0.2s ease;
}
.stTabs [data-baseweb="tab"]:hover { color: #ccd6f6; background: rgba(255,255,255,0.04); }
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%) !important;
    color: #fff !important;
    font-weight: 600;
    box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* Metric cards */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(26,31,58,0.8) 0%, rgba(15,18,37,0.9) 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 20px 16px 16px 16px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    backdrop-filter: blur(10px);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.3);
    border-color: rgba(231, 76, 60, 0.3);
}
[data-testid="stMetric"] label { font-size: 12px !important; color: #8892b0 !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: 0.5px; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 28px !important; font-weight: 700 !important; color: #e6f1ff !important; }
[data-testid="stMetric"] [data-testid="stMetricDelta"] { font-size: 11px !important; }

/* Forms */
[data-testid="stForm"] {
    background: linear-gradient(135deg, rgba(26,31,58,0.6) 0%, rgba(15,18,37,0.7) 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}

/* Buttons */
.stButton > button {
    border-radius: 10px;
    font-weight: 600;
    font-size: 13px;
    padding: 8px 20px;
    border: 1px solid rgba(255,255,255,0.1);
    transition: all 0.2s ease;
}
.stButton > button[kind="primary"], .stButton > button[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #e74c3c, #c0392b) !important;
    color: white !important;
    border: none;
    box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(0,0,0,0.2); }

/* Dataframes */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.06);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] .block-container { padding-top: 2rem; }

/* Expanders */
[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    background: rgba(26,31,58,0.3);
}

/* Section headers */
h1 { font-size: 32px !important; font-weight: 700 !important; background: linear-gradient(135deg, #e6f1ff, #8892b0); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
h2 { font-size: 20px !important; font-weight: 600 !important; color: #ccd6f6 !important; }
h3 { font-size: 16px !important; font-weight: 600 !important; color: #a8b2d1 !important; }

/* Alerts */
[data-testid="stAlert"] { border-radius: 12px; }

/* Selectbox / inputs */
[data-testid="stSelectbox"], [data-testid="stNumberInput"], [data-testid="stTextInput"] {
    border-radius: 10px;
}

/* Dividers */
hr { border-color: rgba(255,255,255,0.06) !important; }

/* Welcome banner for setup */
.welcome-banner {
    text-align: center;
    padding: 40px 20px;
    background: linear-gradient(135deg, rgba(231,76,60,0.1) 0%, rgba(26,31,58,0.5) 100%);
    border-radius: 20px;
    border: 1px solid rgba(231,76,60,0.15);
    margin-bottom: 24px;
}
.welcome-banner h1 { font-size: 42px !important; margin-bottom: 8px; }
.welcome-banner p { color: #8892b0; font-size: 16px; }

/* Quick stat pill */
.stat-pill {
    display: inline-block;
    background: rgba(231,76,60,0.15);
    color: #e74c3c;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    margin: 2px;
}
</style>
""", unsafe_allow_html=True)

# ─── INIT DB ───────────────────────────────────────────────
init_db()

# ─── CHECK SETUP ───────────────────────────────────────────
user = get_user()
if not user or not user.get("setup_completed"):
    # ─── FIRST-TIME QUESTIONNAIRE ──────────────────────────
    st.markdown("""
    <div class="welcome-banner">
        <h1>🧵 Kurti Manufacturing Pro</h1>
        <p>Let's set up your business in under a minute</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("setup_form"):
        st.subheader("👤 Step 1 — Who are you?")
        name = st.text_input("Your Name", placeholder="e.g. Saheli", help="Just your name — no password needed!")

        st.subheader("👥 Step 2 — Your Team")
        col1, col2 = st.columns(2)
        with col1:
            num_workers = st.number_input("How many workers?", min_value=0, max_value=50, value=3)
        with col2:
            hourly_rate = st.number_input("Default hourly rate (₹)", min_value=10, max_value=500, value=50, step=5)

        st.subheader("🧵 Step 3 — Production Basics")
        col3, col4 = st.columns(2)
        with col3:
            cloth_per_kurti = st.number_input("Cloth per kurti (meters)", min_value=0.5, max_value=10.0, value=2.5, step=0.1)
        with col4:
            piece_rate = st.number_input("Piece rate per kurti (₹)", min_value=5, max_value=200, value=20, step=5)

        wastage = st.slider("Typical wastage %", 0, 30, 5)

        st.subheader("📦 Step 4 — What materials do you stock?")
        material_choices = st.multiselect(
            "Select materials",
            ["Cotton", "Silk", "Printed Cotton", "Linen", "Polyester", "Georgette", "Chiffon", "Rayon"],
            default=["Cotton", "Printed Cotton"],
        )

        st.subheader("📅 Step 5 — Current Season")
        col5, col6 = st.columns(2)
        with col5:
            is_festive = st.selectbox("Are you in a festive/high-demand period?", ["No — Normal Season", "Yes — Festive Season"])
        with col6:
            demand_mult = st.slider("Demand multiplier", 1.0, 3.0, 1.5 if "No" in is_festive else 2.0, 0.1)

        submitted = st.form_submit_button("🚀 Start Managing!", type="primary")

        if submitted and name:
            # Save user
            execute(
                "INSERT OR REPLACE INTO users (id, username, name, setup_completed) VALUES (1, ?, ?, 1)",
                (name.lower().replace(" ", "_"), name),
            )

            # Save business params
            for k, v in {
                "cloth_per_kurti": str(cloth_per_kurti),
                "piece_rate": str(piece_rate),
                "hourly_rate_default": str(hourly_rate),
                "wastage_default": str(wastage),
                "low_stock_threshold": "3",
            }.items():
                set_param(k, v)

            # Create workers
            for i in range(1, num_workers + 1):
                execute(
                    "INSERT INTO workers (name, hourly_rate, date) VALUES (?, ?, ?)",
                    (f"Worker {i}", hourly_rate, datetime.now().strftime("%Y-%m-%d")),
                )

            # Create materials
            for mat in material_choices:
                execute(
                    "INSERT INTO materials (name, type, quantity, unit, cost_per_unit) VALUES (?, ?, ?, ?, ?)",
                    (mat, mat, 100, "meters", 50),
                )

            # Create event period
            period_name = "Festival Season" if "Yes" in is_festive else "Normal Season"
            save_event_period(
                period_name,
                datetime.now().strftime("%Y-%m-%d"),
                (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                demand_mult,
            )

            st.rerun()

    st.stop()


# ─── MAIN APP (post-setup) ─────────────────────────────────
multiplier = calculate_demand_multiplier()

# ─── SIDEBAR (minimal — just user info + event management) ─
st.sidebar.markdown(f"### 👋 {user['name']}")

active_periods = [p for p in get_event_periods() if p["is_active"]]
if active_periods:
    ep = active_periods[0]
    st.sidebar.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(231,76,60,0.12), rgba(26,31,58,0.4)); border-radius: 12px; padding: 12px 16px; border: 1px solid rgba(231,76,60,0.15); margin-bottom: 12px;">
        <div style="font-size: 12px; color: #8892b0; text-transform: uppercase; letter-spacing: 0.5px;">Current Period</div>
        <div style="font-size: 16px; font-weight: 600; color: #e6f1ff; margin: 4px 0;">{ep['period_name']}</div>
        <div style="font-size: 24px; font-weight: 700; color: #e74c3c;">{ep['demand_multiplier']}x</div>
        <div style="font-size: 11px; color: #8892b0;">{ep['start_date']} → {ep['end_date']}</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.info(f"Demand: **{multiplier}x**")

with st.sidebar.expander("📅 Manage Event Periods"):
    periods = get_event_periods()
    for ep in periods:
        c1, c2 = st.columns([3, 1])
        with c1:
            active = "✅" if ep["is_active"] else "❌"
            st.caption(f"{active} **{ep['period_name']}** ({ep['demand_multiplier']}x)")
        with c2:
            if st.button("🔄", key=f"t_{ep['id']}"):
                update_event_period(ep["id"], ep["period_name"], ep["start_date"], ep["end_date"], ep["demand_multiplier"], 0 if ep["is_active"] else 1)
                st.rerun()

    with st.form("sb_add_period"):
        pn = st.text_input("Name", placeholder="e.g. Diwali Rush")
        pm = st.slider("Multiplier", 1.0, 3.0, 1.5, 0.1, key="sb_mult")
        if st.form_submit_button("Add") and pn:
            save_event_period(pn, datetime.now().strftime("%Y-%m-%d"), (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"), pm)
            st.rerun()

st.sidebar.divider()
st.sidebar.caption("🧵 Kurti Manufacturing Pro v2.0")
st.sidebar.caption(f"Port **8502** • Multiplier **{multiplier}x**")

# ─── MAIN CONTENT — TABS ──────────────────────────────────
tabs = st.tabs([
    "📊 Dashboard",
    "🧵 Materials",
    "👥 Workers",
    "🏭 Production",
    "💰 Sales",
    "📦 Inventory",
    "💳 Payments",
    "📈 Reports",
    "⚙️ Settings",
])

with tabs[0]:
    from pages.dashboard import show_dashboard
    show_dashboard(multiplier)

with tabs[1]:
    from pages.materials import show_materials
    show_materials(multiplier)

with tabs[2]:
    from pages.workers import show_workers
    show_workers(multiplier)

with tabs[3]:
    from pages.production import show_production
    show_production(multiplier)

with tabs[4]:
    from pages.sales import show_sales
    show_sales(multiplier)

with tabs[5]:
    from pages.inventory import show_inventory
    show_inventory(multiplier)

with tabs[6]:
    from pages.payments import show_payments
    show_payments(multiplier)

with tabs[7]:
    from pages.reports import show_reports
    show_reports(multiplier)

with tabs[8]:
    from pages.settings import show_settings
    show_settings(multiplier)