# SalesPulse – Sales Demand Forecasting DSS

A local Flask + SQLite starter application for sales management, dashboards, demand forecasting, inventory alerts and reports.

## Requirements
- Python 3.10 or newer
- Visual Studio Code
- VS Code Python extension

## Run on Windows
Open this folder in VS Code, then open **Terminal → New Terminal**.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, use Command Prompt terminal:
```bat
.venv\Scripts\activate.bat
```

Open `http://127.0.0.1:5000` in your browser.

## Demo login
- Username: `admin`
- Password: `admin123`

Change the demo password and Flask `SECRET_KEY` before using this outside a private development environment.

## First steps
1. Open Products and note the product IDs (visible in the URL only indirectly; use SQLite Browser or add IDs to your workflow as needed).
2. Add or edit products.
3. Add sales manually or import a CSV.
4. Open Demand forecast and select a product and model.
5. Review Inventory, Business insights and Reports.

## CSV format
The importer expects these exact column names:
```csv
product_id,sale_date,quantity,unit_price
1,2026-01-01,5,599
2,2026-01-01,12,80
```
Dates should be `YYYY-MM-DD`. The product IDs must already exist in the Products table. A sample file is included as `sample_sales.csv` (IDs 1–5 after the starter database is first initialized).

## Database
The SQLite file is created automatically at `database/sales_dss.db` when you first run the app. Sample products and sales are inserted only when the database is empty.

## Notes
- The included forecasting methods are educational baseline models, not guaranteed business forecasts.
- At least seven daily observations are required for a forecast. More history generally produces more useful results.
- The UI loads Bootstrap, Bootstrap Icons, Chart.js and Google Fonts from CDNs, so those visual assets need an internet connection. Flask, SQLite and forecasting run locally.
- The starter has a single demo administrator account. Add production-grade user administration, CSRF protection, stronger secret management, backups and deployment hardening before real business use.
