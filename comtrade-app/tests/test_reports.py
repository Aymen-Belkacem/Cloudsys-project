"""Tests of the report job, with fake AWS clients."""

import io
import json
from datetime import datetime, timezone

import pytest
from botocore.exceptions import ClientError

import reports


class FakeLambda:
    def __init__(self):
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)


WRITTEN_AT = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
ERROR_FILE = json.dumps({"error": "PDF failed", "traceback": "secret paths"}).encode()


class FakeS3:
    def __init__(self, body=None, error_code="NoSuchKey"):
        self.body = body
        self.error_code = error_code
        self.calls = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        if self.body is None:
            raise ClientError({"Error": {"Code": self.error_code}}, "GetObject")
        return {"Body": io.BytesIO(self.body), "LastModified": WRITTEN_AT}


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(reports, "AI_LAMBDA_NAME", "ai-lambda")
    monkeypatch.setattr(reports, "REPORTS_BUCKET", "reports")


def use_s3(monkeypatch, client):
    monkeypatch.setattr(reports, "_s3_client", lambda: client)


def test_request_is_asynchronous(monkeypatch):
    client = FakeLambda()
    monkeypatch.setattr(reports, "_lambda_client", lambda: client)
    reports.request_report({"anomaly_id": "A"})
    call = client.calls[0]
    assert call["FunctionName"] == "ai-lambda"
    assert call["InvocationType"] == "Event"
    assert json.loads(call["Payload"]) == {"anomaly_id": "A"}


def test_fetch_uses_the_key_of_the_pdf_lambda(monkeypatch):
    client = FakeS3(body=b"%PDF")
    use_s3(monkeypatch, client)
    assert reports.fetch_report("FRA_EGY_1001_2023") == b"%PDF"
    assert client.calls[0] == {"Bucket": "reports", "Key": "report_FRA_EGY_1001_2023.pdf"}


def test_missing_report_returns_none(monkeypatch):
    use_s3(monkeypatch, FakeS3())
    assert reports.fetch_report("A") is None


def test_other_s3_errors_are_not_hidden(monkeypatch):
    use_s3(monkeypatch, FakeS3(error_code="AccessDenied"))
    with pytest.raises(ClientError):
        reports.fetch_report("A")


def test_error_of_the_current_job_is_returned_without_the_traceback(monkeypatch):
    client = FakeS3(body=ERROR_FILE)
    use_s3(monkeypatch, client)
    assert reports.fetch_error("A", WRITTEN_AT.timestamp() - 60) == "PDF failed"
    assert client.calls[0]["Key"] == "report_A.error"


def test_error_of_a_previous_attempt_is_ignored(monkeypatch):
    use_s3(monkeypatch, FakeS3(body=ERROR_FILE))
    assert reports.fetch_error("A", WRITTEN_AT.timestamp() + 60) is None


def test_no_error_file_returns_none(monkeypatch):
    use_s3(monkeypatch, FakeS3())
    assert reports.fetch_error("A", 0) is None


@pytest.mark.parametrize("body", [b"not json", b"[]", b"{}", b"null"])
def test_unreadable_error_file_still_counts_as_a_failure(monkeypatch, body):
    use_s3(monkeypatch, FakeS3(body=body))
    assert reports.fetch_error("A", 0) == reports.UNKNOWN_ERROR


def test_s3_errors_on_the_error_file_are_not_hidden(monkeypatch):
    use_s3(monkeypatch, FakeS3(error_code="AccessDenied"))
    with pytest.raises(ClientError):
        reports.fetch_error("A", 0)


def test_not_configured_without_the_lambda_name(monkeypatch):
    monkeypatch.setattr(reports, "AI_LAMBDA_NAME", None)
    assert not reports.is_configured()
