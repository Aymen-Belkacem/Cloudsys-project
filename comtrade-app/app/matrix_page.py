"""Anomaly heatmap: exporter, product and frequency in, top partners x periods out."""

import pandas as pd
import streamlit as st
from pymongo.errors import PyMongoError

import reports
from countries import NON_COUNTRY_CODES, country_name
from db import get_client, get_exporters, get_products, get_trade_rows
from errors import show_error
from matrix import (
    CONSISTENT,
    FLAGGED,
    FREQUENCIES,
    NO_DATA,
    ONE_SIDED,
    build_anomaly_event,
    build_matrix,
    compute_cells,
    declared_cells,
    list_periods,
    match_mirrors,
    route_gap,
    top_partners,
)
from report_view import show_report_section

CELL_COLORS = {
    CONSISTENT: "#ffffff",
    ONE_SIDED: "#ffffff",
    FLAGGED: "#ff0000",
    NO_DATA: "#e0e0e0",
}
RED_CELL_HINT = "Click a red cell to see the details of the anomaly."
TOP_PARTNERS_COUNT = 10
ROW_HEIGHT = 35
REPORT_POLL_SECONDS = 5


def _show_configuration_panel() -> None:
    """Show the panel and remember the selection: clicks on the heatmap rerun the page."""
    with st.form("configuration"):
        exporter_col, product_col, frequency_col, button_col = st.columns([3, 3, 2, 1])
        exporter = exporter_col.selectbox("Exporter", get_exporters(), format_func=country_name)
        product = product_col.selectbox(
            "Product (HS)", get_products(), format_func=lambda item: f"{item[0]} - {item[1]}"
        )
        frequency = frequency_col.selectbox("Frequency", FREQUENCIES)
        if button_col.form_submit_button("Show", type="primary"):
            st.session_state.heatmap_selection = (exporter, product, frequency)


def _style_heatmap(matrix: pd.DataFrame):
    """Return an empty table with one background color per cell."""
    labels = pd.DataFrame(
        "",
        index=[country_name(code) for code in matrix.index],
        columns=matrix.columns,
    )
    colors = matrix.map(lambda status: f"background-color: {CELL_COLORS[status]}")
    colors.index = labels.index
    return labels.style.apply(lambda _: colors, axis=None)


def _show_anomaly(
    cell: pd.Series, exporter: str, product: tuple[int, str], matched: pd.DataFrame
) -> None:
    st.subheader(f"{country_name(exporter)} to {country_name(cell['Importer'])}, {cell['Period']}")
    st.caption(f"{product[0]} - {product[1]} | Anomaly: {cell['Anomaly_type']}")
    fob_col, cif_col, gap_col = st.columns(3)
    fob_col.metric("FOB (USD/t)", f"{cell['Fob']:,.2f}")
    cif_col.metric("CIF (USD/t)", f"{cell['Cif']:,.2f}")
    gap_col.metric("Gap", f"{cell['Gap']:+.1%}")

    if not reports.is_configured():
        st.info("AI reports are not configured (AI_LAMBDA_NAME or REPORTS_BUCKET is not set).")
        return
    event = build_anomaly_event(
        cell, exporter, product, route_gap(matched, cell["Importer"]), country_name
    )
    is_pending = event["anomaly_id"] in st.session_state.get("pending_reports", {})
    st.fragment(show_report_section, run_every=REPORT_POLL_SECONDS if is_pending else None)(event)


def _show_heatmap(exporter: str, product: tuple[int, str], frequency: str) -> None:
    rows = get_trade_rows(exporter, product[0])
    partners = top_partners(rows, exporter, TOP_PARTNERS_COUNT, NON_COUNTRY_CODES)
    if not partners:
        st.info(f"No trade of {product[1]} reported for {country_name(exporter)}.")
        return

    matched = match_mirrors(rows, exporter)
    cells = compute_cells(matched, frequency)
    declared = declared_cells(rows, exporter, frequency)
    matrix = build_matrix(cells, partners, list_periods(rows, frequency), declared)

    event = st.dataframe(
        _style_heatmap(matrix),
        key=f"heatmap-{exporter}-{product[0]}-{frequency}",
        height=ROW_HEIGHT * (len(partners) + 1) + 3,
        row_height=ROW_HEIGHT,
        on_select="rerun",
        selection_mode="single-cell",
    )
    st.caption(
        "White: consistent, or reported by one side only. Red: flagged. "
        f"Grey: no trade reported. {RED_CELL_HINT}"
    )

    if not event.selection.cells:
        return
    row, period = event.selection.cells[0]
    selected = cells[(cells["Importer"] == partners[row]) & (cells["Period"] == period)]
    if not selected.empty and selected.iloc[0]["Status"] == FLAGGED:
        _show_anomaly(selected.iloc[0], exporter, product, matched)


st.title("Trade anomalies")

if get_client() is None:
    st.warning("Database not configured (DOCDB_HOST is not set).")
    st.stop()

try:
    _show_configuration_panel()
    if "heatmap_selection" in st.session_state:
        _show_heatmap(*st.session_state.heatmap_selection)
except PyMongoError as exc:
    show_error("Database error.", exc)
