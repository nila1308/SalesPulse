
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO, StringIO
import csv
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
import pandas as pd

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_file, Response, abort
)

from werkzeug.security import generate_password_hash, check_password_hash

from services.forecasting import forecast_product
from services.uci_database import get_uci_db, init_uci_db


# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Load local .env values without requiring python-dotenv.
# Render supplies its environment variables through the dashboard.
ENV_FILE = Path(BASE_DIR) / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("DATABASE_URL_POOLED")
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "local-development-key-change-before-deployment"
)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
# Initialize UCI database tables when the application starts
init_uci_db()
# =========================================================
# DATABASE CONNECTION
# =========================================================

@contextmanager
def get_db():
    """Open a PostgreSQL connection and commit/rollback safely."""
    if not DATABASE_URL:
        raise RuntimeError(
            "Database URL is missing. Set DATABASE_URL or "
            "DATABASE_URL_POOLED in your .env file / Render environment."
        )

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():
    """
    Verify the migrated Neon database is reachable.
    The schema and existing records were migrated already; do not reseed.
    """
    with get_db() as db:
        db.execute("SELECT 1")


# =========================================================
# AUTHENTICATION AND ROLE-BASED ACCESS CONTROL
# =========================================================

def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return fn(*args, **kwargs)

    return wrapper


def role_required(*allowed_roles):

    def decorator(fn):

        @wraps(fn)
        def wrapper(*args, **kwargs):

            if "user_id" not in session:
                return redirect(url_for("login"))

            if session.get("role") not in allowed_roles:
                abort(403)

            return fn(*args, **kwargs)

        return wrapper

    return decorator


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_db() as db:

            user = db.execute(
                "SELECT * FROM users WHERE username=%s",
                (username,)
            ).fetchone()

        if user and check_password_hash(
            user["password_hash"], password
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            return redirect(url_for("dashboard"))

        flash(
            "Incorrect username or password.",
            "danger"
        )

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(url_for("login"))


# =========================================================
# MAIN DASHBOARD
# =========================================================

@app.route("/")
@login_required
def dashboard():

    with get_db() as db:

        metrics = db.execute("""
            SELECT
                COALESCE(SUM(total), 0) revenue,
                COALESCE(SUM(quantity), 0) units,
                COUNT(DISTINCT product_id) products,
                COUNT(*) transactions
            FROM sales
        """).fetchone()

        best = db.execute("""
            SELECT
                p.name,
                SUM(s.quantity) units
            FROM sales s
            JOIN products p ON p.id = s.product_id
            GROUP BY p.id
            ORDER BY units DESC
            LIMIT 1
        """).fetchone()

        low_stock = db.execute(
            """
            SELECT COUNT(*) n
            FROM products
            WHERE stock <= reorder_level
            """
        ).fetchone()["n"]

        daily = db.execute("""
            SELECT
                sale_date,
                SUM(total) revenue
            FROM sales
            WHERE sale_date >= TO_CHAR(CURRENT_DATE - INTERVAL '29 days', 'YYYY-MM-DD')
            GROUP BY sale_date
            ORDER BY sale_date
        """).fetchall()

        category = db.execute("""
            SELECT
                p.category,
                SUM(s.total) revenue
            FROM sales s
            JOIN products p ON p.id = s.product_id
            GROUP BY p.category
            ORDER BY revenue DESC
        """).fetchall()

        recent = db.execute("""
            SELECT
                s.id,
                s.sale_date,
                p.name,
                s.quantity,
                s.total
            FROM sales s
            JOIN products p ON p.id = s.product_id
            ORDER BY s.sale_date DESC, s.id DESC
            LIMIT 7
        """).fetchall()

        products = db.execute(
            "SELECT * FROM products ORDER BY name"
        ).fetchall()

    return render_template(
        "dashboard.html",
        metrics=metrics,
        best=best,
        low_stock=low_stock,
        daily=daily,
        category=category,
        recent=recent,
        products=products
    )


# =========================================================
# ONLINE RETAIL DASHBOARD - SEPARATE UCI DATABASE
# =========================================================

@app.route("/online-retail")
@login_required
def online_retail():

    with get_uci_db() as db:

        metrics = db.execute("""
            SELECT
                COALESCE(SUM(line_total), 0) AS revenue,
                COALESCE(SUM(quantity), 0) AS units,
                COUNT(DISTINCT invoice_no) AS invoices,
                COUNT(DISTINCT stock_code) AS products
            FROM transactions
        """).fetchone()

        top_products = db.execute("""
            SELECT
                description,
                SUM(quantity) AS units,
                SUM(line_total) AS revenue
            FROM transactions
            GROUP BY stock_code, description
            ORDER BY units DESC
            LIMIT 10
        """).fetchall()

        country_sales = db.execute("""
            SELECT
                country,
                SUM(line_total) AS revenue
            FROM transactions
            GROUP BY country
            ORDER BY revenue DESC
            LIMIT 10
        """).fetchall()

        daily_sales = db.execute("""
            SELECT
                SUBSTR(invoice_date, 1, 10) AS sale_date,
                SUM(line_total) AS revenue
            FROM transactions
            GROUP BY sale_date
            ORDER BY sale_date
        """).fetchall()

    return render_template(
        "online_retail.html",
        metrics=metrics,
        top_products=top_products,
        country_sales=country_sales,
        daily_sales=daily_sales
    )
@app.route("/data-management")
@login_required
def data_management():

    with get_uci_db() as db:

        total_records = db.execute(
    "SELECT COUNT(*) AS total FROM transactions"
).fetchone()["total"]

        import_history = db.execute("""
            SELECT
                source_file,
                imported_at,
                total_rows,
                status
            FROM import_history
            ORDER BY id DESC
        """).fetchall()

        recent_transactions = db.execute("""
            SELECT *
            FROM transactions
            ORDER BY invoice_date DESC
            LIMIT 20
        """).fetchall()

    return render_template(
        "data_management.html",
        total_records=total_records,
        import_history=import_history,
        recent_transactions=recent_transactions
    )
@app.route("/sales-analytics")
@login_required
def sales_analytics():

    with get_db() as db:

        summary = db.execute("""
            SELECT
                COALESCE(SUM(total), 0) AS revenue,
                COALESCE(SUM(quantity), 0) AS units,
                COUNT(*) AS transactions,
                COUNT(DISTINCT product_id) AS products
            FROM sales
        """).fetchone()

        monthly_sales = db.execute("""
            SELECT
                SUBSTR(sale_date, 1, 7) AS month,
                SUM(total) AS revenue
            FROM sales
            GROUP BY month
            ORDER BY month
        """).fetchall()

        category_sales = db.execute("""
            SELECT
                p.category,
                SUM(s.total) AS revenue
            FROM sales s
            JOIN products p ON p.id = s.product_id
            GROUP BY p.category
            ORDER BY revenue DESC
        """).fetchall()

        top_products = db.execute("""
            SELECT
                p.name,
                SUM(s.quantity) AS units,
                SUM(s.total) AS revenue
            FROM sales s
            JOIN products p ON p.id = s.product_id
            GROUP BY p.id, p.name
            ORDER BY revenue DESC
            LIMIT 10
        """).fetchall()

    return render_template(
        "sales_analytics.html",
        summary=summary,
        monthly_sales=monthly_sales,
        category_sales=category_sales,
        top_products=top_products
    )

@app.route("/users", methods=["GET", "POST"])
@login_required
@role_required("admin")
def user_management():

    with get_db() as db:

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "").strip().lower()

            if not username or not password:
                flash("Username and password are required.", "danger")

            elif role not in ("admin", "manager", "analyst"):
                flash("Please select a valid user role.", "danger")

            elif len(password) < 6:
                flash("Password must contain at least 6 characters.", "danger")

            else:
                password_hash = generate_password_hash(password)

                inserted = db.execute(
                    """
                    INSERT INTO users (username, password_hash, role)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO NOTHING
                    """,
                    (username, password_hash, role)
                )

                if inserted.rowcount:
                    flash("User created successfully.", "success")
                else:
                    flash("That username already exists.", "danger")

        users = db.execute("""
            SELECT id, username, role
            FROM users
            ORDER BY id
        """).fetchall()

    return render_template(
        "users.html",
        users=users
    )

# =========================================================
# PRODUCT MANAGEMENT
# All roles can VIEW.
# Admin and Manager can ADD or EDIT.
# =========================================================

@app.route("/products", methods=["GET", "POST"])
@login_required
def products():

    with get_db() as db:

        if request.method == "POST":

            if session.get("role") not in ("admin", "manager"):
                abort(403)

            action = request.form.get("action")

            try:

                name = request.form["name"].strip()

                category = (
                    request.form.get("category", "General").strip()
                    or "General"
                )

                price = float(request.form["price"])
                stock = int(request.form["stock"])
                reorder = int(request.form["reorder_level"])

                if (
                    not name
                    or price < 0
                    or stock < 0
                    or reorder < 0
                ):
                    raise ValueError()

                if action == "update":

                    db.execute(
                        """
                        UPDATE products
                        SET name=%s, category=%s, price=%s,
                            stock=%s, reorder_level=%s
                        WHERE id=%s
                        """,
                        (
                            name,
                            category,
                            price,
                            stock,
                            reorder,
                            request.form["product_id"]
                        )
                    )

                    flash(
                        "Product updated.",
                        "success"
                    )

                else:

                    db.execute(
                        """
                        INSERT INTO products(
                            name, category, price, stock, reorder_level
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            name,
                            category,
                            price,
                            stock,
                            reorder
                        )
                    )

                    flash(
                        "Product added.",
                        "success"
                    )

            except (ValueError, KeyError):

                flash(
                    "Check the product details. Price, stock and "
                    "reorder level must be valid.",
                    "danger"
                )

            return redirect(url_for("products"))

        rows = db.execute(
            "SELECT * FROM products ORDER BY name"
        ).fetchall()

    return render_template(
        "products.html",
        products=rows
    )


# =========================================================
# DELETE PRODUCT - ADMIN ONLY
# =========================================================

@app.route("/products/delete/<int:pid>", methods=["POST"])
@login_required
@role_required("admin")
def delete_product(pid):

    with get_db() as db:

        db.execute(
            "DELETE FROM products WHERE id=%s",
            (pid,)
        )

    flash(
        "Product deleted along with its related sales and forecasts.",
        "info"
    )

    return redirect(url_for("products"))


# =========================================================
# SALES MANAGEMENT
# All roles can VIEW.
# Admin and Manager can ADD sales.
# =========================================================

@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():

    with get_db() as db:

        if request.method == "POST":

            if session.get("role") not in ("admin", "manager"):
                abort(403)

            try:

                pid = int(request.form["product_id"])
                date = request.form["sale_date"]
                qty = int(request.form["quantity"])
                price = float(request.form["unit_price"])

                datetime.strptime(date, "%Y-%m-%d")

                if qty <= 0 or price < 0:
                    raise ValueError()

                exists = db.execute(
                    "SELECT id FROM products WHERE id=%s",
                    (pid,)
                ).fetchone()

                if not exists:
                    raise ValueError()

                db.execute(
                    """
                    INSERT INTO sales(
                        product_id, sale_date,
                        quantity, unit_price, total
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        pid,
                        date,
                        qty,
                        price,
                        qty * price
                    )
                )

                db.execute(
                    """
                    UPDATE products
                    SET stock=GREATEST(0, stock-%s)
                    WHERE id=%s
                    """,
                    (qty, pid)
                )

                flash(
                    "Sales transaction saved and stock updated.",
                    "success"
                )

            except (ValueError, KeyError):

                flash(
                    "Please enter a valid product, date, quantity and price.",
                    "danger"
                )

            return redirect(url_for("sales"))

        rows = db.execute("""
            SELECT
                s.*,
                p.name product_name
            FROM sales s
            JOIN products p ON p.id = s.product_id
            ORDER BY s.sale_date DESC, s.id DESC
            LIMIT 250
        """).fetchall()

        products_list = db.execute(
            "SELECT * FROM products ORDER BY name"
        ).fetchall()

    return render_template(
        "sales.html",
        sales=rows,
        products=products_list
    )


# =========================================================
# SALES CSV IMPORT - ADMIN AND MANAGER ONLY
# =========================================================

@app.route("/sales/upload", methods=["POST"])
@login_required
@role_required("admin", "manager")
def upload_sales():

    file = request.files.get("csv_file")

    if not file or not file.filename.lower().endswith(".csv"):

        flash(
            "Choose a .csv file.",
            "danger"
        )

        return redirect(url_for("sales"))

    try:

        df = pd.read_csv(file)

        required = {
            "product_id",
            "sale_date",
            "quantity",
            "unit_price"
        }

        if not required.issubset(set(df.columns)):

            raise ValueError(
                "CSV must contain product_id, sale_date, "
                "quantity and unit_price columns."
            )

        inserted = 0

        with get_db() as db:

            for _, row in df.iterrows():

                pid = int(row["product_id"])
                qty = int(row["quantity"])
                price = float(row["unit_price"])

                date = pd.to_datetime(
                    row["sale_date"]
                ).date().isoformat()

                if (
                    qty <= 0
                    or price < 0
                    or not db.execute(
                        "SELECT id FROM products WHERE id=%s",
                        (pid,)
                    ).fetchone()
                ):

                    raise ValueError(
                        "A row contains an invalid product, quantity or price."
                    )

                db.execute(
                    """
                    INSERT INTO sales(
                        product_id, sale_date,
                        quantity, unit_price, total
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        pid,
                        date,
                        qty,
                        price,
                        qty * price
                    )
                )

                db.execute(
                    """
                    UPDATE products
                    SET stock=GREATEST(0, stock-%s)
                    WHERE id=%s
                    """,
                    (qty, pid)
                )

                inserted += 1

        flash(
            f"Imported {inserted} sales rows.",
            "success"
        )

    except Exception as exc:

        flash(
            f"Import failed: {exc}",
            "danger"
        )

    return redirect(url_for("sales"))


# =========================================================
# FORECASTING
# All three roles can generate forecasts.
# =========================================================


@app.route("/forecast", methods=["GET", "POST"])
@login_required
def forecast():

    result = None
    selected_product = request.form.get("product_id", "")
    model = request.form.get("model", "Moving Average")

    try:
        horizon = int(request.form.get("horizon", 30))
    except (ValueError, TypeError):
        horizon = 30

    with get_db() as db:

        product_rows = db.execute(
            "SELECT * FROM products ORDER BY name"
        ).fetchall()

        if request.method == "POST":

            try:
                if not selected_product:
                    raise ValueError("Please select a product.")

                pid = int(selected_product)

                p = db.execute(
                    "SELECT * FROM products WHERE id = %s",
                    (pid,)
                ).fetchone()

                if not p:
                    raise ValueError("Selected product was not found.")

                history_rows = db.execute(
                    """
                    SELECT
                        sale_date,
                        SUM(quantity) AS quantity
                    FROM sales
                    WHERE product_id = %s
                    GROUP BY sale_date
                    ORDER BY sale_date
                    """,
                    (pid,)
                ).fetchall()

                history = pd.DataFrame(
                    history_rows,
                    columns=["sale_date", "quantity"]
                )

                result = forecast_product(
                    history,
                    model,
                    horizon
                )

                # Preserve forecasts generated by other models.
                db.execute(
                    """
                    DELETE FROM forecasts
                    WHERE product_id = %s AND model = %s
                    """,
                    (pid, model)
                )

                for item in result["rows"]:
                    db.execute(
                        """
                        INSERT INTO forecasts (
                            product_id,
                            model,
                            forecast_date,
                            predicted_quantity
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            pid,
                            model,
                            item["date"],
                            item["prediction"]
                        )
                    )

                result["product_name"] = p["name"]

            except (ValueError, TypeError) as exc:
                flash(
                    f"Could not generate forecast: {exc}",
                    "danger"
                )

            except Exception as exc:
                flash(
                    f"Forecast generation failed: {exc}",
                    "danger"
                )

    return render_template(
        "forecast.html",
        products=product_rows,
        result=result,
        selected_product=selected_product,
        selected_model=model,
        horizon=horizon
    )


# =========================================================
# INVENTORY
# =========================================================

@app.route("/inventory")
@login_required
def inventory():

    with get_db() as db:

        rows = db.execute("""
            SELECT
                p.*,
                COALESCE(
                    (
                        SELECT SUM(quantity)
                        FROM sales s
                        WHERE s.product_id=p.id
                        AND s.sale_date >= TO_CHAR(CURRENT_DATE - INTERVAL '30 days', 'YYYY-MM-DD')
                    ),
                    0
                ) recent_units
            FROM products p
            ORDER BY
                (p.stock <= p.reorder_level) DESC,
                p.name
        """).fetchall()

    return render_template(
        "inventory.html",
        products=rows
    )


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
@login_required
def reports():

    with get_db() as db:

        rows = db.execute("""
            SELECT
                p.name,
                p.category,
                COUNT(s.id) transactions,
                COALESCE(SUM(s.quantity), 0) units,
                COALESCE(SUM(s.total), 0) revenue
            FROM products p
            LEFT JOIN sales s ON s.product_id=p.id
            GROUP BY p.id
            ORDER BY revenue DESC
        """).fetchall()

    return render_template(
        "reports.html",
        rows=rows
    )


# =========================================================
# CSV EXPORT
# =========================================================

@app.route("/export/sales.csv")
@login_required
def export_sales():

    with get_db() as db:

        rows = db.execute("""
            SELECT
                s.id,
                s.sale_date,
                p.id product_id,
                p.name product_name,
                s.quantity,
                s.unit_price,
                s.total
            FROM sales s
            JOIN products p ON p.id=s.product_id
            ORDER BY s.sale_date
        """).fetchall()

    output = StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "sale_id",
        "sale_date",
        "product_id",
        "product_name",
        "quantity",
        "unit_price",
        "total"
    ])

    writer.writerows([
        tuple(r.values()) for r in rows
    ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=sales_report.csv"
        }
    )


# =========================================================
# PDF REPORT EXPORT
# =========================================================

@app.route("/export/report.pdf")
@login_required
def export_pdf():

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet

    with get_db() as db:

        rows = db.execute("""
            SELECT
                p.name,
                p.category,
                COALESCE(SUM(s.quantity), 0) AS units,
                COALESCE(SUM(s.total), 0) AS revenue
            FROM products p
            LEFT JOIN sales s ON s.product_id=p.id
            GROUP BY p.id
            ORDER BY p.name
        """).fetchall()

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4)
    )

    styles = getSampleStyleSheet()

    data = [
        ["Product", "Category", "Units sold", "Revenue"]
    ] + [
        [
            r["name"],
            r["category"],
            str(r["units"]),
            f"₹{r['revenue']:,.2f}"
        ]
        for r in rows
    ]

    table = Table(
        data,
        repeatRows=1
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#263b80")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#dce2ef")
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#f2f5fb")
                ]
            ),
            (
                "PADDING",
                (0, 0),
                (-1, -1),
                8
            )
        ])
    )

    doc.build([
        Paragraph(
            "Sales Demand Forecasting – Product Report",
            styles["Title"]
        ),
        Spacer(1, 16),
        table
    ])

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="sales_report.pdf",
        mimetype="application/pdf"
    )


# =========================================================
# BUSINESS INSIGHTS
# =========================================================

@app.route("/insights")
@login_required
def insights():

    with get_db() as db:

        rows = db.execute("""
            SELECT
                p.name,
                p.stock,
                p.reorder_level,
                COALESCE(SUM(s.quantity), 0) units
            FROM products p
            LEFT JOIN sales s
                ON s.product_id=p.id
                AND s.sale_date >= TO_CHAR(CURRENT_DATE - INTERVAL '30 days', 'YYYY-MM-DD')
            GROUP BY p.id
            ORDER BY units DESC
        """).fetchall()

    cards = []

    for r in rows:

        if r["stock"] <= r["reorder_level"]:

            cards.append((
                r["name"],
                "Low stock",
                (
                    f"Current stock is {r['stock']}; "
                    f"reorder level is {r['reorder_level']}."
                ),
                "warning"
            ))

        elif r["units"] > 50:

            cards.append((
                r["name"],
                "Strong recent demand",
                f"{r['units']} units sold in the last 30 days.",
                "success"
            ))

        elif r["units"] == 0:

            cards.append((
                r["name"],
                "No recent sales",
                "No sales were recorded in the last 30 days.",
                "secondary"
            ))

    return render_template(
        "insights.html",
        insights=cards
    )


# =========================================================
# APPLICATION START
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False,
        use_reloader=False
    )
