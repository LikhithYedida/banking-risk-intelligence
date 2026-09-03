import requests

API_URL = (
    "https://www.consumerfinance.gov/"
    "data-research/consumer-complaints/search/api/v1/"
)

params = {
    "size": 10,
    "sort": "created_date_desc",
    "no_aggs": "true"
}

print("Connecting to CFPB Consumer Complaint API...")

response = requests.get(
    API_URL,
    params=params,
    headers={"Accept": "application/json"},
    timeout=30
)

print("HTTP Status:", response.status_code)

response.raise_for_status()

data = response.json()

complaints = data["hits"]["hits"]

print("Complaints returned:", len(complaints))

print("\nFirst complaint:")
print(complaints[0]["_source"])