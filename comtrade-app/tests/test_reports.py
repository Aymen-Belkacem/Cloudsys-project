"""Tests of the report job, with fake AWS clients."""

import io
import json

import pytest
from botocore.exceptions import ClientError

import reports


class FakeLambda:
    def __init__(self):
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)


class FakeS3:
    def __init__(self, body=None, error_code="NoSuchKey"):
        self.body = body
        self.error_code = error_code
        self.calls = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        if self.body is None:
            raise ClientError({"Error": {"Code": self.error_code}}, "GetObject")
        return {"Body": io.BytesIO(self.body)}


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


def test_not_configured_without_the_lambda_name(monkeypatch):
    monkeypatch.setattr(reports, "AI_LAMBDA_NAME", None)
    assert not reports.is_configured()
