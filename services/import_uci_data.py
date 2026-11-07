
import pandas as pd
from pathlib import Path
from datetime import datetime
from uci_database import get_uci_db, init_uci_db

BASE_DIR = Path(__file__).resolve().parent.parent
EXCEL_PATH = BASE_DIR / "data" / "online_retail.xlsx"


def import_excel_data():
    if not EXCEL_PATH.exists():
        print("Excel file not found:", EXCEL_PATH)
        return

    # Initialize the separate Online Retail database
    init_uci_db()

    # Read Excel data
    df = pd.read_excel(EXCEL_PATH)

    # Check required columns
    required_columns = [
        "InvoiceNo", "StockCode", "Description",
        "Quantity", "InvoiceDate", "UnitPrice",
        "CustomerID", "Country", "LineTotal"
    ]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        print("Missing columns:", missing)
        return

    conn = get_uci_db()

    try:
        existing = conn.execute(
            "SELECT COUNT(*) FROM transactions"
        ).fetchone()[0]

        if existing > 0:
            print(f"Database already contains {existing} records.")
            print("Import stopped to prevent duplicate records.")
            return

        records = []

        for _, row in df.iterrows():
            invoice_date = pd.to_datetime(row["InvoiceDate"])

            customer_id = (
                None if pd.isna(row["CustomerID"])
                else str(int(row["CustomerID"]))
            )

            records.append((
                str(row["InvoiceNo"]),
                str(row["StockCode"]),
                str(row["Description"]),
                int(row["Quantity"]),
                invoice_date.strftime("%Y-%m-%d %H:%M:%S"),
                float(row["UnitPrice"]),
                customer_id,
                str(row["Country"]),
                float(row["LineTotal"])
            ))

        conn.executemany("""
            INSERT INTO transactions (
                invoice_no, stock_code, description,
                quantity, invoice_date, unit_price,
                customer_id, country, line_total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

        conn.execute("""
            INSERT INTO import_history (
                source_file, imported_at, total_rows, status
            )
            VALUES (?, ?, ?, ?)
        """, (
            EXCEL_PATH.name,
            datetime.now().isoformat(timespec="seconds"),
            len(records),
            "SUCCESS"
        ))

        conn.commit()

        print("Excel import completed successfully!")
        print("Records imported:", len(records))

    except Exception as error:
        conn.rollback()
        print("Import failed:", error)

    finally:
        conn.close()


if __name__ == "__main__":
    import_excel_data()
