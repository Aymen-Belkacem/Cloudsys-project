"""Status report: runtime, ECS task, DocumentDB connection and sample document."""

import json
import os
import platform
import socket
import sys
import urllib.request
from datetime import datetime, timezone

import streamlit as st

from db import DOCDB_COLLECTION, DOCDB_DATABASE, DOCDB_HOST, get_client

APP_NAME = "Comtrade Anomalies"
APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_ENV = os.getenv("APP_ENV", "local")


@st.cache_resource
def _started_at() -> datetime:
    """Process start time (cached for the whole process lifetime)."""
    return datetime.now(timezone.utc)


def _ecs_task_metadata() -> dict | None:
    """Read the ECS task metadata when the app runs on ECS/Fargate.

    ECS injects the ECS_CONTAINER_METADATA_URI_V4 variable into every container.
    Locally it is missing and the function returns None.
    """
    base_uri = os.getenv("ECS_CONTAINER_METADATA_URI_V4")
    if not base_uri:
        return None
    try:
        with urllib.request.urlopen(f"{base_uri}/task", timeout=2) as resp:
            data = json.load(resp)
        return {
            "Cluster": data.get("Cluster", "?").split("/")[-1],
            "Task ARN": data.get("TaskARN", "?"),
            "Availability Zone": data.get("AvailabilityZone", "?"),
            "Launch type": data.get("LaunchType", "?"),
            "Task definition": f'{data.get("Family", "?")}:{data.get("Revision", "?")}',
        }
    except Exception as exc:  # noqa: BLE001 - the status report must never crash
        return {"Metadata read error": str(exc)}


def _format_uptime(started: datetime) -> str:
    seconds = int((datetime.now(timezone.utc) - started).total_seconds())
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours} h {minutes:02d} min {secs:02d} s"


def _read_database() -> dict:
    """Ping DocumentDB and read its collections and one sample document."""
    client = get_client()
    if client is None:
        return {"state": "Not configured (DOCDB_HOST not set)"}
    try:
        client.admin.command("ping")
        database = client[DOCDB_DATABASE]
        return {
            "state": "Connected",
            "counts": {
                name: database[name].estimated_document_count()
                for name in database.list_collection_names()
            },
            "sample": database[DOCDB_COLLECTION].find_one(),
        }
    except Exception as exc:  # noqa: BLE001 - the status report must never crash
        return {"state": "Connection failed", "error": str(exc)}


st.title(f"{APP_NAME} - Status report")
st.caption("Step 2: Streamlit application.")

ecs_meta = _ecs_task_metadata()
runtime = "AWS ECS (Fargate)" if ecs_meta else "Local (Docker / dev machine)"
db_report = _read_database()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Status", "OK")
col2.metric("Version", APP_VERSION)
col3.metric("Environment", APP_ENV)
col4.metric("Uptime", _format_uptime(_started_at()))

st.subheader("Runtime")
st.table(
    {
        "Parameter": [
            "Platform",
            "Container hostname",
            "Server time (UTC)",
            "Python",
            "Streamlit",
            "OS / architecture",
        ],
        "Value": [
            runtime,
            socket.gethostname(),
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            sys.version.split()[0],
            st.__version__,
            f"{platform.system()} / {platform.machine()}",
        ],
    }
)

if ecs_meta:
    st.subheader("ECS task")
    st.table({"Parameter": list(ecs_meta.keys()), "Value": list(ecs_meta.values())})

st.subheader("Database")
st.table(
    {
        "Parameter": ["State", "Host", "Database", "Collection"],
        "Value": [db_report["state"], DOCDB_HOST or "-", DOCDB_DATABASE, DOCDB_COLLECTION],
    }
)

if "error" in db_report:
    st.error(db_report["error"])

if "counts" in db_report:
    st.table(
        {
            "Collection": list(db_report["counts"].keys()),
            "Documents (estimated)": list(db_report["counts"].values()),
        }
    )
    sample = db_report["sample"]
    if sample is None:
        st.info(f"The `{DOCDB_COLLECTION}` collection is empty.")
    else:
        st.write(f"Sample document from `{DOCDB_COLLECTION}`:")
        st.table(
            {
                "Field": list(sample.keys()),
                "Type": [type(value).__name__ for value in sample.values()],
            }
        )
        st.json(json.dumps(sample, default=str))

st.subheader("Architecture components")
st.table(
    {
        "Component": [
            f"Amazon DocumentDB ({DOCDB_DATABASE}.{DOCDB_COLLECTION})",
            "AWS Lambda - AI Orchestrator (step 3)",
            "Amazon S3 - reports-pdf (step 3)",
            "AWS Cognito (optional)",
        ],
        "State": [
            db_report["state"],
            "Not wired (placeholder)",
            "Not wired (placeholder)",
            "Not enabled",
        ],
    }
)

with st.expander("Interactive test (checks that WebSockets work)"):
    st.write(
        "If this counter goes up when you click, the WebSocket connection "
        "between the browser and the Streamlit server works."
    )
    if "clicks" not in st.session_state:
        st.session_state.clicks = 0
    if st.button("Click"):
        st.session_state.clicks += 1
    st.write(f"Click count: **{st.session_state.clicks}**")
