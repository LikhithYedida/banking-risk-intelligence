import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

RAW_DIRECTORY = Path("data/raw")

EXPECTED_ROWS = 50_000

BATCH_SIZE = 1_000


# ============================================================
# 1. FIND LATEST RAW CFPB FILE
# ============================================================

raw_files = list(
    RAW_DIRECTORY.glob(
        "cfpb_complaints_raw_*.csv"
    )
)

if not raw_files:
    raise FileNotFoundError(
        "No CFPB raw CSV file found in data/raw."
    )

latest_file = max(
    raw_files,
    key=lambda file: file.stat().st_mtime,
)

print(
    "\n========================================"
)
print(
    "POSTGRESQL RAW LOAD"
)
print(
    "========================================"
)

print(
    "\nRaw file selected:"
)
print(
    latest_file
)


# ============================================================
# 2. READ RAW CSV
# ============================================================

df = pd.read_csv(
    latest_file,
    dtype=str,
    low_memory=False,
)

print(
    f"\nRows read from CSV: {len(df):,}"
)

print(
    f"Columns read: {len(df.columns)}"
)


# ============================================================
# 3. VALIDATE RAW FILE
# ============================================================

required_columns = {
    "product",
    "complaint_what_happened",
    "date_sent_to_company",
    "issue",
    "sub_product",
    "zip_code",
    "tags",
    "complaint_id",
    "timely",
    "company_response",
    "submitted_via",
    "company",
    "date_received",
    "state",
    "company_public_response",
    "sub_issue",
}

missing_columns = (
    required_columns
    - set(df.columns)
)

if missing_columns:
    raise ValueError(
        "Required columns are missing from "
        f"the raw CSV: {sorted(missing_columns)}"
    )


# Require the portfolio-scale dataset.
if len(df) != EXPECTED_ROWS:
    raise ValueError(
        f"Expected {EXPECTED_ROWS:,} rows "
        f"but found {len(df):,}. "
        "PostgreSQL load stopped."
    )


# ============================================================
# 4. DERIVE has_narrative
# ============================================================

narrative_text = (
    df["complaint_what_happened"]
    .fillna("")
    .astype(str)
    .str.strip()
)

df["has_narrative"] = (
    narrative_text.ne("")
)


# ============================================================
# 5. DATA QUALITY CHECKS
# ============================================================

complaint_ids = (
    df["complaint_id"]
    .fillna("")
    .astype(str)
    .str.strip()
)

missing_ids = (
    complaint_ids.eq("").sum()
)

duplicate_ids = (
    complaint_ids.duplicated().sum()
)

unique_ids = (
    complaint_ids.nunique()
)

print(
    "\n========================================"
)
print(
    "PRE-LOAD DATA QUALITY CHECK"
)
print(
    "========================================"
)

print(
    f"Rows: {len(df):,}"
)

print(
    f"Unique complaint IDs: {unique_ids:,}"
)

print(
    f"Duplicate complaint IDs: {duplicate_ids:,}"
)

print(
    f"Missing complaint IDs: {missing_ids:,}"
)


if missing_ids > 0:
    raise ValueError(
        "Missing complaint IDs detected. "
        "Database load stopped."
    )

if duplicate_ids > 0:
    raise ValueError(
        "Duplicate complaint IDs detected. "
        "Database load stopped."
    )


# ============================================================
# 6. ADD INGESTION METADATA
# ============================================================

df["source_file"] = (
    latest_file.name
)


# ============================================================
# 7. CONVERT NaN TO PYTHON None
# ============================================================

df = df.astype(object).where(
    pd.notna(df),
    None,
)


# ============================================================
# 8. DATABASE CONNECTION
# ============================================================

required_environment_variables = [
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
]

missing_environment_variables = [
    variable
    for variable in required_environment_variables
    if not os.getenv(variable)
]

if missing_environment_variables:
    raise RuntimeError(
        "Missing database environment variables: "
        f"{missing_environment_variables}"
    )


connection = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)

cursor = connection.cursor()


try:

    # ========================================================
    # 9. CHECK CURRENT DATABASE STATE
    # ========================================================

    cursor.execute(
        """
        SELECT
            COUNT(*)
        FROM raw.cfpb_complaints;
        """
    )

    existing_rows = (
        cursor.fetchone()[0]
    )

    print(
        "\nExisting rows in "
        f"raw.cfpb_complaints: {existing_rows:,}"
    )

    print(
        "The existing development dataset "
        "will be replaced with the validated "
        "50,000-row dataset."
    )


    # ========================================================
    # 10. PREPARE INSERT COLUMNS
    # ========================================================

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
        "source_file",
    ]


    records = list(
        df[columns].itertuples(
            index=False,
            name=None,
        )
    )


    # ========================================================
    # 11. TRANSACTION-SAFE REPLACEMENT
    # ========================================================

    # PostgreSQL TRUNCATE participates in the current
    # transaction. If anything below fails, rollback()
    # restores the previous table state.

    print(
        "\nClearing existing raw table..."
    )

    cursor.execute(
        """
        TRUNCATE TABLE
            raw.cfpb_complaints
        RESTART IDENTITY;
        """
    )


    # ========================================================
    # 12. INSERT 50,000 RECORDS
    # ========================================================

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


    print(
        f"\nLoading {len(records):,} records "
        "into PostgreSQL..."
    )


    execute_values(
        cursor,
        insert_sql,
        records,
        page_size=BATCH_SIZE,
    )


    # ========================================================
    # 13. VALIDATE BEFORE COMMIT
    # ========================================================

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT complaint_id)
                AS unique_complaints,
            COUNT(*)
                - COUNT(DISTINCT complaint_id)
                AS duplicate_complaints
        FROM raw.cfpb_complaints;
        """
    )

    (
        total_rows,
        unique_complaints,
        duplicate_complaints,
    ) = cursor.fetchone()


    print(
        "\n========================================"
    )
    print(
        "POSTGRESQL LOAD VALIDATION"
    )
    print(
        "========================================"
    )

    print(
        f"Total database rows: {total_rows:,}"
    )

    print(
        f"Unique complaint IDs: "
        f"{unique_complaints:,}"
    )

    print(
        f"Duplicate complaint IDs: "
        f"{duplicate_complaints:,}"
    )


    # ========================================================
    # 14. FINAL SAFETY CHECK
    # ========================================================

    if total_rows != EXPECTED_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_ROWS:,} rows "
            f"after loading but found "
            f"{total_rows:,}."
        )

    if unique_complaints != EXPECTED_ROWS:
        raise RuntimeError(
            "Unique complaint ID count "
            "does not match expected row count."
        )

    if duplicate_complaints != 0:
        raise RuntimeError(
            "Duplicate complaint IDs exist "
            "after PostgreSQL load."
        )


    # ========================================================
    # 15. COMMIT ONLY AFTER VALIDATION PASSES
    # ========================================================

    connection.commit()

    print(
        "\nLoad completed successfully."
    )

    print(
        "Transaction committed."
    )


except Exception as error:

    print(
        "\nERROR DURING DATABASE LOAD:"
    )

    print(
        error
    )

    print(
        "\nRolling back transaction..."
    )

    connection.rollback()

    print(
        "Rollback completed. "
        "Previous database state preserved."
    )

    raise


finally:

    cursor.close()
    connection.close()

    print(
        "\nDatabase connection closed."
    )