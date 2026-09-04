import re
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

import truststore

# Use the Windows certificate store for HTTPS validation.
truststore.inject_into_ssl()

import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BULK_DATA_URL = (
    "https://files.consumerfinance.gov/"
    "ccdb/complaints.csv.zip"
)

TOTAL_RECORDS = 50_000

# Number of rows read from the large CFPB CSV at a time.
READ_CHUNK_SIZE = 100_000

# Download the ZIP in 1 MB pieces.
DOWNLOAD_CHUNK_SIZE = 1024 * 1024

REQUEST_TIMEOUT = (30, 300)

MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 3


# ============================================================
# COLUMN DEFINITIONS
# ============================================================

CANONICAL_COLUMNS = [
    "date_received",
    "product",
    "sub_product",
    "issue",
    "sub_issue",
    "complaint_what_happened",
    "company_public_response",
    "company",
    "state",
    "zip_code",
    "tags",
    "consumer_consent_provided",
    "submitted_via",
    "date_sent_to_company",
    "company_response",
    "timely",
    "consumer_disputed",
    "complaint_id",
]

REQUIRED_COLUMNS = {
    "date_received",
    "product",
    "issue",
    "company",
    "submitted_via",
    "timely",
    "complaint_id",
}


# ============================================================
# NORMALIZE CSV COLUMN NAMES
# ============================================================

def normalize_column_name(column_name):
    """
    Convert CFPB CSV headers into snake_case names.

    Example:
        Date received -> date_received
        ZIP code -> zip_code
        Timely response? -> timely_response
    """

    normalized = column_name.strip().lower()

    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        normalized,
    )

    return normalized.strip("_")


def normalize_columns(df):
    """
    Convert CFPB bulk CSV field names into the same structure
    used by the existing PostgreSQL and dbt pipeline.
    """

    df = df.rename(
        columns={
            column: normalize_column_name(column)
            for column in df.columns
        }
    )

    alias_map = {
        "consumer_complaint_narrative":
            "complaint_what_happened",

        "company_response_to_consumer":
            "company_response",

        "timely_response":
            "timely",
    }

    df = df.rename(
        columns=alias_map
    )

    return df


# ============================================================
# DOWNLOAD CFPB BULK ZIP
# ============================================================

def download_bulk_file(session, destination):
    """
    Download the official CFPB complaint database ZIP.
    """

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            print(
                f"\nDownloading CFPB bulk dataset..."
                f"\nAttempt {attempt}/{MAX_RETRIES}"
            )

            response = session.get(
                BULK_DATA_URL,
                stream=True,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent":
                        "banking-risk-intelligence-project/1.0"
                },
            )

            response.raise_for_status()

            total_bytes = int(
                response.headers.get(
                    "content-length",
                    0,
                )
            )

            downloaded_bytes = 0

            next_progress = 10

            with open(
                destination,
                "wb",
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=DOWNLOAD_CHUNK_SIZE
                ):

                    if not chunk:
                        continue

                    file.write(chunk)

                    downloaded_bytes += len(chunk)

                    if total_bytes > 0:

                        percentage = (
                            downloaded_bytes
                            / total_bytes
                            * 100
                        )

                        if percentage >= next_progress:

                            print(
                                f"Download progress: "
                                f"{percentage:.0f}%"
                            )

                            next_progress += 10

            print(
                "\nBulk ZIP downloaded successfully."
            )

            print(
                f"Downloaded: "
                f"{downloaded_bytes / (1024 * 1024):.2f} MB"
            )

            return

        except requests.RequestException as error:

            print(
                "\nDownload failed."
            )

            print(
                f"Error: {error}"
            )

            if attempt == MAX_RETRIES:

                raise RuntimeError(
                    "Unable to download the CFPB "
                    "bulk complaint dataset."
                ) from error

            wait_time = (
                RETRY_BACKOFF_SECONDS
                * attempt
            )

            print(
                f"Waiting {wait_time} seconds "
                "before retrying..."
            )

            time.sleep(
                wait_time
            )


# ============================================================
# SELECT LATEST 50,000 COMPLAINTS
# ============================================================

def extract_latest_records(zip_path):
    """
    Read the full CFPB CSV in chunks and retain the latest
    TOTAL_RECORDS complaints.

    This avoids loading the entire complaint database
    into memory at once.
    """

    print(
        "\n========================================"
    )

    print(
        "PROCESSING CFPB DATA"
    )

    print(
        "========================================"
    )

    best_records = None

    total_rows_scanned = 0

    with zipfile.ZipFile(
        zip_path,
        "r",
    ) as archive:

        csv_files = [
            file_name
            for file_name in archive.namelist()
            if file_name.lower().endswith(".csv")
        ]

        if not csv_files:

            raise RuntimeError(
                "No CSV file was found "
                "inside the CFPB ZIP."
            )

        # If the ZIP ever contains multiple CSV files,
        # choose the largest one.
        csv_file = max(
            csv_files,
            key=lambda name:
                archive.getinfo(name).file_size,
        )

        print(
            f"CSV found inside ZIP: {csv_file}"
        )

        with archive.open(
            csv_file
        ) as file:

            reader = pd.read_csv(
                file,
                dtype=str,
                chunksize=READ_CHUNK_SIZE,
                low_memory=False,
            )

            for chunk_number, chunk in enumerate(
                reader,
                start=1,
            ):

                chunk = normalize_columns(
                    chunk
                )

                if chunk_number == 1:

                    missing_columns = (
                        REQUIRED_COLUMNS
                        - set(chunk.columns)
                    )

                    if missing_columns:

                        raise ValueError(
                            "Required CFPB columns "
                            "are missing: "
                            f"{sorted(missing_columns)}"
                        )

                total_rows_scanned += len(
                    chunk
                )

                print(
                    f"Processing chunk {chunk_number}"
                    f" | Total source rows scanned: "
                    f"{total_rows_scanned:,}"
                )

                # --------------------------------------------
                # Create sorting fields
                # --------------------------------------------

                chunk["_received_sort"] = pd.to_datetime(
                    chunk["date_received"],
                    errors="coerce",
                )

                chunk["_complaint_id_sort"] = pd.to_numeric(
                    chunk["complaint_id"],
                    errors="coerce",
                ).fillna(-1)

                # --------------------------------------------
                # Keep best candidate records
                # --------------------------------------------

                if best_records is None:

                    candidates = chunk

                else:

                    candidates = pd.concat(
                        [
                            best_records,
                            chunk,
                        ],
                        ignore_index=True,
                    )

                candidates = (
                    candidates
                    .sort_values(
                        by=[
                            "_received_sort",
                            "_complaint_id_sort",
                        ],
                        ascending=[
                            False,
                            False,
                        ],
                        na_position="last",
                    )
                    .head(TOTAL_RECORDS)
                    .copy()
                )

                best_records = candidates

    if best_records is None:

        raise RuntimeError(
            "No complaint records were read."
        )

    print(
        "\nSource rows scanned: "
        f"{total_rows_scanned:,}"
    )

    print(
        "Candidate rows retained: "
        f"{len(best_records):,}"
    )

    # Remove temporary sort columns.
    best_records = best_records.drop(
        columns=[
            "_received_sort",
            "_complaint_id_sort",
        ],
        errors="ignore",
    )

    return best_records


# ============================================================
# PREPARE FINAL RAW DATASET
# ============================================================

def prepare_dataset(df):

    print(
        "\nPreparing final 50,000-row dataset..."
    )

    # Ensure optional source columns always exist.
    for column in CANONICAL_COLUMNS:

        if column not in df.columns:

            df[column] = None

    df = df[
        CANONICAL_COLUMNS
    ].copy()

    if len(df) < TOTAL_RECORDS:

        raise RuntimeError(
            "The CFPB dataset contained fewer "
            f"than {TOTAL_RECORDS:,} usable records."
        )

    df = df.head(
        TOTAL_RECORDS
    )

    return df


# ============================================================
# DATA QUALITY CHECKS
# ============================================================

def validate_dataset(df):

    print(
        "\n========================================"
    )

    print(
        "EXTRACTION QUALITY CHECK"
    )

    print(
        "========================================"
    )

    print(
        f"Rows extracted: {len(df):,}"
    )

    print(
        f"Columns extracted: {len(df.columns)}"
    )

    # --------------------------------------------------------
    # Complaint IDs
    # --------------------------------------------------------

    complaint_ids = (
        df["complaint_id"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    missing_complaint_ids = (
        complaint_ids
        .eq("")
        .sum()
    )

    duplicate_count = (
        complaint_ids
        .duplicated()
        .sum()
    )

    unique_count = (
        complaint_ids
        .nunique()
    )

    print(
        f"Unique complaint IDs: "
        f"{unique_count:,}"
    )

    print(
        f"Duplicate complaint IDs: "
        f"{duplicate_count:,}"
    )

    print(
        f"Missing complaint IDs: "
        f"{missing_complaint_ids:,}"
    )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    received_dates = pd.to_datetime(
        df["date_received"],
        errors="coerce",
    )

    invalid_dates = (
        received_dates
        .isna()
        .sum()
    )

    print(
        f"Invalid received dates: "
        f"{invalid_dates:,}"
    )

    if received_dates.notna().any():

        print(
            "Earliest complaint date: "
            f"{received_dates.min().date()}"
        )

        print(
            "Latest complaint date: "
            f"{received_dates.max().date()}"
        )

    # --------------------------------------------------------
    # Narrative information
    # --------------------------------------------------------

    narrative_count = (
        df["complaint_what_happened"]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
        .sum()
    )

    print(
        f"Complaints with narratives: "
        f"{narrative_count:,}"
    )

    # --------------------------------------------------------
    # Fail if critical checks fail
    # --------------------------------------------------------

    if len(df) != TOTAL_RECORDS:

        raise ValueError(
            f"Expected {TOTAL_RECORDS:,} rows "
            f"but received {len(df):,}."
        )

    if missing_complaint_ids > 0:

        raise ValueError(
            "Missing complaint IDs detected. "
            "Raw file will NOT be saved."
        )

    if duplicate_count > 0:

        raise ValueError(
            "Duplicate complaint IDs detected. "
            "Raw file will NOT be saved."
        )

    if invalid_dates > 0:

        raise ValueError(
            "Invalid complaint dates detected. "
            "Raw file will NOT be saved."
        )

    return unique_count


# ============================================================
# SAVE FINAL RAW CSV
# ============================================================

def save_raw_file(df):

    raw_directory = Path(
        "data/raw"
    )

    raw_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = (
        datetime.now()
        .strftime("%Y%m%d_%H%M%S")
    )

    output_file = (
        raw_directory
        / f"cfpb_complaints_raw_{timestamp}.csv"
    )

    df.to_csv(
        output_file,
        index=False,
    )

    return output_file


# ============================================================
# MAIN
# ============================================================

def main():

    start_time = time.time()

    print(
        "========================================"
    )

    print(
        "CFPB COMPLAINT BULK EXTRACTION"
    )

    print(
        "========================================"
    )

    print(
        "Source: Official CFPB bulk CSV ZIP"
    )

    print(
        f"Target records: {TOTAL_RECORDS:,}"
    )

    print(
        "Selection: Latest complaints"
    )

    print(
        "========================================"
    )

    session = requests.Session()

    try:

        with tempfile.TemporaryDirectory() as temp_dir:

            zip_path = (
                Path(temp_dir)
                / "complaints.csv.zip"
            )

            download_bulk_file(
                session=session,
                destination=zip_path,
            )

            df = extract_latest_records(
                zip_path
            )

    finally:

        session.close()

    df = prepare_dataset(
        df
    )

    unique_count = validate_dataset(
        df
    )

    output_file = save_raw_file(
        df
    )

    elapsed_seconds = (
        time.time()
        - start_time
    )

    print(
        "\n========================================"
    )

    print(
        "EXTRACTION COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        f"Final rows: {len(df):,}"
    )

    print(
        f"Unique complaint IDs: "
        f"{unique_count:,}"
    )

    print(
        f"Runtime: "
        f"{elapsed_seconds / 60:.2f} minutes"
    )

    print(
        "\nRaw file saved successfully:"
    )

    print(
        output_file
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()