import requests
import pandas as pd
from pathlib import Path
from datetime import datetime


API_URL = (
    "https://www.consumerfinance.gov/"
    "data-research/consumer-complaints/search/api/v1/"
)

PAGE_SIZE = 100
TOTAL_RECORDS = 1000

all_complaints = []

page_number = 1
frm = 0
search_after = None
known_break_points = {}


print("Starting CFPB complaint extraction...")


while len(all_complaints) < TOTAL_RECORDS:

    params = {
        "size": PAGE_SIZE,
        "frm": frm,
        "sort": "created_date_desc",
        "no_aggs": "true"
    }

    if search_after:
        params["search_after"] = search_after

    print(f"Downloading page {page_number}...")

    response = requests.get(
        API_URL,
        params=params,
        headers={"Accept": "application/json"},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        print("No more records returned.")
        break

    complaints = [
        record["_source"]
        for record in hits
    ]

    all_complaints.extend(complaints)

    print(
        f"Page {page_number} returned "
        f"{len(complaints)} complaints."
    )

    if len(hits) < PAGE_SIZE:
        break

    # Store pagination cursors returned by CFPB
    break_points = (
        data.get("_meta", {})
        .get("break_points", {})
    )

    known_break_points.update(break_points)

    # Move to the next page number
    page_number += 1

    next_cursor = known_break_points.get(
        str(page_number)
    )

    if not next_cursor:
        raise RuntimeError(
            f"No pagination cursor found "
            f"for page {page_number}."
        )

    search_after = (
        f"{next_cursor[0]}_{next_cursor[1]}"
    )

    frm += PAGE_SIZE


df = pd.DataFrame(all_complaints)

# Keep only the number of records requested
df = df.head(TOTAL_RECORDS)


print("\n==============================")
print("EXTRACTION QUALITY CHECK")
print("==============================")

print("Rows extracted:", len(df))
print("Columns:", len(df.columns))

duplicate_count = (
    df["complaint_id"]
    .duplicated()
    .sum()
)

unique_count = (
    df["complaint_id"]
    .nunique()
)

print("Unique complaint IDs:", unique_count)
print("Duplicate complaint IDs:", duplicate_count)


# Fail the pipeline if duplicate IDs exist
if duplicate_count > 0:
    raise ValueError(
        "Duplicate complaint IDs detected. "
        "Raw file will NOT be saved."
    )


raw_directory = Path("data/raw")

raw_directory.mkdir(
    parents=True,
    exist_ok=True
)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

output_file = (
    raw_directory
    / f"cfpb_complaints_raw_{timestamp}.csv"
)

df.to_csv(
    output_file,
    index=False
)


print("\nRaw file saved successfully:")
print(output_file)