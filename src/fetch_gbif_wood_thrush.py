import time
import requests
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

output_path = (
    ROOT
    / "data"
    / "raw"
    / "gbif"
    / "wood_thrush_ebird_ny_2023_breeding.csv"
)

output_path.parent.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.gbif.org/v1/occurrence/search"

params = {
    "datasetKey": "4fa7b334-ce0d-4e88-aaae-2e0c138d049e",   # eBird Observation Dataset
    "scientificName": "Hylocichla mustelina",               # Wood Thrush
    "stateProvince": "New York",
    "hasCoordinate": "true",
    "eventDate": "2023-05-31,2023-07-26",                  # breeding season window
    "limit": 300,
    "offset": 0
}

all_records = []
page = 1

while True:
    print(f"Requesting page {page} | offset = {params['offset']}")

    response = requests.get(BASE_URL, params=params, timeout=60)
    response.raise_for_status()

    payload = response.json()
    results = payload.get("results", [])

    print(f"  records returned: {len(results)}")

    for r in results:
        all_records.append({
            "gbif_id": r.get("key"),
            "species": r.get("species"),
            "scientific_name": r.get("scientificName"),
            "event_date": r.get("eventDate"),
            "lat": r.get("decimalLatitude"),
            "lon": r.get("decimalLongitude"),
            "county": r.get("county"),
            "state_province": r.get("stateProvince"),
            "locality": r.get("locality"),
            "basis_of_record": r.get("basisOfRecord"),
        })

    if payload.get("endOfRecords", True):
        print("Reached end of records.")
        break

    params["offset"] += params["limit"]
    page += 1
    time.sleep(0.2)

df = pd.DataFrame(all_records)

# Drop rows with missing coordinates just in case
df = df.dropna(subset=["lat", "lon"]).copy()

# Remove any accidental duplicate GBIF IDs
df = df.drop_duplicates(subset=["gbif_id"]).copy()

df.to_csv(output_path, index=False)

print("\nSaved:")
print(output_path)

print("\nFinal dataset shape:")
print(df.shape)

print("\nPreview:")
print(df.head())

print("\nLatitude range:", df["lat"].min(), "to", df["lat"].max())
print("Longitude range:", df["lon"].min(), "to", df["lon"].max())