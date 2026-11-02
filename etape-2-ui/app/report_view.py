"""Report section of an anomaly: show the PDF, start the job, report failures."""

import time

import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError

import reports
from errors import show_error

# Kept even with the .error files: the AI Lambda does not write any
REPORT_TIMEOUT_SECONDS = 180
PDF_VIEWER_HEIGHT = 800
FAILURE_MESSAGE = "Report generation failed. See the Lambda logs."
TIMEOUT_DETAIL = "No report after 3 minutes."


def _show_pdf(report: bytes, anomaly_id: str) -> None:
    st.pdf(report, height=PDF_VIEWER_HEIGHT, key=f"pdf-{anomaly_id}")
    st.download_button(
        "Download PDF",
        report,
        file_name=reports.report_key(anomaly_id),
        mime="application/pdf",
        on_click="ignore",
    )


def _update_report_section(event: dict) -> None:
    anomaly_id = event["anomaly_id"]
    pending = st.session_state.setdefault("pending_reports", {})
    failed = st.session_state.setdefault("failed_reports", {})
    started = pending.get(anomaly_id)

    # First, because a .error stays in the bucket next to a later valid PDF
    report = reports.fetch_report(anomaly_id)
    if report is not None:
        failed.pop(anomaly_id, None)
        if started is not None:
            del pending[anomaly_id]
            st.rerun()  # a full rerun stops the polling
        _show_pdf(report, anomaly_id)
        return

    if started is None:
        if anomaly_id in failed:
            show_error(FAILURE_MESSAGE, failed[anomaly_id])
        if st.button("Retry" if anomaly_id in failed else "Analyze anomaly"):
            reports.request_report(event)
            failed.pop(anomaly_id, None)
            pending[anomaly_id] = time.time()
            st.rerun()
        return

    error = reports.fetch_error(anomaly_id, started)
    if error is None and time.time() - started > REPORT_TIMEOUT_SECONDS:
        error = TIMEOUT_DETAIL
    if error is not None:
        failed[anomaly_id] = error
        del pending[anomaly_id]
        st.rerun()
    st.info("Generating the report, this takes about 30 seconds...")


def show_report_section(event: dict) -> None:
    """Show the report if it exists, else offer to generate it and wait for it."""
    try:
        _update_report_section(event)
    except (BotoCoreError, ClientError) as exc:
        show_error("Report service error.", exc)
