# Kurti Manufacturing Management System

## 📋 Project Overview

A comprehensive Streamlit-based web application for managing a kurti manufacturing store and meshop shop business. The system tracks materials, workers, production, sales, inventory, and payments with automated alerts and reporting.

## 🎯 Business Purpose

This application automates key operational tasks for a kurti manufacturing business:

1. **Material/Cloth Tracking** - Track incoming cloth, usage per kurti, wastage, and inventory levels
2. **Worker Payment Management** - Log daily hours/pieces, auto-calculate salaries based on time and piece-rate
3. **Inventory Run-Out Alerts** - 3-day advance warning when raw materials will run out
4. **Production Tracking** - Record kurtis produced per design, track cloth consumption and revenue
5. **Daily Business Summaries** - Comprehensive daily/weekly reports with analytics
6. **Sales Integration** - Track meshop platform sales and compare with production
7. **Event Period Demand Forecasting** - Seasonal demand multipliers (default 1.5x, adjustable)

## 🏗️ Architecture

### Tech Stack
- **Framework**: Streamlit (Python)
- **Database**: SQLite (local file: kurti_business.db)
- **Visualization**: Plotly, Pandas
- **Deployment**: Ready for Streamlit Cloud / GitHub Pages

### File Structure
```
kurti_business/
├── app.py                        # Main application entry point
├── database.py                   # SQLite database initialization
├── kurti_business.db             # Runtime database (created on first run)
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── pages/                        # Individual page modules
│   ├── dashboard.py
│   ├── materials.py
│   ├── workers.py
│   ├── production.py
│   ├── sales.py
│   ├── inventory.py
│   ├── payments.py
│   ├── reports.py
│   └── settings.py
└── .streamlit/                   # Streamlit configuration (optional)
```

## 🚀 Quick Start

### Prerequisites
```bash
pip install -r requirements.txt
```

### Run Locally
```bash
streamlit run app.py
```

### Access the App
- **Local**: http://localhost:8501
- **Network**: http://192.168.0.104:8501
- **External**: http://your-external-ip:8501

### First-Time Setup
1. Complete the initial form with username, password, name, email
2. Define event periods (e.g., "Festival Season", "Off Season")
3. Set default demand multiplier (1.5x by default, adjustable)
4. Add materials, workers, and start recording daily operations

## 📦 Python Dependencies (requirements.txt)

```text
streamlit>=1.62.0
plotly>=5.0.0
pandas>=2.0.0
sqlite3 (built-in)
```

## 🎨 Key Features

### User Onboarding
- Initial setup questions at first login (workers count, hourly rates, cloth per kurti, wastage %)
- Role-based access (admin/worker/vendor)
- Business parameter configuration

### Material Management
- Add materials (cotton, silk, printed, linen, etc.)
- Track quantity, supplier, cost per unit
- Daily cloth usage recording with auto-inventory deduction
- Consumption history and charts

### Worker Management
- Log hours worked and pieces completed per worker daily
- Auto-salary calculation: (hours × rate) + (pieces × piece-rate)
- Payment status tracking (paid/unpaid)
- Salary history per worker

### Production Tracking
- Record kurtis produced per design (Anarkali, A-line, Straight, etc.)
- Track cloth used, wastage percentage, sale price
- Auto-revenue calculation: quantity × sale price
- Per-design analytics: total pieces, revenue, cloth consumption, profit margins

### Event Period & Demand Forecasting *(YOUR SPECIFIC REQUEST)*
- Define event periods (festive season, off-season, etc.)
- **Default demand multiplier: 1.5x** (as specified)
- User-adjustable toggle: increase to 2.0-3.0 during peak seasons
- System auto-adjusts inventory consumption predictions based on current period
- Internet-derived demand patterns affect stockout predictions

### Sales & Meshop Integration
- Enter daily sales with quantity, price, and meshop reference ID
- Sales vs production comparison analytics
- Fulfillment rate analysis (made vs sold)
- Revenue efficiency tracking

### Inventory Management
- Real-time stock levels for all materials
- **3-day advance low stock alerts** (critical/warning/ok)
- Demand multiplier adjustment during event periods
- Emergency order generation
- Manual stock adjustments for wastage/damage

### Payment System
- Worker salaries: pending/paid status
- Vendor payments tracking
- Outstanding balance summary
- Payment history for audit

### Reporting & Analytics
- Daily business summaries
- Weekly production & sales analytics with interactive charts
- Profit & Loss analysis
- Key Performance Indicators (KPIs)
- Export to CSV

### Settings & Business Rules
- Edit event periods and demand multipliers
- Configure business parameters (cloth per kurti, piece rate, hourly rate)
- User profile management
- Guidelines and how-to documentation

## 🗂️ Project Location

**Current Directory**: `C:\Users\divya\OneDrive\Documents\Default Project`

**Full Path**: `C:\Users\divya\OneDrive\Documents\Default Project\`

**Database**: `C:\Users\divya\OneDrive\Documents\Default Project\kurti_business.db`

## 🔧 Customization

### Adding New Features
1. Create new page file in `pages/` directory
2. Add corresponding navigation in `app.py` sidebar
3. Update database schema in `database.py` if needed

### Modifying Demand Multiplier
- Go to ⚙️ Settings → Event Periods
- Adjust the demand multiplier slider
- Default: 1.5x, adjustable between 1.0-3.0

### Changing Business Parameters
- Go to ⚙️ Settings → Business Configuration
- Modify: cloth per kurti, piece rate, hourly rate, low stock threshold

## 🚢 Deployment

### Streamlit Cloud
1. Push to GitHub repository
2. Connect to Streamlit Cloud
3. Set main file: `app.py`
4. Environment variables automatically included

### Local Network
- Access via network IP: `http://192.168.0.x:8501`
- Ensure firewall allows port 8501/8502

## 📞 Support

For modifications or additional features:
- Edit page files in `pages/` directory
- Modify `database.py` for schema changes
- Update `app.py` for new navigation items

---

**Built with ❤️ for Kurti Manufacturing Business**