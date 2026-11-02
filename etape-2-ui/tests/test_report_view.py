"""Tests of the report section, with the AWS calls replaced."""

import time

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import errors
import reports
from report_view import FAILURE_MESSAGE, REPORT_TIMEOUT_SECONDS

ANOMALY_ID = "FRA_EGY_1001_2023"
DETAIL = "Object of type ObjectId is not JSON serializable"
WAITING = "Generating the report, this takes about 30 seconds..."


def page():
    from report_view import show_report_section

    show_report_section({"anomaly_id": "FRA_EGY_1001_2023"})


@pytest.fixture
def aws(monkeypatch):
    """Replace the AWS calls: no report, no error, jobs recorded in `requests`."""

    class Aws:
        report = None
        error = None
        requests = []

    Aws.requests = []
    monkeypatch.setattr(reports, "fetch_report", lambda anomaly_id: Aws.report)
    monkeypatch.setattr(reports, "fetch_error", lambda anomaly_id, since: Aws.error)
    monkeypatch.setattr(reports, "request_report", Aws.requests.append)
    monkeypatch.setattr(st, "pdf", lambda data, **kwargs: st.text("PDF viewer"))
    monkeypatch.setattr(errors, "IS_LOCAL", False)
    return Aws


def run_page(pending_since=None, failed=None):
    app = AppTest.from_function(page, default_timeout=10)
    if pending_since is not None:
        app.session_state["pending_reports"] = {ANOMALY_ID: pending_since}
    if failed is not None:
        app.session_state["failed_reports"] = {ANOMALY_ID: failed}
    return app.run()


def errors_of(app):
    return [element.value for element in app.error]


def labels_of(app):
    return [element.label for element in app.button]


def test_new_anomaly_offers_the_analysis(aws):
    app = run_page()
    assert labels_of(app) == ["Analyze anomaly"]
    assert errors_of(app) == []


def test_click_starts_the_job_and_waits(aws):
    app = run_page()
    app.button[0].click().run()
    assert aws.requests == [{"anomaly_id": ANOMALY_ID}]
    assert [element.value for element in app.info] == [WAITING]


def test_error_file_stops_the_wait_at_once(aws):
    aws.error = DETAIL
    app = run_page(pending_since=time.time())
    assert errors_of(app) == [FAILURE_MESSAGE]
    assert labels_of(app) == ["Retry"]
    assert not app.info
    assert app.session_state["pending_reports"] == {}


def test_production_hides_the_detail(aws):
    aws.error = DETAIL
    assert DETAIL not in errors_of(run_page(pending_since=time.time()))[0]


def test_local_run_shows_the_detail(aws, monkeypatch):
    monkeypatch.setattr(errors, "IS_LOCAL", True)
    aws.error = DETAIL
    assert DETAIL in errors_of(run_page(pending_since=time.time()))[0]


def test_no_error_file_keeps_waiting(aws):
    app = run_page(pending_since=time.time())
    assert [element.value for element in app.info] == [WAITING]
    assert errors_of(app) == []


def test_timeout_still_ends_the_wait_without_error_file(aws):
    app = run_page(pending_since=time.time() - REPORT_TIMEOUT_SECONDS - 1)
    assert errors_of(app) == [FAILURE_MESSAGE]
    assert labels_of(app) == ["Retry"]


def test_retry_starts_a_new_job_and_clears_the_failure(aws):
    app = run_page(failed=DETAIL)
    app.button[0].click().run()
    assert len(aws.requests) == 1
    assert errors_of(app) == []
    assert ANOMALY_ID in app.session_state["pending_reports"]


def test_pdf_wins_over_an_old_failure(aws):
    aws.report = b"%PDF"
    aws.error = DETAIL
    app = run_page(failed=DETAIL)
    assert errors_of(app) == []
    assert [element.value for element in app.text] == ["PDF viewer"]
    assert app.session_state["failed_reports"] == {}


def test_pdf_ends_the_wait(aws):
    aws.report = b"%PDF"
    app = run_page(pending_since=time.time())
    assert [element.value for element in app.text] == ["PDF viewer"]
    assert app.session_state["pending_reports"] == {}
