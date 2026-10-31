"""AI report generation, through the AI Lambda and the reports bucket.

The Lambda does not return the report: it hands the text over to the PDF Lambda,
which writes report_<anomaly_id>.pdf to S3. So the app starts the job, then waits
for that file. A report already in the bucket is reused.
"""

import json
import os

import boto3
import streamlit as st
from botocore.exceptions import ClientError

AI_LAMBDA_NAME = os.getenv("AI_LAMBDA_NAME")
REPORTS_BUCKET = os.getenv("REPORTS_BUCKET")


def is_configured() -> bool:
    return bool(AI_LAMBDA_NAME and REPORTS_BUCKET)


@st.cache_resource
def _lambda_client():
    return boto3.client("lambda")


@st.cache_resource
def _s3_client():
    return boto3.client("s3")


def report_key(anomaly_id: str) -> str:
    """S3 key chosen by the PDF Lambda."""
    return f"report_{anomaly_id}.pdf"


def request_report(event: dict) -> None:
    """Start the report job. "Event" returns at once, without waiting for the Lambda."""
    _lambda_client().invoke(
        FunctionName=AI_LAMBDA_NAME,
        InvocationType="Event",
        Payload=json.dumps(event),
    )


def fetch_report(anomaly_id: str) -> bytes | None:
    """Return the PDF, or None when it does not exist yet."""
    try:
        response = _s3_client().get_object(Bucket=REPORTS_BUCKET, Key=report_key(anomaly_id))
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise
    return response["Body"].read()
