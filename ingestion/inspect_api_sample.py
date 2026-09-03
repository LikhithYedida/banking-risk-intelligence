import requests
import pandas as pd

API_URL = (
    "https://www.consumerfinance.gov/"
    "data-research/consumer-complaints/search/api/v1/"
)

params = {
    "size": 10,
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

print("\nDATAFRAME SHAPE")
print(df.shape)

print("\nCOLUMN NAMES")
print(df.columns.tolist())

print("\nFIRST 5 ROWS")
print(df.head())

print("\nDATA TYPES")
print(df.dtypes)