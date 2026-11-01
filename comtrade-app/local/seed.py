"""Load the bilateral trade CSV into the local MongoDB (local development only)."""

import os

import pandas as pd
from pymongo import MongoClient

CSV_PATH = "/data/Bilateral_data.csv"

collection = MongoClient(os.environ["DOCDB_HOST"], 27017)[os.environ["DOCDB_DATABASE"]][
    os.environ["DOCDB_COLLECTION"]
]

if collection.estimated_document_count() > 0:
    print("Local database already loaded")
else:
    rows = pd.read_csv(CSV_PATH, thousands="'", dtype={"YearMonth": str})
    collection.insert_many(rows.to_dict("records"))
    print(f"Loaded {len(rows)} rows")
