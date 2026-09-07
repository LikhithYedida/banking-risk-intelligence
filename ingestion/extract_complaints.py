import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

# Inject Windows certificate store before requests is imported.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import numpy as np
import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BULK_FILE_URL = (
    "https://files.consumerfinance.gov/"
    "ccdb/complaints.csv.zip"
)

RAW_DIRECTORY = Path("data/raw")

# Final analytical sample size.
TOTAL_RECORDS = 50_000

# Previous 12 complete calendar months.
MONTH_COUNT = 12

# Read CFPB bulk CSV in chunks.
CHUNK_SIZE = 200_000

# Makes the random sample reproducible.
RANDOM_SEED = 42

DOWNLOAD_CHUNK_SIZE = 1024 * 1024


# ============================================================
# COLUMN CONFIGURATION
# ============================================================

OUTPUT_COLUMNS = [
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
]


COLUMN_RENAME_MAP = {
    "consumer_complaint_narrative":
        "complaint_what_happened",

    "company_response_to_consumer":
        "company_response",

    "timely_response":
        "timely",
}


# ============================================================
# HELPERS
# ============================================================

def normalize_column_name(column_name):
    """
    Convert CFPB column names into predictable snake_case.
    """

    value = str(column_name).strip().lower()

    value = value.replace("?", "")

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    value = value.strip("_")

    return value


def normalize_columns(df):
    """
    Normalize original CFPB bulk-file headers and map
    selected fields to names used by our pipeline.
    """

    df.columns = [
        normalize_column_name(column)
        for column in df.columns
    ]

    df = df.rename(
        columns=COLUMN_RENAME_MAP
    )

    return df


def get_sampling_months():
    """
    Return the previous 12 complete calendar months.

    Example when run in September 2026:
        2025-09 through 2026-08
    """

    today = pd.Timestamp.today().normalize()

    current_month = today.to_period("M")

    final_complete_month = current_month - 1

    months = pd.period_range(
        end=final_complete_month,
        periods=MONTH_COUNT,
        freq="M",
    )

    return months


def download_bulk_file(destination):
    """
    Download the official CFPB bulk complaints ZIP.
    """

    print("\nDownloading official CFPB bulk dataset...")

    with requests.get(
        BULK_FILE_URL,
        stream=True,
        timeout=120,
    ) as response:

        response.raise_for_status()

        downloaded_bytes = 0

        with open(destination, "wb") as file:

            for block in response.iter_content(
                chunk_size=DOWNLOAD_CHUNK_SIZE
            ):

                if not block:
                    continue

                file.write(block)

                downloaded_bytes += len(block)

                downloaded_mb = (
                    downloaded_bytes
                    / 1024
                    / 1024
                )

                print(
                    f"\rDownloaded: "
                    f"{downloaded_mb:,.1f} MB",
                    end="",
                    flush=True,
                )

    print("\nBulk download complete.")


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print(
        "\n========================================"
    )
    print(
        "CFPB 12-MONTH ANALYTICAL EXTRACTION"
    )
    print(
        "========================================"
    )

    months = get_sampling_months()

    month_strings = [
        str(month)
        for month in months
    ]

    print(
        f"Target records: {TOTAL_RECORDS:,}"
    )

    print(
        f"Complete months: {MONTH_COUNT}"
    )

    print(
        "Window:"
        f" {month_strings[0]}"
        f" through {month_strings[-1]}"
    )

    print(
        f"Random seed: {RANDOM_SEED}"
    )

    print(
        "\nSampling method:"
        "\n  Uniform random sample across the"
        "\n  entire 12-month population."
        "\n  Natural monthly distribution preserved."
    )


    # ========================================================
    # TEMPORARY BULK ZIP
    # ========================================================

    temp_directory = Path(
        tempfile.gettempdir()
    )

    bulk_zip_path = (
        temp_directory
        / "cfpb_complaints_bulk.zip"
    )

    try:

        download_bulk_file(
            bulk_zip_path
        )


        # ====================================================
        # OPEN BULK FILE
        # ====================================================

        print(
            "\nOpening CFPB bulk ZIP..."
        )

        with zipfile.ZipFile(
            bulk_zip_path,
            "r",
        ) as archive:

            csv_files = [
                filename
                for filename
                in archive.namelist()
                if filename.lower().endswith(
                    ".csv"
                )
            ]

            if not csv_files:
                raise RuntimeError(
                    "No CSV file found inside "
                    "the CFPB ZIP archive."
                )

            csv_filename = csv_files[0]

            print(
                "CSV inside archive:"
            )

            print(
                csv_filename
            )


            # ================================================
            # SAMPLING STATE
            # ================================================

            rng = np.random.default_rng(
                RANDOM_SEED
            )

            # Instead of one sample per month,
            # maintain ONE global sample.
            overall_sample = pd.DataFrame()

            # Track actual source distribution.
            available_rows = {
                month: 0
                for month in month_strings
            }

            total_rows_scanned = 0

            relevant_rows_seen = 0


            # ================================================
            # STREAM CSV IN CHUNKS
            # ================================================

            with archive.open(
                csv_filename
            ) as csv_file:

                chunks = pd.read_csv(
                    csv_file,
                    dtype=str,
                    chunksize=CHUNK_SIZE,
                    low_memory=False,
                )


                for chunk_number, chunk in enumerate(
                    chunks,
                    start=1,
                ):

                    total_rows_scanned += len(chunk)

                    chunk = normalize_columns(
                        chunk
                    )


                    # ========================================
                    # VERIFY REQUIRED COLUMNS
                    # ========================================

                    missing_columns = [
                        column
                        for column in OUTPUT_COLUMNS
                        if column not in chunk.columns
                    ]

                    if missing_columns:
                        raise ValueError(
                            "Required columns missing "
                            "from CFPB bulk file: "
                            f"{missing_columns}"
                        )


                    # ========================================
                    # DATE FILTER
                    # ========================================

                    received_dates = pd.to_datetime(
                        chunk["date_received"],
                        errors="coerce",
                    )

                    chunk["_received_date_parsed"] = (
                        received_dates
                    )

                    chunk["_received_month"] = (
                        received_dates
                        .dt.to_period("M")
                        .astype(str)
                    )

                    relevant = chunk[
                        chunk["_received_month"]
                        .isin(month_strings)
                    ].copy()


                    # ========================================
                    # REMOVE INVALID COMPLAINT IDS
                    # ========================================

                    relevant["complaint_id"] = (
                        relevant["complaint_id"]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                    )

                    relevant = relevant[
                        relevant["complaint_id"] != ""
                    ].copy()

                    # Protect against duplicate complaint IDs
                    # occurring inside the same chunk.
                    relevant = (
                        relevant
                        .drop_duplicates(
                            subset=["complaint_id"],
                            keep="first",
                        )
                    )

                    relevant_rows_seen += len(relevant)


                    # ========================================
                    # TRACK NATURAL MONTHLY DISTRIBUTION
                    # ========================================

                    month_counts = (
                        relevant["_received_month"]
                        .value_counts()
                    )

                    for month, count in month_counts.items():

                        if month in available_rows:

                            available_rows[month] += int(
                                count
                            )


                    # ========================================
                    # GLOBAL RANDOM SAMPLING
                    # ========================================

                    if not relevant.empty:

                        # Every eligible complaint receives
                        # one random sampling key.
                        relevant["_sample_key"] = (
                            rng.random(
                                len(relevant)
                            )
                        )

                        overall_sample = pd.concat(
                            [
                                overall_sample,
                                relevant,
                            ],
                            ignore_index=True,
                        )

                        # Protect against duplicate IDs
                        # across chunks.
                        overall_sample = (
                            overall_sample
                            .sort_values(
                                "_sample_key"
                            )
                            .drop_duplicates(
                                subset=["complaint_id"],
                                keep="first",
                            )
                        )

                        # Keep the 50,000 smallest random keys
                        # seen across the ENTIRE 12-month
                        # population.
                        overall_sample = (
                            overall_sample
                            .nsmallest(
                                TOTAL_RECORDS,
                                "_sample_key",
                            )
                        )


                    print(
                        f"Chunk {chunk_number:,} | "
                        f"Rows scanned: "
                        f"{total_rows_scanned:,} | "
                        f"Valid rows in target window: "
                        f"{relevant_rows_seen:,}"
                    )


        # ====================================================
        # VALIDATE SOURCE POPULATION
        # ====================================================

        print(
            "\n========================================"
        )
        print(
            "12-MONTH SOURCE DISTRIBUTION"
        )
        print(
            "========================================"
        )

        total_available = sum(
            available_rows.values()
        )

        for month in month_strings:

            count = available_rows[month]

            pct = (
                100.0
                * count
                / total_available
                if total_available
                else 0
            )

            print(
                f"{month}: "
                f"{count:,} available "
                f"({pct:.2f}%)"
            )


        if len(overall_sample) < TOTAL_RECORDS:

            raise RuntimeError(
                f"Only {len(overall_sample):,} "
                f"unique valid complaints were "
                f"available in the selected "
                f"12-month window. "
                f"{TOTAL_RECORDS:,} were requested."
            )


        # ====================================================
        # BUILD FINAL SAMPLE
        # ====================================================

        final_df = overall_sample.copy()

        # Sort output chronologically for easier inspection.
        final_df["_sort_received_date"] = (
            pd.to_datetime(
                final_df["date_received"],
                errors="coerce",
            )
        )

        final_df = (
            final_df
            .sort_values(
                [
                    "_sort_received_date",
                    "complaint_id",
                ]
            )
            .reset_index(drop=True)
        )


        # ====================================================
        # FINAL CLEANUP
        # ====================================================

        final_df = final_df[
            OUTPUT_COLUMNS
        ].copy()


        # ====================================================
        # SAMPLE MONTHLY DISTRIBUTION
        # ====================================================

        parsed_dates = pd.to_datetime(
            final_df["date_received"],
            errors="coerce",
        )

        sample_months = (
            parsed_dates
            .dt.to_period("M")
            .astype(str)
        )

        sample_month_counts = (
            sample_months
            .value_counts()
        )

        print(
            "\n========================================"
        )
        print(
            "FINAL SAMPLE MONTHLY DISTRIBUTION"
        )
        print(
            "========================================"
        )

        for month in month_strings:

            count = int(
                sample_month_counts.get(
                    month,
                    0,
                )
            )

            pct = (
                100.0
                * count
                / len(final_df)
            )

            print(
                f"{month}: "
                f"{count:,} sampled "
                f"({pct:.2f}%)"
            )


        # ====================================================
        # FINAL DATA QUALITY
        # ====================================================

        total_rows = len(
            final_df
        )

        unique_ids = (
            final_df[
                "complaint_id"
            ]
            .nunique()
        )

        duplicate_ids = (
            final_df[
                "complaint_id"
            ]
            .duplicated()
            .sum()
        )

        parsed_dates = pd.to_datetime(
            final_df["date_received"],
            errors="coerce",
        )

        earliest_date = (
            parsed_dates.min()
        )

        latest_date = (
            parsed_dates.max()
        )

        distinct_months = (
            parsed_dates
            .dt.to_period("M")
            .nunique()
        )


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
            f"Final rows: {total_rows:,}"
        )

        print(
            f"Unique complaint IDs: "
            f"{unique_ids:,}"
        )

        print(
            f"Duplicate complaint IDs: "
            f"{duplicate_ids:,}"
        )

        print(
            f"Earliest date: "
            f"{earliest_date.date()}"
        )

        print(
            f"Latest date: "
            f"{latest_date.date()}"
        )

        print(
            f"Distinct months: "
            f"{distinct_months}"
        )


        if total_rows != TOTAL_RECORDS:

            raise ValueError(
                f"Expected {TOTAL_RECORDS:,} "
                f"records but produced "
                f"{total_rows:,}."
            )

        if unique_ids != TOTAL_RECORDS:

            raise ValueError(
                "Complaint IDs are not unique."
            )

        if duplicate_ids != 0:

            raise ValueError(
                "Duplicate complaint IDs detected."
            )

        if distinct_months != MONTH_COUNT:

            raise ValueError(
                f"Expected {MONTH_COUNT} "
                f"distinct months but found "
                f"{distinct_months}."
            )


        # ====================================================
        # SAVE RAW FILE
        # ====================================================

        RAW_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        output_file = (
            RAW_DIRECTORY
            / (
                "cfpb_complaints_raw_"
                f"{timestamp}.csv"
            )
        )

        final_df.to_csv(
            output_file,
            index=False,
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
            f"Final rows: "
            f"{len(final_df):,}"
        )

        print(
            f"Unique complaint IDs: "
            f"{final_df['complaint_id'].nunique():,}"
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


    finally:

        # Remove temporary downloaded bulk ZIP.
        if bulk_zip_path.exists():

            try:

                bulk_zip_path.unlink()

                print(
                    "\nTemporary CFPB ZIP removed."
                )

            except PermissionError:

                print(
                    "\nWarning: temporary ZIP "
                    "could not be removed."
                )


if __name__ == "__main__":
    main()