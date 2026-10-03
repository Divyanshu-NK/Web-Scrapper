import os
import sys
import threading
import time
import streamlit as st
import pandas as pd
import requests
import html
import re
import json
import textwrap
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

# ─── Path Resolution & Self-Starting Backend for Cloud Deployment ───────────
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
for p in [root_dir, parent_dir, current_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

API_URL = "http://127.0.0.1:8000"

def ensure_backend_running():
    try:
        r = requests.get(f"{API_URL}/", timeout=1)
        if r.status_code == 200:
            return
    except Exception:
        pass
    
    def start_uvicorn():
        try:
            import uvicorn
            from backend.main import app as fastapi_app
            uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="warning", install_signal_handlers=False)
        except Exception as e:
            print(f"Backend start error: {e}")

    t = threading.Thread(target=start_uvicorn, daemon=True)
    t.start()
    time.sleep(2.5)

ensure_backend_running()

# ─── Page Configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Saheli Fashion Intelligence | Kurti Trend Radar",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Initialize Session State ────────────────────────────────────────────────
if "saved_product_ids" not in st.session_state:
    st.session_state.saved_product_ids = set()

if "theme" not in st.session_state:
    st.session_state.theme = "light"

# ─── Direct High-Performance Cached Database Access Engine ───────────────────
try:
    from backend.database import DatabaseManager
    db_manager = DatabaseManager()
except Exception:
    db_manager = None

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_trending_products(limit, min_rating, min_reviews, price_min, price_max, platforms_tuple, keyword):
    if not db_manager:
        return []
    plats = list(platforms_tuple) if platforms_tuple else None
    return db_manager.get_trending_products(
        limit=limit,
        min_rating=min_rating,
        min_reviews=min_reviews,
        price_min=price_min,
        price_max=price_max,
        platforms=plats,
        keyword=keyword
    )

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_products(limit, keyword):
    if not db_manager:
        return []
    return db_manager.get_all_products(limit=limit, keyword=keyword)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_time_demand(limit, keyword):
    if not db_manager:
        return []
    return db_manager.get_all_time_demand_products(limit=limit, keyword=keyword)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_product_details(product_id):
    if not db_manager:
        return {}
    sql_product = "SELECT * FROM products WHERE id = %s"
    prod_rows = db_manager.execute_query(sql_product, (product_id,))
    if not prod_rows:
        return {}
    product = prod_rows[0]
    if not db_manager.is_postgres and isinstance(product.get('attributes'), str):
        product['attributes'] = db_manager.deserialize_json(product['attributes'])
    history = db_manager.get_product_metrics_history(product_id, limit=90)
    sql_score = "SELECT * FROM trend_scores WHERE product_id = %s ORDER BY calculated_date DESC LIMIT 1"
    score_rows = db_manager.execute_query(sql_score, (product_id,))
    latest_score = score_rows[0] if score_rows else {}
    return {
        "product": product,
        "score": latest_score,
        "metrics_history": history
    }

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_attribute_trends(limit=100):
    if not db_manager:
        return []
    return db_manager.get_attribute_trends(limit=limit)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_sources():
    if not db_manager:
        return {}
    return db_manager.get_available_sources()

@st.cache_data(ttl=30, show_spinner=False)
def _cached_get_saved_products():
    if not db_manager:
        return []
    return db_manager.get_saved_products()

@st.cache_data(ttl=30, show_spinner=False)
def _cached_get_scraper_jobs(limit=20):
    if not db_manager:
        return []
    return db_manager.get_recent_scrape_jobs(limit=limit)

def api_get(endpoint: str, params: dict = None) -> list:
    if params is None:
        params = {}
    
    if db_manager:
        try:
            if endpoint == "/api/products":
                limit = params.get("limit", 32)
                min_rating = params.get("min_rating", 0.0)
                min_reviews = params.get("min_reviews", 0)
                price_min = params.get("price_min", 0.0)
                price_max = params.get("price_max", 99999.0)
                plats = params.get("platforms")
                plats_tuple = tuple(plats) if isinstance(plats, list) else (tuple(plats) if isinstance(plats, (set, tuple)) else None)
                keyword = params.get("keyword", "kurti")
                return _cached_get_trending_products(limit, min_rating, min_reviews, price_min, price_max, plats_tuple, keyword)
            
            elif endpoint == "/api/products/all":
                limit = params.get("limit", 200)
                keyword = params.get("keyword")
                return _cached_get_all_products(limit, keyword)
                
            elif endpoint == "/api/products/all-time-demand":
                limit = params.get("limit", 50)
                keyword = params.get("keyword", "kurti")
                return _cached_get_all_time_demand(limit, keyword)
                
            elif endpoint.startswith("/api/products/"):
                prod_id = endpoint.replace("/api/products/", "")
                return _cached_get_product_details(prod_id)
                
            elif endpoint == "/api/analytics/attributes":
                limit = params.get("limit", 100)
                return _cached_get_attribute_trends(limit)
                
            elif endpoint == "/api/sources":
                return _cached_get_sources()
                
            elif endpoint == "/api/saved-products":
                return _cached_get_saved_products()

            elif endpoint == "/api/scraper/jobs":
                limit = params.get("limit", 20)
                return _cached_get_scraper_jobs(limit)
        except Exception:
            pass

    try:
        r = requests.get(f"{API_URL}{endpoint}", params=params, timeout=5)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception:
        return []

def api_post(endpoint: str, params: dict = None) -> dict:
    st.cache_data.clear()
    if db_manager:
        try:
            if endpoint.startswith("/api/saved-products/"):
                prod_id = endpoint.replace("/api/saved-products/", "")
                db_manager.save_product(prod_id)
                return {"status": "saved", "product_id": prod_id}
            elif endpoint == "/api/sources":
                name = params.get("name") if params else None
                url = params.get("url") if params else None
                if name and url:
                    res = db_manager.add_custom_source(name, url)
                    return res
        except Exception:
            pass
    try:
        r = requests.post(f"{API_URL}{endpoint}", params=params, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def api_delete(endpoint: str) -> dict:
    st.cache_data.clear()
    if db_manager:
        try:
            if endpoint.startswith("/api/saved-products/"):
                prod_id = endpoint.replace("/api/saved-products/", "")
                db_manager.remove_saved_product(prod_id)
                return {"status": "removed", "product_id": prod_id}
            elif endpoint.startswith("/api/sources/"):
                brand_key = endpoint.replace("/api/sources/", "")
                res = db_manager.remove_custom_source(brand_key)
                return res
        except Exception:
            pass
    try:
        r = requests.delete(f"{API_URL}{endpoint}", timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

# Sync saved products from DB on initial load
if not st.session_state.saved_product_ids:
    db_saved = api_get("/api/saved-products")
    if db_saved:
        st.session_state.saved_product_ids = set(p['id'] for p in db_saved)

# ─── Helper: Clean & Validate Product Descriptions ───────────────────────────
def clean_product_description(raw_desc: str, title: str = "", attrs: dict = None) -> str:
    """
    Sanitizes raw descriptions: strips HTML tags, unescapes HTML entities,
    removes marketing boilerplate, and provides rich fallback attributes.
    """
    if attrs is None:
        attrs = {}
        
    desc = str(raw_desc or "")
    desc = html.unescape(desc)
    desc = re.sub(r'<[^>]+>', ' ', desc)
    desc = re.sub(r'[\r\n\t]+', ' ', desc)
    desc = re.sub(r'\s+', ' ', desc).strip()
    desc = re.sub(r'^(Our\s+|Introducing\s+(the\s+)?|Shop\s+this\s+|Buy\s+)', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'^(Flipkart\s+Kurti:\s*|Myntra\s+Kurti:\s*)', '', desc, flags=re.IGNORECASE)
    
    if len(desc) < 22 or desc.lower().startswith('official') or 'kurti' in desc.lower()[:15]:
        fabric = attrs.get('fabric') or 'Cotton'
        pattern = attrs.get('pattern') or 'Printed'
        neck = attrs.get('neckline') or 'Round Neck'
        sleeve = attrs.get('sleeve_type') or '3/4 Sleeve'
        desc = f"Tailored {pattern.lower()} silhouette in premium {fabric.lower()} featuring an elegant {neck.lower()} and {sleeve.lower()}."
    
    if desc:
        desc = desc[0].upper() + desc[1:]
        if len(desc) > 125:
            desc = desc[:122].rsplit(' ', 1)[0] + '...'
            
    return desc

# ─── Sidebar Header & Theme Toggle Switch ────────────────────────────────────
with st.sidebar:
    st.markdown("""
        <div style='padding: 4px 0 12px 0;'>
            <div style='font-size:0.72rem; font-weight:800; color:#4f46e5; letter-spacing:0.18em; text-transform:uppercase;'>Saheli Intelligence</div>
            <div style='font-size:1.25rem; font-weight:800; letter-spacing:-0.02em;'>Kurti Trend Radar</div>
        </div>
    """, unsafe_allow_html=True)

    # Clean Dual-Theme Mode Toggle
    theme_choice = st.radio(
        "Theme Appearance",
        options=["☀️ Light Theme", "🌙 Dark Theme"],
        index=0 if st.session_state.theme == "light" else 1,
        horizontal=True,
        key="theme_toggle_radio"
    )
    st.session_state.theme = "light" if "Light" in theme_choice else "dark"
    current_theme = st.session_state.theme

# ─── Dynamic High-Contrast Theme CSS Injection ───────────────────────────────
if current_theme == "light":
    # ☀️ LIGHT THEME CSS
    css_theme = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: #f8fafc;
            color: #0f172a;
        }
        .stApp {
            background-color: #f8fafc;
            color: #0f172a;
        }
        
        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #e2e8f0 !important;
        }
        [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {
            color: #1e293b !important;
            font-size: 0.85rem;
            font-weight: 700;
        }
        [data-testid="stSidebar"] .stTextInput input, [data-testid="stSidebar"] .stNumberInput input {
            background: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
            border-radius: 8px !important;
        }
        
        .brand-eyebrow {
            font-size: 0.76rem;
            font-weight: 800;
            color: #4f46e5;
            text-transform: uppercase;
            letter-spacing: 0.18em;
            margin-bottom: 4px;
        }
        .main-header {
            font-size: 2.35rem;
            font-weight: 800;
            color: #0f172a;
            margin: 0 0 6px 0;
            line-height: 1.15;
        }
        .sub-header {
            font-size: 0.92rem;
            color: #475569;
            margin-bottom: 24px;
            font-weight: 500;
        }

        /* KPI Cards */
        .kpi-card {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }
        .kpi-card-1 { border-top: 4px solid #4f46e5; }
        .kpi-card-2 { border-top: 4px solid #059669; }
        .kpi-card-3 { border-top: 4px solid #ea580c; }
        .kpi-card-4 { border-top: 4px solid #d97706; }
        .kpi-value {
            font-size: 2rem;
            font-weight: 800;
            color: #0f172a;
        }
        .kpi-label {
            font-size: 0.74rem;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            margin-top: 4px;
        }
        .kpi-delta { font-size: 0.76rem; font-weight: 700; margin-top: 4px; }
        .delta-indigo { color: #4338ca; }
        .delta-emerald { color: #047857; }
        .delta-orange { color: #c2410c; }
        .delta-amber { color: #b45309; }

        /* Product Cards */
        .product-card {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
            margin-bottom: 20px;
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        .product-img-wrapper {
            width: 100%;
            height: 240px;
            background: #f1f5f9;
            overflow: hidden;
        }
        .product-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: top center;
            display: block;
        }
        .product-body {
            padding: 16px;
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }
        .platform-badge {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
            background: #f1f5f9;
            color: #1e293b;
            border: 1px solid #cbd5e1;
        }
        .dir-badge {
            display: inline-flex;
            align-items: center;
            gap: 3px;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
        }
        .dir-rising  { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
        .dir-falling { background: #fff1f2; color: #be123c; border: 1px solid #fecdd3; }
        .dir-stable  { background: #f8fafc; color: #475569; border: 1px solid #cbd5e1; }
        .dir-new     { background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa; }

        .card-title {
            font-size: 0.94rem;
            font-weight: 700;
            color: #0f172a;
            margin: 10px 0 4px 0;
            height: 40px;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            line-height: 1.4;
        }
        .card-description {
            font-size: 0.78rem;
            color: #334155;
            line-height: 1.45;
            height: 36px;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            margin-bottom: 8px;
            font-weight: 500;
        }
        .price-row {
            display: flex;
            align-items: baseline;
            gap: 6px;
            margin: 6px 0 8px 0;
        }
        .price-main { font-size: 1.3rem; font-weight: 800; color: #0f172a; }
        .price-original { font-size: 0.85rem; text-decoration: line-through; color: #64748b; }
        .price-discount { font-size: 0.74rem; font-weight: 800; color: #047857; background: #ecfdf5; padding: 2px 6px; border-radius: 4px; border: 1px solid #a7f3d0; }
        
        .rating-row {
            font-size: 0.78rem;
            color: #1e293b;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 4px;
            margin-bottom: 8px;
        }
        .attr-row { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
        .attr-chip {
            display: inline-block;
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            color: #1e293b;
            font-size: 0.68rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
        }
        .trend-meter-bg {
            height: 6px;
            background: #e2e8f0;
            border-radius: 999px;
            margin: 8px 0 4px;
            overflow: hidden;
        }
        .trend-meter-fill {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #4f46e5, #059669);
        }
        .trend-footer {
            display: flex;
            justify-content: space-between;
            font-size: 0.72rem;
            color: #475569;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .trend-score-value { color: #4338ca; font-weight: 800; font-size: 0.82rem; }
        
        .product-link-btn {
            display: block;
            text-align: center;
            background: #eef2ff !important;
            border: 1px solid #c7d2fe !important;
            color: #4338ca !important;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.78rem;
            font-weight: 700;
            text-decoration: none !important;
            margin-top: 6px;
        }
        .product-link-btn:hover {
            background: #4f46e5 !important;
            color: #ffffff !important;
            border-color: #4f46e5 !important;
        }

        /* Buttons & Tabs */
        .stButton > button {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #94a3b8 !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            font-size: 0.82rem !important;
            padding: 6px 14px !important;
        }
        .stButton > button:hover {
            background-color: #4f46e5 !important;
            color: #ffffff !important;
            border-color: #4f46e5 !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            background: #ffffff;
            border-radius: 10px;
            padding: 6px;
            gap: 6px;
            border: 1px solid #cbd5e1;
        }
        .stTabs [data-baseweb="tab"] {
            background: #f8fafc !important;
            color: #334155 !important;
            border-radius: 8px;
            padding: 8px 18px;
            font-size: 0.84rem;
            font-weight: 700;
            border: 1px solid #e2e8f0 !important;
        }
        .stTabs [aria-selected="true"] {
            background: #4f46e5 !important;
            color: #ffffff !important;
            border-color: #4f46e5 !important;
        }

        .factor-breakdown-card {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 10px;
        }
        .factor-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.84rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 4px;
        }
        .factor-weight { font-size: 0.72rem; color: #4338ca; font-weight: 700; }
        .factor-desc { font-size: 0.76rem; color: #334155; line-height: 1.45; }
        .factor-score-val { font-size: 1.05rem; font-weight: 800; color: #047857; }

        .custom-source-badge {
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            color: #1d4ed8;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            display: inline-block;
        }
        
        .no-data-container {
            text-align: center;
            padding: 50px 20px;
            border: 2px dashed #94a3b8;
            border-radius: 14px;
            background: #ffffff;
            margin: 20px 0;
        }
        .no-data-title { font-size: 1.15rem; font-weight: 800; color: #0f172a; margin-bottom: 6px; }
        .no-data-subtitle { font-size: 0.88rem; color: #475569; max-width: 480px; margin: 0 auto; line-height: 1.5; font-weight: 500; }
        hr { border-color: #cbd5e1 !important; }
        </style>
    """
else:
    # 🌙 DARK THEME CSS
    css_theme = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: #090b10;
            color: #f8fafc;
        }
        .stApp {
            background: radial-gradient(circle at 15% 10%, #111520 0%, #090b10 70%);
            color: #f8fafc;
        }
        
        [data-testid="stSidebar"] {
            background-color: #0d111a !important;
            border-right: 1px solid #1f2738 !important;
        }
        [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {
            color: #e2e8f0 !important;
            font-size: 0.85rem;
            font-weight: 700;
        }
        [data-testid="stSidebar"] .stTextInput input, [data-testid="stSidebar"] .stNumberInput input {
            background: #151b28 !important;
            border: 1px solid #2d3748 !important;
            color: #f8fafc !important;
            border-radius: 8px !important;
        }
        
        .brand-eyebrow {
            font-size: 0.76rem;
            font-weight: 800;
            color: #d4af37;
            text-transform: uppercase;
            letter-spacing: 0.18em;
            margin-bottom: 4px;
        }
        .main-header {
            font-size: 2.35rem;
            font-weight: 800;
            color: #ffffff;
            margin: 0 0 6px 0;
            line-height: 1.15;
        }
        .sub-header {
            font-size: 0.92rem;
            color: #94a3b8;
            margin-bottom: 24px;
            font-weight: 500;
        }

        /* KPI Cards */
        .kpi-card {
            background: #121724;
            border: 1px solid #232d42;
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
        }
        .kpi-card-1 { border-top: 4px solid #6366f1; }
        .kpi-card-2 { border-top: 4px solid #10b981; }
        .kpi-card-3 { border-top: 4px solid #f97316; }
        .kpi-card-4 { border-top: 4px solid #d4af37; }
        .kpi-value {
            font-size: 2rem;
            font-weight: 800;
            color: #ffffff;
        }
        .kpi-label {
            font-size: 0.74rem;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            margin-top: 4px;
        }
        .kpi-delta { font-size: 0.76rem; font-weight: 700; margin-top: 4px; }
        .delta-indigo { color: #818cf8; }
        .delta-emerald { color: #34d399; }
        .delta-orange { color: #fb923c; }
        .delta-amber { color: #fbbf24; }

        /* Product Cards */
        .product-card {
            background: #111520;
            border: 1px solid #232d42;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
            margin-bottom: 20px;
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        .product-img-wrapper {
            width: 100%;
            height: 240px;
            background: #181f2f;
            overflow: hidden;
        }
        .product-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: top center;
            display: block;
        }
        .product-body {
            padding: 16px;
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }
        .platform-badge {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
            background: rgba(255,255,255,0.08);
            color: #f1f5f9;
            border: 1px solid rgba(255,255,255,0.15);
        }
        .dir-badge {
            display: inline-flex;
            align-items: center;
            gap: 3px;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
        }
        .dir-rising  { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }
        .dir-falling { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
        .dir-stable  { background: rgba(148,163,184,0.12); color: #94a3b8; border: 1px solid rgba(148,163,184,0.25); }
        .dir-new     { background: rgba(212,175,55,0.15); color: #fbbf24; border: 1px solid rgba(212,175,55,0.3); }

        .card-title {
            font-size: 0.94rem;
            font-weight: 700;
            color: #ffffff;
            margin: 10px 0 4px 0;
            height: 40px;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            line-height: 1.4;
        }
        .card-description {
            font-size: 0.78rem;
            color: #94a3b8;
            line-height: 1.45;
            height: 36px;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            margin-bottom: 8px;
            font-weight: 500;
        }
        .price-row {
            display: flex;
            align-items: baseline;
            gap: 6px;
            margin: 6px 0 8px 0;
        }
        .price-main { font-size: 1.3rem; font-weight: 800; color: #ffffff; }
        .price-original { font-size: 0.85rem; text-decoration: line-through; color: #64748b; }
        .price-discount { font-size: 0.74rem; font-weight: 800; color: #34d399; background: rgba(16,185,129,0.15); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(16,185,129,0.3); }
        
        .rating-row {
            font-size: 0.78rem;
            color: #cbd5e1;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 4px;
            margin-bottom: 8px;
        }
        .attr-row { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
        .attr-chip {
            display: inline-block;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.12);
            color: #e2e8f0;
            font-size: 0.68rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
        }
        .trend-meter-bg {
            height: 6px;
            background: rgba(255,255,255,0.08);
            border-radius: 999px;
            margin: 8px 0 4px;
            overflow: hidden;
        }
        .trend-meter-fill {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #d4af37, #10b981);
        }
        .trend-footer {
            display: flex;
            justify-content: space-between;
            font-size: 0.72rem;
            color: #94a3b8;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .trend-score-value { color: #d4af37; font-weight: 800; font-size: 0.82rem; }
        
        .product-link-btn {
            display: block;
            text-align: center;
            background: rgba(212, 175, 55, 0.12) !important;
            border: 1px solid rgba(212, 175, 55, 0.3) !important;
            color: #e5c378 !important;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.78rem;
            font-weight: 700;
            text-decoration: none !important;
            margin-top: 6px;
        }
        .product-link-btn:hover {
            background: #d4af37 !important;
            color: #07090d !important;
            border-color: #d4af37 !important;
        }

        /* Buttons & Tabs */
        .stButton > button {
            background-color: #1e2433 !important;
            color: #f8fafc !important;
            border: 1px solid #3b465e !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            font-size: 0.82rem !important;
            padding: 6px 14px !important;
        }
        .stButton > button:hover {
            background-color: #d4af37 !important;
            color: #07090d !important;
            border-color: #d4af37 !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            background: #111520;
            border-radius: 10px;
            padding: 6px;
            gap: 6px;
            border: 1px solid #232d42;
        }
        .stTabs [data-baseweb="tab"] {
            background: #151b28 !important;
            color: #94a3b8 !important;
            border-radius: 8px;
            padding: 8px 18px;
            font-size: 0.84rem;
            font-weight: 700;
            border: 1px solid #232d42 !important;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(212,175,55,0.18) !important;
            color: #fbbf24 !important;
            border: 1px solid rgba(212,175,55,0.4) !important;
        }

        .factor-breakdown-card {
            background: #141a27;
            border: 1px solid #232d42;
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 10px;
        }
        .factor-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.84rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 4px;
        }
        .factor-weight { font-size: 0.72rem; color: #d4af37; font-weight: 700; }
        .factor-desc { font-size: 0.76rem; color: #94a3b8; line-height: 1.45; }
        .factor-score-val { font-size: 1.05rem; font-weight: 800; color: #34d399; }

        .custom-source-badge {
            background: rgba(59,130,246,0.15);
            border: 1px solid rgba(59,130,246,0.3);
            color: #60a5fa;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            display: inline-block;
        }
        
        .no-data-container {
            text-align: center;
            padding: 50px 20px;
            border: 2px dashed #3b465e;
            border-radius: 14px;
            background: #111520;
            margin: 20px 0;
        }
        .no-data-title { font-size: 1.15rem; font-weight: 800; color: #ffffff; margin-bottom: 6px; }
        .no-data-subtitle { font-size: 0.88rem; color: #94a3b8; max-width: 480px; margin: 0 auto; line-height: 1.5; font-weight: 500; }
        hr { border-color: #232d42 !important; }
        </style>
    """

st.markdown(textwrap.dedent(css_theme), unsafe_allow_html=True)

# ─── No Data Helper ──────────────────────────────────────────────────────────
def render_no_data(icon: str, title: str, subtitle: str):
    html_out = textwrap.dedent(f"""
        <div class='no-data-container'>
            <div style='font-size:2.2rem; margin-bottom:10px;'>{icon}</div>
            <div class='no-data-title'>{title}</div>
            <div class='no-data-subtitle'>{subtitle}</div>
        </div>
    """)
    st.markdown(html_out, unsafe_allow_html=True)

# ─── Modal Dialog: Comprehensive Product Factor Inspector ────────────────────
@st.dialog("Product Factor Breakdown & Audit", width="large")
def show_product_inspector_dialog(prod_id: str):
    details = api_get(f"/api/products/{prod_id}")
    if not details:
        st.error("Could not retrieve product metrics.")
        return
    
    p = details.get('product', {})
    score = details.get('score', {})
    history = details.get('metrics_history', [])
    attrs = p.get('attributes', {})
    
    brand = p.get('brand') or 'Ethnic Brand'
    title = p.get('title') or 'Kurti'
    price = float(p.get('price') or 0.0)
    orig_price = float(p.get('original_price') or price)
    
    # Calculate real discount percentage
    raw_discount = float(p.get('discount_percentage') or 0.0)
    if orig_price > price and orig_price > 0:
        discount = round(((orig_price - price) / orig_price) * 100)
    else:
        discount = min(95.0, max(0.0, raw_discount))
    
    reviews_count = int(p.get('review_count') or 0)
    rating_val = float(p.get('rating') or 4.2)
    img_url = p.get('image_url') or ''
    prod_url = p.get('product_url') or ''
    launch_date_str = p.get('launch_date') or p.get('first_seen_date') or str(date.today())
    
    days_since_launch = 14
    try:
        ld = datetime.strptime(launch_date_str.split('T')[0], "%Y-%m-%d").date()
        days_since_launch = (date.today() - ld).days
    except Exception:
        days_since_launch = p.get('days_since_launch') or 14

    overall_score = float(score.get('overall_trend_score') or 0.0)
    velocity_score = float(score.get('velocity_score') or 0.0)
    recency_score = float(score.get('recency_score') or 0.0)
    popularity_score = float(score.get('popularity_score') or 0.0)
    price_pos_score = float(score.get('price_position_score') or 0.0)
    direction = score.get('trend_direction') or 'stable'
    phase = score.get('trend_phase') or 'Growth'

    clean_desc = clean_product_description(p.get('description', ''), title=title, attrs=attrs)

    col_hero_img, col_hero_info = st.columns([1, 2])
    with col_hero_img:
        if img_url:
            st.image(img_url, use_container_width=True)
    with col_hero_info:
        st.markdown(f"<span class='platform-badge'>{brand.upper()}</span>", unsafe_allow_html=True)
        st.markdown(f"### {title}")
        st.markdown(f"<p class='card-description' style='height:auto; display:block;'>{clean_desc}</p>", unsafe_allow_html=True)
        
        hero_price_html = textwrap.dedent(f"""
            <div style='display:flex; align-items:baseline; gap:8px; margin: 8px 0;'>
                <span class='price-main'>₹{price:,.0f}</span>
                <span class='price-original'>₹{orig_price:,.0f}</span>
                <span class='price-discount'>{discount:.0f}% OFF</span>
            </div>
        """)
        st.markdown(hero_price_html, unsafe_allow_html=True)
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if prod_url and prod_url != '#':
                st.markdown(f"<a href='{prod_url}' target='_blank' class='product-link-btn' style='margin-top:0;'>Open Live Store Page ↗</a>", unsafe_allow_html=True)
        with col_btn2:
            is_saved = prod_id in st.session_state.saved_product_ids
            if is_saved:
                if st.button("Remove from Saved", key=f"dlg_rem_{prod_id}", use_container_width=True):
                    api_delete(f"/api/saved-products/{prod_id}")
                    st.session_state.saved_product_ids.remove(prod_id)
                    st.rerun()
            else:
                if st.button("★ Save to Portfolio", key=f"dlg_add_{prod_id}", use_container_width=True):
                    api_post(f"/api/saved-products/{prod_id}")
                    st.session_state.saved_product_ids.add(prod_id)
                    st.rerun()

    st.divider()

    st.markdown("#### 1. Verified Underlying Product Data")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Actual Reviews", f"{reviews_count:,}", help="Total verified customer review volume extracted from store catalog.")
    with col_m2:
        st.metric("Days Since Posted", f"{days_since_launch} days", f"Launched {launch_date_str.split('T')[0]}")
    with col_m3:
        st.metric("Customer Rating", f"{rating_val:.1f} ★", help="Store verified average buyer satisfaction.")
    with col_m4:
        st.metric("Trend Phase", f"{phase.title()}", f"{direction.upper()} Momentum")

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    st.markdown("#### 2. Trend Scoring Algorithm Breakdown")
    st.caption("Mathematical breakdown of the 100-point Trend Index for this design:")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        f1_html = textwrap.dedent(f"""
            <div class='factor-breakdown-card'>
                <div class='factor-header'>
                    <span>⚡ Review Growth Velocity</span>
                    <span class='factor-score-val'>{velocity_score:.0f}/100</span>
                </div>
                <div class='factor-weight'>Weight: 35%</div>
                <div class='factor-desc'>
                    Measures daily review accumulation rate vs market max. High velocity signifies accelerated buyer interest.
                </div>
            </div>
            <div class='factor-breakdown-card'>
                <div class='factor-header'>
                    <span>👥 Total Demand Volume</span>
                    <span class='factor-score-val'>{popularity_score:.0f}/100</span>
                </div>
                <div class='factor-weight'>Weight: 20%</div>
                <div class='factor-desc'>
                    Logarithmically scaled cumulative customer adoption ({reviews_count:,} reviews).
                </div>
            </div>
            <div class='factor-breakdown-card'>
                <div class='factor-header'>
                    <span>★ Customer Satisfaction</span>
                    <span class='factor-score-val'>{(rating_val/5.0)*100:.0f}/100</span>
                </div>
                <div class='factor-weight'>Weight: 20%</div>
                <div class='factor-desc'>
                    Normalized customer review satisfaction ({rating_val:.1f} / 5.0).
                </div>
            </div>
        """)
        st.markdown(f1_html, unsafe_allow_html=True)
    with col_f2:
        f2_html = textwrap.dedent(f"""
            <div class='factor-breakdown-card'>
                <div class='factor-header'>
                    <span>📅 Launch Recency Factor</span>
                    <span class='factor-score-val'>{recency_score:.0f}/100</span>
                </div>
                <div class='factor-weight'>Weight: 15%</div>
                <div class='factor-desc'>
                    Exponential decay curve e^(-0.04 × {days_since_launch} days). Recent launches gain visibility advantage.
                </div>
            </div>
            <div class='factor-breakdown-card'>
                <div class='factor-header'>
                    <span>💰 Price Competitiveness</span>
                    <span class='factor-score-val'>{price_pos_score:.0f}/100</span>
                </div>
                <div class='factor-weight'>Weight: 10%</div>
                <div class='factor-desc'>
                    Price positioning against median category benchmark (Fabric: {attrs.get('fabric', 'Cotton')}).
                </div>
            </div>
            <div class='factor-breakdown-card'>
                <div class='factor-header'>
                    <span style='color:#4f46e5;'>🎯 Composite Trend Score</span>
                    <span style='font-size:1.15rem; font-weight:800; color:#4f46e5;'>{overall_score:.1f}/100</span>
                </div>
                <div class='factor-weight'>Final Weighted Index</div>
                <div class='factor-desc'>
                    (Vel × 35%) + (Pop × 20%) + (Rating × 20%) + (Recency × 15%) + (Price × 10%)
                </div>
            </div>
        """)
        st.markdown(f2_html, unsafe_allow_html=True)

    st.markdown("#### 3. Design Attribute Profile")
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    col_d1.info(f"**Fabric:** {attrs.get('fabric', 'Cotton')}")
    col_d2.info(f"**Pattern / Craft:** {attrs.get('pattern', 'Printed')}")
    col_d3.info(f"**Neckline:** {attrs.get('neckline', 'Round Neck')}")
    col_d4.info(f"**Sleeve Style:** {attrs.get('sleeve_type', '3/4 Sleeve')}")

    if history:
        st.markdown("#### 4. Historical Trajectory (30-Day Audit)")
        hist_df = pd.DataFrame(history)
        hist_df['date'] = hist_df['date'].apply(lambda x: x.split('T')[0] if isinstance(x, str) else x)

        chart_bg = "#ffffff" if current_theme == "light" else "#111520"
        chart_text = "#475569" if current_theme == "light" else "#94a3b8"
        grid_color = "#f1f5f9" if current_theme == "light" else "#1f2738"
        title_color = "#0f172a" if current_theme == "light" else "#ffffff"

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            fig_price = px.line(hist_df, x='date', y='price', title="Price Trajectory (₹)",
                                markers=True, labels={'price': 'Price (₹)', 'date': 'Date'})
            fig_price.update_layout(
                height=260, plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
                font=dict(color=chart_text, family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                yaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                title_font_color=title_color, margin=dict(l=10, r=10, t=30, b=10)
            )
            fig_price.update_traces(line_color='#4f46e5', line_width=2.5, marker_color='#6366f1')
            st.plotly_chart(fig_price, use_container_width=True)

        with col_c2:
            fig_rev = px.area(hist_df, x='date', y='review_count', title="Cumulative Reviews Velocity",
                              labels={'review_count': 'Verified Reviews', 'date': 'Date'})
            fig_rev.update_layout(
                height=260, plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
                font=dict(color=chart_text, family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                yaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                title_font_color=title_color, margin=dict(l=10, r=10, t=30, b=10)
            )
            fig_rev.update_traces(line_color='#059669', fillcolor='rgba(5, 150, 105, 0.15)', line_width=2)
            st.plotly_chart(fig_rev, use_container_width=True)

# ─── Sidebar Body ────────────────────────────────────────────────────────────
with st.sidebar:
    saved_count = len(st.session_state.saved_product_ids)
    st.markdown(textwrap.dedent(f"""
        <div style='background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; display:flex; justify-content:space-between; align-items:center;'>
            <span style='font-size:0.78rem; color:#b45309; font-weight:700;'>★ Saved Shortlist</span>
            <span style='background:#d97706; color:#ffffff; font-size:0.72rem; font-weight:800; padding:2px 8px; border-radius:6px;'>{saved_count}</span>
        </div>
    """), unsafe_allow_html=True)

    st.markdown("**Search Catalog**")
    keyword = st.text_input(
        "Search Keyword",
        value="kurti",
        placeholder="Search keywords (e.g. kurti, cotton, anarkali)...",
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    st.markdown("**Monitored Brands & Stores**")

    sources_data = api_get("/api/sources")
    all_available_names = sources_data.get("all_names") if sources_data else [
        'Libas', 'Janasya', 'Aarsi', 'Bunaai', 'Mulmul',
        'Gulabo Jaipur', 'Jaipur Kurti', 'Fashor', 'Sabhyata', 
        'Rustorange', 'Karagiri', 'Tjori', 'TrueBrowns', 'Myntra', 'Flipkart'
    ]
    
    default_selected = [s for s in ['Libas', 'Janasya', 'Aarsi', 'Bunaai', 'Myntra', 'Jaipur Kurti', 'Fashor', 'Sabhyata'] if s in all_available_names]

    platforms = st.multiselect(
        "Active Sources",
        all_available_names,
        default=default_selected
    )

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        min_rating = st.slider("Min Rating", 0.0, 5.0, 3.0, 0.1)
    with col_s2:
        min_reviews = st.number_input("Min Reviews", 0, 10000, 0, step=10)

    price_range = st.slider("Price Spectrum (₹)", 0, 10000, (199, 7999), step=100)

    st.divider()
    
    # ── Feature: Manually Add New Website / Store to Scan ──
    with st.expander("➕ Add Custom Website to Scan", expanded=False):
        st.caption("Add any ethnic wear brand, Shopify store, or custom collection URL to monitor.")
        custom_name = st.text_input("Brand / Store Name", placeholder="e.g. Biba, House of Indya...", key="add_store_name")
        custom_url = st.text_input("Store or Collection URL", placeholder="e.g. https://www.biba.in...", key="add_store_url")
        
        if st.button("✦ Add Store Feed", use_container_width=True):
            if not custom_name or not custom_url:
                st.error("Please enter both Store Name and URL.")
            else:
                res = api_post(f"/api/sources?name={custom_name}&url={custom_url}")
                if res.get("status") == "success":
                    st.success(f"Added {custom_name}! Refreshing sources...")
                    st.rerun()
                else:
                    st.error(f"Failed to add store: {res}")

        custom_sources_list = sources_data.get("custom", []) if sources_data else []
        if custom_sources_list:
            st.markdown("<div style='font-size:0.75rem; font-weight:700; margin-top:8px;'>User-Added Custom Stores:</div>", unsafe_allow_html=True)
            for cs in custom_sources_list:
                col_c1, col_c2 = st.columns([3, 1])
                with col_c1:
                    st.markdown(f"<span class='custom-source-badge'>{cs['name']}</span>", unsafe_allow_html=True)
                with col_c2:
                    if st.button("✕", key=f"del_cs_{cs['brand_key']}", help="Remove custom store"):
                        api_delete(f"/api/sources/{cs['brand_key']}")
                        st.rerun()

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    st.markdown("**Live Scraper Trigger**")
    st.caption("Pulls real product feeds and parses design attributes with automatic deduplication.")

    col_ref1, col_ref2 = st.columns(2)
    with col_ref1:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col_ref2:
        if st.button("Trigger Live Scraping", use_container_width=True):
            plats_list = [p.lower() for p in platforms]
            if not plats_list:
                st.error("Select at least one brand or marketplace.")
            else:
                with st.spinner("Scraping live brand catalogs..."):
                    params = {"platforms": plats_list, "keyword": keyword}
                    success = False
                    try:
                        r = requests.post(f"{API_URL}/api/scraper/scrape", params=params, timeout=5)
                        if r.status_code == 200:
                            success = True
                    except Exception:
                        pass
                    
                    if not success and db_manager:
                        try:
                            from backend.scrapers.orchestrator import ScraperOrchestrator
                            def run_in_bg():
                                orch = ScraperOrchestrator(db_manager)
                                orch.run_orchestrator(platforms=plats_list, keyword=keyword)
                            t = threading.Thread(target=run_in_bg, daemon=True)
                            t.start()
                            success = True
                        except Exception as e:
                            st.error(f"Background scraper trigger notice: {e}")
                    
                    if success:
                        st.cache_data.clear()
                        st.success("Scrape job triggered in background.")
                        st.rerun()
                    else:
                        st.error("Could not trigger live scraper.")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.caption(f"Engine: Fast WAL Cached DB")
    st.caption(f"Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ─── Main Content & Executive KPI Metrics ─────────────────────────────────────
st.markdown("<div class='brand-eyebrow'>Market Intelligence System</div>", unsafe_allow_html=True)
st.markdown("<h1 class='main-header'><span>Saheli Kurti Intelligence</span></h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Real-time design attribute tracking, review velocity analytics, and price benchmarking across verified Indian ethnic wear brands.</p>", unsafe_allow_html=True)

kpi_products = api_get("/api/products/all", {"limit": 500, "keyword": keyword})
kpi_trending = api_get("/api/products", {
    "limit": 100, "min_rating": 0, "min_reviews": 0,
    "price_min": 0, "price_max": 99999, "keyword": keyword
})

total_prods = len(kpi_products) if kpi_products else 0
avg_score = 0.0
platforms_active = 0
rising_count = 0

if kpi_products:
    avg_score = sum(float(p.get('overall_trend_score') or 0) for p in kpi_products) / max(1, total_prods)
    platforms_active = len(set(p.get('platform', '') for p in kpi_products))

if kpi_trending:
    rising_count = sum(1 for p in kpi_trending if p.get('trend_direction') == 'rising')

col_k1, col_k2, col_k3, col_k4 = st.columns(4)
with col_k1:
    st.markdown(textwrap.dedent(f"""
        <div class='kpi-card kpi-card-1'>
            <div class='kpi-value'>{total_prods:,}</div>
            <div class='kpi-label'>Active Indexed SKUs</div>
            <div class='kpi-delta delta-indigo'>Live Catalog Feed</div>
        </div>
    """), unsafe_allow_html=True)
with col_k2:
    val = f"{avg_score:.1f}" if total_prods > 0 else "—"
    st.markdown(textwrap.dedent(f"""
        <div class='kpi-card kpi-card-2'>
            <div class='kpi-value'>{val}</div>
            <div class='kpi-label'>Mean Trend Index / 100</div>
            <div class='kpi-delta delta-emerald'>Velocity Weighted</div>
        </div>
    """), unsafe_allow_html=True)
with col_k3:
    st.markdown(textwrap.dedent(f"""
        <div class='kpi-card kpi-card-3'>
            <div class='kpi-value'>{platforms_active}</div>
            <div class='kpi-label'>Monitored Brand Feeds</div>
            <div class='kpi-delta delta-orange'>Direct D2C Channels</div>
        </div>
    """), unsafe_allow_html=True)
with col_k4:
    st.markdown(textwrap.dedent(f"""
        <div class='kpi-card kpi-card-4'>
            <div class='kpi-value'>{saved_count}</div>
            <div class='kpi-label'>Saved Shortlist Items</div>
            <div class='kpi-delta delta-amber'>Custom Portfolio</div>
        </div>
    """), unsafe_allow_html=True)

st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# ─── Navigation Tabs ─────────────────────────────────────────────────────────
tab1, tab_saved, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Trending Now",
    f"★ Saved Portfolio ({saved_count})",
    "All-Time Demand",
    "Catalog Explorer",
    "Design Analytics",
    "Brand & Competitor Intel",
    "Scraper Diagnostics"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: Trending Now
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Top Trending Kurti Designs")
    st.caption("Click **'✦ Inspect'** on any card to view its verified review velocity, days since posted, and complete scoring factors.")

    params = {
        "limit": 36,
        "min_rating": min_rating,
        "min_reviews": min_reviews,
        "price_min": price_range[0],
        "price_max": price_range[1],
        "platforms": [p.lower() for p in platforms] if platforms else None,
        "keyword": keyword
    }
    trending = api_get("/api/products", params)

    if trending:
        cols_per_row = 4
        for i in range(0, len(trending), cols_per_row):
            row_items = trending[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for idx, item in enumerate(row_items):
                with cols[idx]:
                    prod_id     = item.get('id')
                    title_str   = item.get('title', 'Ethnic Kurti')
                    raw_desc    = item.get('description', '')
                    image_url   = item.get('image_url', '')
                    platform    = item.get('platform', 'unknown').lower()
                    brand_name  = item.get('brand', platform.capitalize())
                    price       = float(item.get('price', 0.0))
                    orig_price  = float(item.get('original_price', 0.0) or price)
                    
                    raw_disc    = float(item.get('discount_percentage', 0.0))
                    if orig_price > price and orig_price > 0:
                        discount = round(((orig_price - price) / orig_price) * 100)
                    else:
                        discount = min(95.0, max(0.0, raw_disc))

                    rating      = float(item.get('rating', 0.0))
                    reviews     = int(item.get('review_count', 0))
                    trend_score = float(item.get('trend_score', 0.0))
                    direction   = item.get('trend_direction', 'stable')
                    attrs       = item.get('attributes', {})
                    product_url = item.get('product_url', '')

                    clean_desc = clean_product_description(raw_desc, title=title_str, attrs=attrs)

                    dir_class = f"dir-{direction}"
                    dir_icon = {"rising": "▲", "falling": "▼", "stable": "◆", "new": "★"}.get(direction, "•")

                    price_html = f"<span class='price-main'>₹{price:,.0f}</span>"
                    if orig_price > price:
                        price_html += f"<span class='price-original'>₹{orig_price:,.0f}</span>"
                    if discount > 0:
                        price_html += f"<span class='price-discount'>{discount:.0f}% OFF</span>"

                    if image_url:
                        img_html = f"<img class='product-img' src='{image_url}' onerror=\"this.style.display='none'\">"
                    else:
                        img_html = "<div style='width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:0.75rem;'>No Image</div>"

                    link_html = ""
                    if product_url and product_url != '#':
                        link_html = f"<a href='{product_url}' target='_blank' class='product-link-btn'>View on {brand_name} ↗</a>"

                    card_html = textwrap.dedent(f"""
<div class='product-card'>
<div class='product-img-wrapper'>
{img_html}
</div>
<div class='product-body'>
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;'>
<span class='platform-badge'>{brand_name}</span>
<span class='dir-badge {dir_class}'>{dir_icon} {direction.upper()}</span>
</div>
<div class='card-title' title='{title_str}'>{title_str}</div>
<div class='card-description' title='{clean_desc}'>{clean_desc}</div>
<div class='attr-row'>
<span class='attr-chip'>{attrs.get("fabric","Cotton")}</span>
<span class='attr-chip'>{attrs.get("pattern","Printed")}</span>
<span class='attr-chip'>{attrs.get("neckline","Round Neck")}</span>
</div>
<div class='price-row'>{price_html}</div>
<div class='rating-row'>★ {rating:.1f} &nbsp;·&nbsp; {reviews:,} reviews</div>
<div class='trend-meter-bg'>
<div class='trend-meter-fill' style='width:{trend_score}%;'></div>
</div>
<div class='trend-footer'>
<span>Trend Velocity Score</span>
<span class='trend-score-value'>{trend_score:.1f}/100</span>
</div>
{link_html}
</div>
</div>
""")
                    st.markdown(card_html, unsafe_allow_html=True)

                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        if st.button("✦ Inspect", key=f"insp_trend_{prod_id}", use_container_width=True):
                            show_product_inspector_dialog(prod_id)
                    with col_act2:
                        is_saved = prod_id in st.session_state.saved_product_ids
                        if is_saved:
                            if st.button("✓ Saved", key=f"save_trend_{prod_id}", use_container_width=True):
                                api_delete(f"/api/saved-products/{prod_id}")
                                st.session_state.saved_product_ids.remove(prod_id)
                                st.rerun()
                        else:
                            if st.button("★ Save", key=f"save_trend_{prod_id}", use_container_width=True):
                                api_post(f"/api/saved-products/{prod_id}")
                                st.session_state.saved_product_ids.add(prod_id)
                                st.rerun()
    else:
        render_no_data("✦", "No Active Products in Feed", "Trigger live scraping to index products.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: Saved Products (Wishlist / Portfolio)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_saved:
    st.markdown("### ★ Saved Product Portfolio & Shortlist")
    st.caption("Manage saved designs, compare factor metrics side-by-side, and export custom portfolios.")

    saved_items = api_get("/api/saved-products")

    if saved_items:
        col_hdr1, col_hdr2 = st.columns([3, 1])
        with col_hdr1:
            st.markdown(f"**Total Shortlisted Products: `{len(saved_items)}`**")
        with col_hdr2:
            if st.button("Clear All Saved Items", use_container_width=True):
                for p in saved_items:
                    api_delete(f"/api/saved-products/{p['id']}")
                st.session_state.saved_product_ids.clear()
                st.rerun()

        comp_rows = []
        for p in saved_items:
            attrs = p.get('attributes', {})
            comp_rows.append({
                "ID": p.get('id'),
                "Product": p.get('title'),
                "Brand": p.get('brand'),
                "Price (₹)": int(float(p.get('price', 0))),
                "Rating": float(p.get('rating', 0)),
                "Reviews": int(p.get('review_count', 0)),
                "Days Since Posted": p.get('days_since_launch', '—'),
                "Trend Score": float(p.get('trend_score') or 0.0),
                "Velocity Score": float(p.get('velocity_score') or 0.0),
                "Recency Score": float(p.get('recency_score') or 0.0),
                "Popularity Score": float(p.get('popularity_score') or 0.0),
                "Price Pos Score": float(p.get('price_position_score') or 0.0),
                "Fabric": attrs.get('fabric', '—'),
                "Pattern": attrs.get('pattern', '—'),
                "Neckline": attrs.get('neckline', '—'),
                "Sleeve": attrs.get('sleeve_type', '—'),
                "Store URL": p.get('product_url', '')
            })
        
        saved_df = pd.DataFrame(comp_rows)

        st.dataframe(
            saved_df.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price (₹)": st.column_config.NumberColumn(format="₹%d"),
                "Rating": st.column_config.NumberColumn(format="%.1f ★"),
                "Trend Score": st.column_config.ProgressColumn("Trend Score", min_value=0, max_value=100, format="%.1f"),
                "Velocity Score": st.column_config.ProgressColumn("Velocity", min_value=0, max_value=100, format="%.0f"),
                "Recency Score": st.column_config.ProgressColumn("Recency", min_value=0, max_value=100, format="%.0f"),
                "Store URL": st.column_config.LinkColumn("Store URL")
            }
        )

        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv_saved = saved_df.to_csv(index=False).encode('utf-8')
            st.download_button("Export Saved Portfolio (CSV)", csv_saved, "saved_kurti_portfolio.csv", "text/csv", use_container_width=True)
        with col_exp2:
            try:
                import io
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    saved_df.to_excel(writer, sheet_name='Saved Portfolio', index=False)
                st.download_button("Export Saved Portfolio (Excel)", buf.getvalue(), "saved_kurti_portfolio.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
            except Exception as e:
                st.caption(f"Excel export notice: {e}")

        st.divider()
        st.markdown("#### Saved Cards Grid")

        cols_per_row = 4
        for i in range(0, len(saved_items), cols_per_row):
            row_items = saved_items[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for idx, item in enumerate(row_items):
                with cols[idx]:
                    prod_id     = item.get('id')
                    title_str   = item.get('title', 'Ethnic Kurti')
                    raw_desc    = item.get('description', '')
                    image_url   = item.get('image_url', '')
                    platform    = item.get('platform', 'unknown').lower()
                    brand_name  = item.get('brand', platform.capitalize())
                    price       = float(item.get('price', 0.0))
                    orig_price  = float(item.get('original_price', 0.0) or price)
                    rating      = float(item.get('rating', 0.0))
                    reviews     = int(item.get('review_count', 0))
                    trend_score = float(item.get('trend_score', 0.0))
                    direction   = item.get('trend_direction', 'stable')
                    attrs       = item.get('attributes', {})
                    clean_desc  = clean_product_description(raw_desc, title=title_str, attrs=attrs)

                    price_html = f"<span class='price-main'>₹{price:,.0f}</span>"
                    if orig_price > price:
                        price_html += f"<span class='price-original'>₹{orig_price:,.0f}</span>"

                    img_html = f"<img class='product-img' src='{image_url}' onerror=\"this.style.display='none'\">" if image_url else "<div style='height:100%;'></div>"

                    saved_card_html = textwrap.dedent(f"""
<div class='product-card'>
<div class='product-img-wrapper'>{img_html}</div>
<div class='product-body'>
<div style='display:flex; justify-content:space-between; align-items:center;'>
<span class='platform-badge'>{brand_name}</span>
<span class='dir-badge dir-{direction}'>{direction.upper()}</span>
</div>
<div class='card-title' title='{title_str}'>{title_str}</div>
<div class='card-description'>{clean_desc}</div>
<div class='price-row'>{price_html}</div>
<div class='rating-row'>★ {rating:.1f} &nbsp;·&nbsp; {reviews:,} reviews</div>
<div class='trend-meter-bg'><div class='trend-meter-fill' style='width:{trend_score}%;'></div></div>
<div class='trend-footer'><span>Trend Score</span><span class='trend-score-value'>{trend_score:.1f}/100</span></div>
</div>
</div>
""")
                    st.markdown(saved_card_html, unsafe_allow_html=True)

                    col_c_act1, col_c_act2 = st.columns(2)
                    with col_c_act1:
                        if st.button("✦ Inspect", key=f"insp_saved_{prod_id}", use_container_width=True):
                            show_product_inspector_dialog(prod_id)
                    with col_c_act2:
                        if st.button("Remove", key=f"rem_saved_{prod_id}", use_container_width=True):
                            api_delete(f"/api/saved-products/{prod_id}")
                            st.session_state.saved_product_ids.remove(prod_id)
                            st.rerun()
    else:
        render_no_data("★", "No Saved Products Yet", "Click **'★ Save'** on any product across tabs to build your personalized trend portfolio.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: All-Time Demand
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### All-Time Demand Leaders")
    st.caption("Products ranked by cumulative lifetime review volume and sustained market velocity.")

    demand_data = api_get("/api/products/all-time-demand", {"limit": 100, "keyword": keyword})

    if demand_data:
        demand_rows = []
        for p in demand_data:
            attrs = p.get('attributes', {})
            demand_rows.append({
                "ID": p.get('id'),
                "Rank": 0,
                "Product": p.get('title', '—'),
                "Brand": p.get('brand', 'Generic'),
                "Price (₹)": int(float(p.get('price', 0))),
                "Discount": f"{float(p.get('discount_percentage', 0)):.0f}%",
                "Rating": float(p.get('rating', 0)),
                "Reviews": int(p.get('review_count', 0)),
                "Days Active": p.get('days_since_launch', '—'),
                "Trend Score": float(p.get('overall_trend_score') or 0),
                "Velocity Score": float(p.get('velocity_score') or 0),
                "Popularity Score": float(p.get('popularity_score') or 0),
                "Fabric": attrs.get('fabric', '—'),
                "Pattern": attrs.get('pattern', '—'),
                "Live Store Link": p.get('product_url', ''),
            })

        demand_df = pd.DataFrame(demand_rows)
        demand_df["Rank"] = range(1, len(demand_df) + 1)

        col_sf1, col_sf2 = st.columns([3, 1])
        with col_sf1:
            demand_search = st.text_input("Filter table by brand, fabric, pattern...", "", key="demand_search")
        with col_sf2:
            show_top = st.selectbox("Display Count", [10, 25, 50, 100], index=1, key="demand_top")

        if demand_search:
            mask = demand_df.apply(lambda row: row.astype(str).str.contains(demand_search, case=False).any(), axis=1)
            demand_df = demand_df[mask]

        demand_df = demand_df.head(show_top)

        st.dataframe(
            demand_df.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price (₹)": st.column_config.NumberColumn(format="₹%d"),
                "Rating": st.column_config.NumberColumn(format="%.1f ★"),
                "Reviews": st.column_config.NumberColumn(format="%d"),
                "Trend Score": st.column_config.ProgressColumn("Trend Score", min_value=0, max_value=100, format="%.1f"),
                "Velocity Score": st.column_config.ProgressColumn("Velocity", min_value=0, max_value=100, format="%.0f"),
                "Popularity Score": st.column_config.ProgressColumn("Popularity", min_value=0, max_value=100, format="%.0f"),
                "Live Store Link": st.column_config.LinkColumn("Store Link"),
            }
        )

        st.markdown("#### Quick SKU Inspector & Saver")
        sel_demand_title = st.selectbox("Select product from demand leaders to inspect / save", options=demand_df['Product'].unique())
        if sel_demand_title:
            matched_prod = demand_df[demand_df['Product'] == sel_demand_title].iloc[0]
            m_id = matched_prod['ID']
            col_d_act1, col_d_act2 = st.columns(2)
            with col_d_act1:
                if st.button("✦ Inspect Complete Factors & Calculation", key=f"insp_d_{m_id}", use_container_width=True):
                    show_product_inspector_dialog(m_id)
            with col_d_act2:
                is_saved = m_id in st.session_state.saved_product_ids
                if is_saved:
                    if st.button("✓ Saved in Portfolio", key=f"save_d_{m_id}", use_container_width=True):
                        api_delete(f"/api/saved-products/{m_id}")
                        st.session_state.saved_product_ids.remove(m_id)
                        st.rerun()
                else:
                    if st.button("★ Save to Portfolio", key=f"save_d_{m_id}", use_container_width=True):
                        api_post(f"/api/saved-products/{m_id}")
                        st.session_state.saved_product_ids.add(m_id)
                        st.rerun()

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        st.markdown("#### Demand Volume Distribution")
        top10 = demand_df.head(10)
        fig_demand = go.Figure()
        
        chart_bg = "#ffffff" if current_theme == "light" else "#111520"
        chart_text = "#475569" if current_theme == "light" else "#94a3b8"
        grid_color = "#f1f5f9" if current_theme == "light" else "#1f2738"
        bar_colors = [[0, '#cbd5e1'], [0.5, '#4f46e5'], [1, '#059669']] if current_theme == "light" else [[0, '#1e293b'], [0.5, '#d4af37'], [1, '#10b981']]

        fig_demand.add_trace(go.Bar(
            x=top10["Reviews"], y=top10["Product"].str[:35],
            orientation='h',
            marker=dict(
                color=top10["Trend Score"],
                colorscale=bar_colors,
                colorbar=dict(title="Score", tickfont=dict(color=chart_text)),
            ),
            hovertemplate="<b>%{y}</b><br>Reviews: %{x:,}<extra></extra>"
        ))
        fig_demand.update_layout(
            height=360,
            plot_bgcolor=chart_bg,
            paper_bgcolor=chart_bg,
            font=dict(color=chart_text, family='Plus Jakarta Sans'),
            xaxis=dict(showgrid=True, gridcolor=grid_color, title="Review Volume", color=chart_text),
            yaxis=dict(autorange="reversed", color=chart_text),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig_demand, use_container_width=True)

        csv_data = demand_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Demand Analytics (CSV)", csv_data, "kurti_demand_rankings.csv", "text/csv")
    else:
        render_no_data("✦", "No Demand Data Available", "Trigger live scraping to generate lifetime demand rankings.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: Catalog Explorer
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Catalog Inventory & Spec Deep-Dive")
    st.caption("Search, filter, and inspect product specifications, pricing trajectories, and review increments.")

    all_products = api_get("/api/products/all", {"limit": 500, "keyword": keyword})

    if all_products:
        rows = []
        for p in all_products:
            attrs = p.get('attributes', {})
            clean_d = clean_product_description(p.get('description', ''), title=p.get('title', ''), attrs=attrs)
            rows.append({
                "ID": p.get('id'),
                "Title": p.get('title'),
                "Brand": p.get('brand', 'Unknown'),
                "Description": clean_d,
                "Price (₹)": int(float(p.get('price', 0))),
                "Original (₹)": int(float(p.get('original_price', 0) or 0)),
                "Discount %": float(p.get('discount_percentage', 0)),
                "Rating": float(p.get('rating', 0)),
                "Reviews": int(p.get('review_count', 0)),
                "Fabric": attrs.get('fabric', '—'),
                "Pattern": attrs.get('pattern', '—'),
                "Neckline": attrs.get('neckline', '—'),
                "Sleeve": attrs.get('sleeve_type', '—'),
                "Trend Score": float(p.get('overall_trend_score') or 0),
                "Launch Date": (p.get('launch_date', '') or '').split('T')[0],
                "Live Store URL": p.get('product_url', ''),
            })
        df = pd.DataFrame(rows)

        search_query = st.text_input("Search catalog by title, brand, fabric, neckline...", "", key="cat_search")
        if search_query:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)]

        st.dataframe(
            df.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price (₹)": st.column_config.NumberColumn(format="₹%d"),
                "Original (₹)": st.column_config.NumberColumn(format="₹%d"),
                "Discount %": st.column_config.NumberColumn(format="%d%%"),
                "Rating": st.column_config.NumberColumn(format="%.1f ★"),
                "Trend Score": st.column_config.ProgressColumn("Trend Score", min_value=0, max_value=100, format="%.1f"),
                "Live Store URL": st.column_config.LinkColumn("Store Link"),
            }
        )

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button("Export Catalog to CSV", csv_data, "kurti_catalog_export.csv", "text/csv", use_container_width=True)
        with col_dl2:
            try:
                import io
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Kurti Catalog', index=False)
                st.download_button("Export Catalog to Excel", buf.getvalue(), "kurti_catalog_export.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
            except Exception as e:
                st.caption(f"Excel export notice: {e}")

        st.divider()
        st.markdown("#### Interactive SKU Inspector")

        selected_title = st.selectbox(
            "Select product for historical audit & factor breakdown",
            options=df['Title'].unique(),
            index=0 if len(df) > 0 else None
        )

        if selected_title:
            prod_id = None
            for p in all_products:
                if p['title'] == selected_title:
                    prod_id = p['id']
                    break

            if prod_id:
                col_i_act1, col_i_act2 = st.columns(2)
                with col_i_act1:
                    if st.button("✦ Open Detailed Factor Calculation Modal", key="insp_cat_btn", use_container_width=True):
                        show_product_inspector_dialog(prod_id)
                with col_i_act2:
                    is_saved = prod_id in st.session_state.saved_product_ids
                    if is_saved:
                        if st.button("✓ Saved in Portfolio", key=f"save_cat_{prod_id}", use_container_width=True):
                            api_delete(f"/api/saved-products/{prod_id}")
                            st.session_state.saved_product_ids.remove(prod_id)
                            st.rerun()
                    else:
                        if st.button("★ Save to Portfolio", key=f"save_cat_{prod_id}", use_container_width=True):
                            api_post(f"/api/saved-products/{prod_id}")
                            st.session_state.saved_product_ids.add(prod_id)
                            st.rerun()

                details = api_get(f"/api/products/{prod_id}")
                if details:
                    p_info  = details.get('product', {})
                    sc_info = details.get('score', {})
                    history = details.get('metrics_history', [])
                    p_attrs = p_info.get('attributes', {})
                    cleaned_spec_desc = clean_product_description(p_info.get('description', ''), title=p_info.get('title', ''), attrs=p_attrs)

                    col_img, col_specs = st.columns([1, 2])
                    with col_img:
                        img_url = p_info.get('image_url', '')
                        if img_url:
                            st.image(img_url, use_container_width=True)
                    with col_specs:
                        st.markdown(f"#### {p_info.get('brand','Generic')} — {p_info.get('title','')}")
                        prod_link = p_info.get('product_url', '')
                        if prod_link:
                            st.markdown(f"[**Open Live Store Page on {p_info.get('brand','Official Store')} ↗**]({prod_link})")

                        st.markdown(f"*{cleaned_spec_desc}*")

                        col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
                        col_s1.metric("Overall Score", f"{sc_info.get('overall_trend_score', 0):.1f}/100")
                        col_s2.metric("Recency", f"{sc_info.get('recency_score', 0):.0f}/100")
                        col_s3.metric("Popularity", f"{sc_info.get('popularity_score', 0):.0f}/100")
                        col_s4.metric("Velocity", f"{sc_info.get('velocity_score', 0):.0f}/100")
                        col_s5.metric("Price Pos", f"{sc_info.get('price_position_score', 0):.0f}/100")

                        st.markdown(
                            f"**Direction:** `{sc_info.get('trend_direction','—').upper()}` &nbsp;|&nbsp; "
                            f"**Fabric:** `{p_attrs.get('fabric','—')}` &nbsp;|&nbsp; "
                            f"**Pattern:** `{p_attrs.get('pattern','—')}` &nbsp;|&nbsp; "
                            f"**Neckline:** `{p_attrs.get('neckline','—')}`"
                        )

                    if history:
                        hist_df = pd.DataFrame(history)
                        hist_df['date'] = hist_df['date'].apply(lambda x: x.split('T')[0] if isinstance(x, str) else x)

                        chart_bg = "#ffffff" if current_theme == "light" else "#111520"
                        chart_text = "#475569" if current_theme == "light" else "#94a3b8"
                        grid_color = "#f1f5f9" if current_theme == "light" else "#1f2738"
                        title_color = "#0f172a" if current_theme == "light" else "#ffffff"

                        col_c1, col_c2 = st.columns(2)
                        with col_c1:
                            fig_price = px.line(hist_df, x='date', y='price', title="Price Trajectory (30-Day)",
                                                markers=True, labels={'price': 'Price (₹)', 'date': 'Date'})
                            fig_price.update_layout(
                                height=260, plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
                                font=dict(color=chart_text, family='Plus Jakarta Sans'),
                                xaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                                yaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                                title_font_color=title_color
                            )
                            fig_price.update_traces(line_color='#4f46e5', line_width=2.5, marker_color='#6366f1')
                            st.plotly_chart(fig_price, use_container_width=True)

                        with col_c2:
                            fig_rev = px.area(hist_df, x='date', y='review_count',
                                              title="Review Velocity & Demand Accumulation",
                                              labels={'review_count': 'Total Reviews', 'date': 'Date'})
                            fig_rev.update_layout(
                                height=260, plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
                                font=dict(color=chart_text, family='Plus Jakarta Sans'),
                                xaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                                yaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                                title_font_color=title_color
                            )
                            fig_rev.update_traces(line_color='#059669', fillcolor='rgba(5, 150, 105, 0.15)', line_width=2)
                            st.plotly_chart(fig_rev, use_container_width=True)
    else:
        render_no_data("✦", "No Products in Catalog", "Trigger live scraping to index products.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: Design Analytics
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### Design Attribute Market Shares & Velocity")
    st.caption("Distribution and trend indices for fabric composition, craft techniques, and necklines.")

    analytics = api_get("/api/analytics/attributes")

    if analytics:
        an_df = pd.DataFrame(analytics)
        an_df['month_year'] = an_df['month_year'].apply(lambda x: x.split('T')[0] if isinstance(x, str) else x)
        categories = an_df['attribute_category'].unique()

        chart_bg = "#ffffff" if current_theme == "light" else "#111520"
        chart_text = "#475569" if current_theme == "light" else "#94a3b8"
        grid_color = "#f1f5f9" if current_theme == "light" else "#1f2738"
        title_color = "#0f172a" if current_theme == "light" else "#ffffff"

        for cat in categories:
            st.markdown(f"#### **{cat.replace('_', ' ').title()} Index**")
            cat_df = an_df[an_df['attribute_category'] == cat].sort_values('trend_score', ascending=False)

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fig_pie = px.pie(
                    cat_df, values='product_count', names='attribute_value',
                    title=f"Catalog Share — {cat.title()}",
                    hole=0.45,
                    color_discrete_sequence=['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#64748b']
                )
                fig_pie.update_layout(
                    plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
                    font=dict(color=chart_text, family='Plus Jakarta Sans'),
                    title_font_color=title_color, margin=dict(t=50, b=10, l=10, r=10),
                    legend=dict(font=dict(color=chart_text))
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_c2:
                fig_bar = px.bar(
                    cat_df, x='attribute_value', y='trend_score',
                    title=f"Mean Trend Score — {cat.title()}",
                    labels={'trend_score': 'Trend Index', 'attribute_value': cat.title()},
                    color='trend_score',
                    color_continuous_scale=[[0, '#e2e8f0'], [0.5, '#818cf8'], [1, '#4f46e5']] if current_theme == "light" else [[0, '#1e293b'], [0.5, '#d4af37'], [1, '#10b981']]
                )
                fig_bar.update_layout(
                    plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
                    font=dict(color=chart_text, family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=False, color=chart_text),
                    yaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                    title_font_color=title_color, coloraxis_showscale=False
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            st.divider()
    else:
        render_no_data("✦", "No Attribute Analytics Available", "Trigger live scraping to compute attribute market dynamics.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5: Brand & Competitor Intel
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("### Competitor Positioning & Benchmarking")
    st.caption("Price spectrum, catalog size, and trend score positioning across Indian ethnic wear labels.")

    prods_list = api_get("/api/products/all", {"limit": 500, "keyword": keyword})

    if prods_list:
        comp_rows = []
        for p in prods_list:
            comp_rows.append({
                "Brand": p.get('brand', 'Generic'),
                "Platform": p.get('platform', '').upper(),
                "Price": float(p.get('price', 0)),
                "Discount": float(p.get('discount_percentage', 0) or 0),
                "Rating": float(p.get('rating', 0) or 0),
                "Reviews": int(p.get('review_count', 0) or 0),
                "Trend Score": float(p.get('overall_trend_score') or 0),
            })
        comp_df = pd.DataFrame(comp_rows)

        chart_bg = "#ffffff" if current_theme == "light" else "#111520"
        chart_text = "#475569" if current_theme == "light" else "#94a3b8"
        grid_color = "#f1f5f9" if current_theme == "light" else "#1f2738"
        title_color = "#0f172a" if current_theme == "light" else "#ffffff"

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.markdown("#### Price Spectrum by Brand")
            fig_box = px.box(
                comp_df, x='Brand', y='Price', color='Brand',
                title="Price Dispersion (Min / Median / Max) by Brand",
                color_discrete_sequence=['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#64748b']
            )
            fig_box.update_layout(
                plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
                font=dict(color=chart_text, family='Plus Jakarta Sans'),
                yaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text, title="Price (₹)"),
                xaxis=dict(color=chart_text), title_font_color=title_color, showlegend=False
            )
            st.plotly_chart(fig_box, use_container_width=True)

        with col_p2:
            st.markdown("#### Catalog Depth by Brand")
            brand_counts = comp_df['Brand'].value_counts().reset_index()
            brand_counts.columns = ['Brand', 'Products']
            fig_brands = px.bar(
                brand_counts, x='Products', y='Brand', orientation='h',
                title="Indexed SKUs Count",
                color='Products',
                color_continuous_scale=[[0, '#e2e8f0'], [0.5, '#818cf8'], [1, '#4f46e5']] if current_theme == "light" else [[0, '#1e293b'], [0.5, '#d4af37'], [1, '#10b981']]
            )
            fig_brands.update_layout(
                plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
                font=dict(color=chart_text, family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
                yaxis=dict(autorange="reversed", color=chart_text), title_font_color=title_color,
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_brands, use_container_width=True)

        st.markdown("#### Mean Brand Trend Index")
        brand_scores = comp_df.groupby('Brand')['Trend Score'].mean().reset_index().sort_values('Trend Score', ascending=False)
        fig_plat = px.bar(
            brand_scores, x='Brand', y='Trend Score', color='Brand',
            title="Brand Benchmark Score",
            color_discrete_sequence=['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#64748b']
        )
        fig_plat.update_layout(
            plot_bgcolor=chart_bg, paper_bgcolor=chart_bg,
            font=dict(color=chart_text, family='Plus Jakarta Sans'),
            xaxis=dict(color=chart_text), yaxis=dict(showgrid=True, gridcolor=grid_color, color=chart_text),
            title_font_color=title_color, showlegend=False
        )
        st.plotly_chart(fig_plat, use_container_width=True)
    else:
        render_no_data("✦", "No Brand Intelligence Data", "Trigger live scraping to generate competitor benchmarks.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6: Scraper Diagnostics & Custom Websites Management
# ═══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("### Scraper Execution Logs & Custom Store Feeds")
    st.caption("Audit trail of all catalog scraping operations, execution times, and custom website scanner feeds.")

    col_diag1, col_diag2 = st.columns([2, 1])
    with col_diag2:
        st.markdown("#### Registered Custom Stores")
        c_sources = sources_data.get("custom", []) if sources_data else []
        if c_sources:
            for s in c_sources:
                st.markdown(f"• **{s['name']}** — `{s['url'][:30]}...`")
        else:
            st.caption("No custom stores added yet. Use the sidebar to add any competitor or brand store.")

    with col_diag1:
        st.markdown("#### Recent Scraping Job History")
        jobs = api_get("/api/scraper/jobs", {"limit": 20})

        if jobs:
            jobs_df = pd.DataFrame(jobs)
            for col in ['start_time', 'end_time', 'created_at']:
                if col in jobs_df.columns:
                    jobs_df[col] = jobs_df[col].apply(lambda x: x.replace('T', ' ').split('.')[0] if isinstance(x, str) else x)

            jobs_df = jobs_df.rename(columns={
                "job_type": "Job Type", "platforms": "Platforms",
                "status": "Status", "products_scraped": "Scraped",
                "products_new": "New SKUs", "products_updated": "Updated SKUs",
                "start_time": "Start Time", "end_time": "End Time",
                "error_log": "Diagnostic Errors"
            })

            st.dataframe(
                jobs_df.drop(columns=["id", "created_at"], errors='ignore'),
                use_container_width=True, hide_index=True
            )
        else:
            render_no_data("✦", "No Scrape Jobs Recorded", "Use the sidebar to run a live scrape.")
