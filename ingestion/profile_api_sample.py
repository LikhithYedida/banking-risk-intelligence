import requests
import pandas as pd


API_URL = (
    "https://www.consumerfinance.gov/"
    "data-research/consumer-complaints/search/api/v1/"
)

params = {
    "size": 100,
    "sort": "created_date_desc",
    "no_aggs": "true"
}


response = requests.get(
    API_URL,
    params=params,
    headers={"Accept": "application/json"},
    timeout=30
)

response.raise_for_status()

data = response.json()

complaints = [
    record["_source"]
    for record in data["hits"]["hits"]
]

df = pd.DataFrame(complaints)


print("\n==============================")
print("CFPB SAMPLE DATA PROFILE")
print("==============================")

print("\n1. DATASET SHAPE")
print(df.shape)


print("\n2. DUPLICATE COMPLAINT IDs")
print(df["complaint_id"].duplicated().sum())


print("\n3. MISSING VALUES BY COLUMN")
print(df.isna().sum().sort_values(ascending=False))


print("\n4. TIMELY RESPONSE VALUES")
print(df["timely"].value_counts(dropna=False))


print("\n5. SUBMISSION CHANNELS")
print(df["submitted_via"].value_counts(dropna=False))


print("\n6. TOP 10 PRODUCTS")
print(df["product"].value_counts(dropna=False).head(10))


print("\n7. TOP 10 COMPANIES")
print(df["company"].value_counts(dropna=False).head(10))


print("\n8. NARRATIVE AVAILABILITY")
print(df["has_narrative"].value_counts(dropna=False))


date_received = pd.to_datetime(
    df["date_received"],
    errors="coerce"
)

print("\n9. DATE RANGE")
print("Earliest:", date_received.min())
print("Latest:  ", date_received.max())