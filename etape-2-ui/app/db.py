"""DocumentDB access shared by the Streamlit pages."""

import os

import pandas as pd
import streamlit as st
from pymongo import MongoClient

# Downloaded by the Dockerfile. Outside /app, which docker-compose mounts over.
CA_FILE = "/etc/ssl/certs/docdb-global-bundle.pem"

DOCDB_HOST = os.getenv("DOCDB_HOST")
DOCDB_DATABASE = os.getenv("DOCDB_DATABASE", "ingestion")
DOCDB_COLLECTION = os.getenv("DOCDB_COLLECTION", "products")
DOCDB_TLS = os.getenv("DOCDB_TLS", "true") == "true"  # false for the local MongoDB

TRADE_COLUMNS = ["YearMonth", "Reporter", "Flow", "Partner", "Value_USD", "Qty_t"]
CACHE_SECONDS = 3600


@st.cache_resource
def get_client() -> MongoClient | None:
    """Return the shared client, or None when no database is configured.

    The client connects lazily: a wrong host or password only fails on the first query.
    Options come from the AWS documentation for TLS clusters.
    """
    if not DOCDB_HOST:
        return None
    documentdb_options = {
        "tls": True,
        "tlsCAFile": CA_FILE,
        "replicaSet": "rs0",
        "readPreference": "secondaryPreferred",
        "retryWrites": False,
    }
    return MongoClient(
        DOCDB_HOST,
        27017,
        username=os.getenv("DOCDB_USERNAME"),
        password=os.getenv("DOCDB_PASSWORD"),
        serverSelectionTimeoutMS=5000,
        **(documentdb_options if DOCDB_TLS else {}),
    )


def _products_collection():
    return get_client()[DOCDB_DATABASE][DOCDB_COLLECTION]


@st.cache_data(ttl=CACHE_SECONDS)
def get_exporters() -> list[str]:
    """Countries that report exports."""
    return sorted(_products_collection().distinct("Reporter", {"Flow": "Export"}))


@st.cache_data(ttl=CACHE_SECONDS)
def get_products() -> list[tuple[int, str]]:
    """Products as (HS4 code, name) pairs."""
    groups = _products_collection().aggregate(
        [{"$group": {"_id": {"hs4": "$HS4", "name": "$Product"}}}]
    )
    return sorted((group["_id"]["hs4"], group["_id"]["name"]) for group in groups)


@st.cache_data(ttl=CACHE_SECONDS)
def get_trade_rows(exporter: str, hs4: int) -> pd.DataFrame:
    """Both sides of the exporter's flows for one product."""
    documents = _products_collection().find(
        {
            "HS4": hs4,
            "$or": [
                {"Flow": "Export", "Reporter": exporter},
                {"Flow": "Import", "Partner": exporter},
            ],
        },
        {column: 1 for column in TRADE_COLUMNS} | {"_id": 0},
    )
    return pd.DataFrame(list(documents), columns=TRADE_COLUMNS)
