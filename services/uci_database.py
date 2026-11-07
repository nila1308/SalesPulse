
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "online_retail.db"


def get_uci_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def init_uci_db():
    conn = get_uci_db()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT,
                stock_code TEXT,
                description TEXT,
                quantity INTEGER,
                invoice_date TEXT,
                unit_price REAL,
                customer_id TEXT,
                country TEXT,
                line_total REAL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                total_rows INTEGER NOT NULL,
                status TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_uci_invoice_date
            ON transactions(invoice_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_uci_stock_code
            ON transactions(stock_code)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_uci_country
            ON transactions(country)
        """)

        conn.commit()
        print("UCI database tables created successfully.")

    finally:
        conn.close()


if __name__ == "__main__":
    init_uci_db()
