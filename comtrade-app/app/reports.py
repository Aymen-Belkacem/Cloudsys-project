"""AI report generation, through the AI Lambda and the reports bucket.

The Lambda does not return the report: it hands the text over to the PDF Lambda,
which writes report_<anomaly_id>.pdf to S3, or report_<anomaly_id>.error when it
fails. So the app starts the job, then waits for one of these files. A report
already in the bucket is reused.
"""

import json
import os

import boto3
import streamlit as st
from botocore.exceptions import ClientError

UNKNOWN_ERROR = "Unreadable error file"

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


def error_key(anomaly_id: str) -> str:
    """S3 key written by the PDF Lambda when it fails."""
    return f"report_{anomaly_id}.error"


def request_report(event: dict) -> None:
    """Start the report job. "Event" returns at once, without waiting for the Lambda."""
    _lambda_client().invoke(
        FunctionName=AI_LAMBDA_NAME,
        InvocationType="Event",
        Payload=json.dumps(event),
    )


def _get_object(key: str) -> dict | None:
    """Return the S3 object, or None when it does not exist."""
    try:
        return _s3_client().get_object(Bucket=REPORTS_BUCKET, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def fetch_report(anomaly_id: str) -> bytes | None:
    """Return the PDF, or None when it does not exist yet."""
    response = _get_object(report_key(anomaly_id))
    return None if response is None else response["Body"].read()


def fetch_error(anomaly_id: str, since: float) -> str | None:
    """Return the failure of a job started at `since`, or None.

    The PDF Lambda never deletes its .error files: an older one belongs to a
    previous attempt. The traceback of the file is left out on purpose.
    """
    response = _get_object(error_key(anomaly_id))
    if response is None or response["LastModified"].timestamp() < since:
        return None
    try:
        return json.loads(response["Body"].read())["error"]
    except (KeyError, TypeError, ValueError):
        return UNKNOWN_ERROR
