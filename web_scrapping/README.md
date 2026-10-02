# Web-Scrapper & Kurti Trend Intelligence Platform

An end-to-end multi-source fashion intelligence & web scraping platform for tracking, scraping, and analyzing trending Kurtis across e-commerce marketplaces and direct-to-consumer brand stores.

---

## 🌟 Key Features

- **Multi-Source Web Scraping**:
  - **E-Commerce Marketplaces**: Automated scraping capabilities for Myntra, Flipkart, Amazon, and Meesho.
  - **D2C Brand Stores**: Shopify JSON catalog & HTML parser for top ethnic fashion brands (Libas, Biba, Nykaa Fashion, Aarsi, etc.).
  - **Custom Website Scanner**: Add and scan any custom fashion website / Shopify store dynamically from the dashboard.
- **Trend Intelligence & Scoring Engine**:
  - Algorithmic Trend Velocity Score calculation (Velocity 35%, Review Volume 20%, Rating 20%, Recency 15%, Price 10%).
  - NLP-powered attribute extraction (Fabrics, Necklines, Sleeve types, Silhouette, Patterns, Occasions).
- **Executive Analytics Dashboard**:
  - **Dual Theme Support**: ☀️ Light Mode & 🌙 Dark Mode with instant toggle.
  - **Factor Breakdown Modal**: Inspect verified review counts, active days, and scoring weight trajectory.
  - **Saved Portfolio**: 1-click bookmarking, comparison matrix, and CSV exports.
  - **Price Elasticity & Demand Matrix**: Strategic pricing sweet spots and attribute demand vs saturation analysis.

---

## 🏗️ Architecture & Tech Stack

- **Backend**: Python 3.10+, FastAPI, SQLite, SQLAlchemy, BeautifulSoup4, Requests, Playwright/Browser Scraper.
- **Frontend**: Streamlit, Plotly, Altair, Modern CSS Design System.
- **Data Engine**: SQLite database (`kurti_trend_intelligence.db`) with automated schema migrations and daily time-series metrics.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd kurti_trend_platform
pip install -r requirements.txt
```

### 2. Launch Backend & Frontend
Run the unified launcher:
```bash
python run.py
```
Or use the batch script on Windows:
```cmd
start.bat
```

- **Frontend Dashboard**: `http://localhost:8501`
- **FastAPI Documentation**: `http://127.0.0.1:8000/docs`

---

## 📁 Repository Structure

```
├── kurti_trend_platform/
│   ├── backend/
│   │   ├── scrapers/          # Marketplace, brand, & browser scrapers
│   │   ├── config.py          # Configuration & environment settings
│   │   ├── database.py        # SQLite schema, migrations, & CRUD operations
│   │   ├── main.py            # FastAPI REST API endpoints
│   │   └── scoring_engine.py  # Trend scoring & NLP attribute algorithms
│   ├── frontend/
│   │   └── app.py             # Streamlit Executive Intelligence Dashboard
│   ├── run.py                 # Unified launcher for API & Frontend
│   ├── start.bat              # Windows one-click start script
│   └── requirements.txt       # Python dependencies
├── Web_scrapper/              # Standalone Aarsi tracker & scraper
└── README.md
```
