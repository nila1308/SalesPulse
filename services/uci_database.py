
import os
import psycopg
from psycopg.rows import dict_row


def get_uci_db():
    """
    Connect to the Neon PostgreSQL database.
    Uses the same DATABASE_URL as the main SalesPulse app.
    """

    database_url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("DATABASE_URL_POOLED")
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL was not found. Check your environment variables."
        )

    conn = psycopg.connect(
        database_url,
        row_factory=dict_row
    )

    return conn


def init_uci_db():
    """
    Create UCI Online Retail tables in Neon.
    Existing records and tables are preserved.
    """

    conn = get_uci_db()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id BIGSERIAL PRIMARY KEY,
                invoice_no TEXT,
                stock_code TEXT,
                description TEXT,
                quantity INTEGER,
                invoice_date TEXT,
                unit_price DOUBLE PRECISION,
                customer_id TEXT,
                country TEXT,
                line_total DOUBLE PRECISION
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id BIGSERIAL PRIMARY KEY,
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

        print("UCI PostgreSQL tables initialized successfully.")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    init_uci_db()
