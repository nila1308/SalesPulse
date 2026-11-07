
import os
import pandas as pd
from pathlib import Path
from datetime import datetime

try:
    from .uci_database import get_uci_db, init_uci_db
except ImportError:
    from uci_database import get_uci_db, init_uci_db


BASE_DIR = Path(__file__).resolve().parent.parent
EXCEL_PATH = BASE_DIR / "data" / "online_retail.xlsx"
ENV_PATH = BASE_DIR / ".env"


# Load local environment variables when running the script manually.
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")

        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'")
        )


def import_excel_data():

    if not EXCEL_PATH.exists():
        print("Excel file not found:", EXCEL_PATH)
        return

    try:
        # Create UCI tables in Neon if they do not exist.
        init_uci_db()

        # Read Excel dataset.
        df = pd.read_excel(EXCEL_PATH)

        required_columns = [
            "InvoiceNo", "StockCode", "Description",
            "Quantity", "InvoiceDate", "UnitPrice",
            "CustomerID", "Country", "LineTotal"
        ]

        missing = [
            col for col in required_columns
            if col not in df.columns
        ]

        if missing:
            raise ValueError(f"Missing columns: {missing}")

        conn = get_uci_db()

        try:
            existing = conn.execute(
                "SELECT COUNT(*) AS total FROM transactions"
            ).fetchone()["total"]

            if existing > 0:
                print(
                    f"Neon already contains {existing} UCI records."
                )
                print("Import stopped to prevent duplicates.")
                return

            records = []

            for _, row in df.iterrows():

                invoice_date = pd.to_datetime(
                    row["InvoiceDate"]
                )

                customer_id = (
                    None
                    if pd.isna(row["CustomerID"])
                    else str(int(row["CustomerID"]))
                )

                description = (
                    None if pd.isna(row["Description"])
                    else str(row["Description"])
                )

                records.append((
                    str(row["InvoiceNo"]),
                    str(row["StockCode"]),
                    description,
                    int(row["Quantity"]),
                    invoice_date.strftime("%Y-%m-%d %H:%M:%S"),
                    float(row["UnitPrice"]),
                    customer_id,
                    str(row["Country"]),
                    float(row["LineTotal"])
                ))

            insert_sql = """
                INSERT INTO transactions (
                    invoice_no, stock_code, description,
                    quantity, invoice_date, unit_price,
                    customer_id, country, line_total
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            with conn.cursor() as cursor:
                cursor.executemany(insert_sql, records)

            conn.execute("""
                INSERT INTO import_history (
                    source_file, imported_at, total_rows, status
                )
                VALUES (%s, %s, %s, %s)
            """, (
                EXCEL_PATH.name,
                datetime.now().isoformat(timespec="seconds"),
                len(records),
                "SUCCESS"
            ))

            conn.commit()

            print("\nExcel import completed successfully!")
            print("Records imported:", len(records))

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    except Exception as error:
        print("Import failed:", error)


if __name__ == "__main__":
    import_excel_data()
