import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


load_dotenv()


# --------------------------------------------------
# 1. Find the latest raw CFPB CSV file
# --------------------------------------------------

raw_directory = Path("data/raw")

raw_files = list(
    raw_directory.glob("cfpb_complaints_raw_*.csv")
)

if not raw_files:
    raise FileNotFoundError(
        "No CFPB raw CSV file found in data/raw."
    )

latest_file = max(
    raw_files,
    key=lambda file: file.stat().st_mtime
)

print("\nRaw file selected:")
print(latest_file)


# --------------------------------------------------
# 2. Read raw CSV
# --------------------------------------------------

df = pd.read_csv(
    latest_file,
    dtype=str
)

print("\nRows read from CSV:", len(df))
print("Columns read:", len(df.columns))


# Replace pandas NaN values with Python None
df = df.astype(object).where(
    pd.notna(df),
    None
)


# --------------------------------------------------
# 3. Add ingestion metadata
# --------------------------------------------------

df["source_file"] = latest_file.name


# --------------------------------------------------
# 4. Connect to PostgreSQL
# --------------------------------------------------

connection = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

cursor = connection.cursor()


try:

    # --------------------------------------------------
    # 5. Safety check
    # --------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM raw.cfpb_complaints;
        """
    )

    existing_rows = cursor.fetchone()[0]

    print(
        "\nExisting rows in raw.cfpb_complaints:",
        existing_rows
    )

    if existing_rows > 0:
        raise RuntimeError(
            "raw.cfpb_complaints already contains data. "
            "Load stopped to prevent accidental duplicates."
        )


    # --------------------------------------------------
    # 6. Columns to insert
    # --------------------------------------------------

    columns = [
        "product",
        "complaint_what_happened",
        "date_sent_to_company",
        "issue",
        "sub_product",
        "zip_code",
        "tags",
        "has_narrative",
        "complaint_id",
        "timely",
        "company_response",
        "submitted_via",
        "company",
        "date_received",
        "state",
        "company_public_response",
        "sub_issue",
        "source_file"
    ]


    records = [
        tuple(row)
        for row in df[columns].itertuples(
            index=False,
            name=None
        )
    ]


    # --------------------------------------------------
    # 7. Insert records
    # --------------------------------------------------

    insert_sql = """
        INSERT INTO raw.cfpb_complaints
        (
            product,
            complaint_what_happened,
            date_sent_to_company,
            issue,
            sub_product,
            zip_code,
            tags,
            has_narrative,
            complaint_id,
            timely,
            company_response,
            submitted_via,
            company,
            date_received,
            state,
            company_public_response,
            sub_issue,
            source_file
        )
        VALUES %s
    """


    execute_values(
        cursor,
        insert_sql,
        records,
        page_size=500
    )

    connection.commit()


    print("\nLoad completed successfully.")


    # --------------------------------------------------
    # 8. Validation
    # --------------------------------------------------

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT complaint_id)
                AS unique_complaints
        FROM raw.cfpb_complaints;
        """
    )

    total_rows, unique_complaints = (
        cursor.fetchone()
    )

    duplicates = (
        total_rows - unique_complaints
    )


    print("\n==============================")
    print("POSTGRESQL LOAD VALIDATION")
    print("==============================")

    print("Total database rows:", total_rows)
    print(
        "Unique complaint IDs:",
        unique_complaints
    )
    print(
        "Duplicate complaint IDs:",
        duplicates
    )


except Exception:

    connection.rollback()
    raise


finally:

    cursor.close()
    connection.close()

    print("\nDatabase connection closed.")