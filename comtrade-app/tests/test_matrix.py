"""Tests of the mirror matching and of the anomaly rule (Doc/Project3.pdf p. 7-8)."""

import pandas as pd
import pytest

from matrix import (
    CONSISTENT,
    FLAGGED,
    FOB_ABOVE_CIF,
    GAP_TOO_HIGH,
    MONTHLY,
    NO_DATA,
    QUARTERLY,
    YEARLY,
    build_matrix,
    compute_cells,
    is_flagged,
    list_periods,
    match_mirrors,
    period_labels,
    top_partners,
)


def export_row(month, partner, value, qty, reporter="FRA"):
    return (month, reporter, "Export", partner, value, qty)


def import_row(month, reporter, value, qty, partner="FRA"):
    return (month, reporter, "Import", partner, value, qty)


def rows_of(*rows):
    columns = ["YearMonth", "Reporter", "Flow", "Partner", "Value_USD", "Qty_t"]
    return pd.DataFrame(rows, columns=columns)


@pytest.mark.parametrize(
    "fob, cif, expected",
    [
        (400, 440, False),  # +10%
        (400, 600, True),  # +50%
        (400, 380, True),  # -5%, FOB > CIF
        (400, 400, False),  # no gap
        (400, 540, False),  # exactly 35%: the rule says strictly above
    ],
)
def test_anomaly_rule(fob, cif, expected):
    assert bool(is_flagged(fob, cif)) is expected


def test_matches_the_real_sample_document():
    rows = rows_of(
        export_row("2025-01", "AGO", 22998882, 101939.0, reporter="ARG"),
        import_row("2025-01", "AGO", 42670229, 100000.0, partner="ARG"),
    )
    cell = compute_cells(match_mirrors(rows, "ARG"), MONTHLY).iloc[0]
    assert cell["Fob"] == pytest.approx(225.614, abs=0.001)
    assert cell["Cif"] == pytest.approx(426.702, abs=0.001)
    assert cell["Gap"] == pytest.approx(0.8913, abs=0.0001)
    assert cell["Status"] == FLAGGED
    assert cell["Anomaly_type"] == GAP_TOO_HIGH


def test_fob_above_cif_type():
    rows = rows_of(export_row("2023-05", "EGY", 400, 1.0), import_row("2023-05", "EGY", 380, 1.0))
    cell = compute_cells(match_mirrors(rows, "FRA"), MONTHLY).iloc[0]
    assert cell["Status"] == FLAGGED
    assert cell["Anomaly_type"] == FOB_ABOVE_CIF


def test_months_without_a_mirror_are_excluded():
    rows = rows_of(
        export_row("2023-01", "EGY", 400, 1.0),
        import_row("2023-01", "EGY", 440, 1.0),
        export_row("2023-02", "EGY", 9000, 1.0),  # no import reported
        import_row("2023-03", "EGY", 9000, 1.0),  # no export reported
    )
    matched = match_mirrors(rows, "FRA")
    assert matched["YearMonth"].tolist() == ["2023-01"]


def test_zero_quantities_are_dropped():
    rows = rows_of(export_row("2023-01", "EGY", 400, 0.0), import_row("2023-01", "EGY", 440, 1.0))
    assert match_mirrors(rows, "FRA").empty


def test_other_exporters_are_ignored():
    rows = rows_of(
        export_row("2023-01", "EGY", 400, 1.0, reporter="USA"),
        import_row("2023-01", "EGY", 440, 1.0, partner="USA"),
    )
    assert match_mirrors(rows, "FRA").empty


def test_period_prices_are_weighted_by_quantity():
    # Import side: 90 t at 440 and 10 t at 600 give 456, not the plain average of 520.
    rows = rows_of(
        export_row("2023-01", "EGY", 36000, 90.0),
        import_row("2023-01", "EGY", 39600, 90.0),
        export_row("2023-02", "EGY", 4000, 10.0),
        import_row("2023-02", "EGY", 6000, 10.0),
    )
    cell = compute_cells(match_mirrors(rows, "FRA"), YEARLY).iloc[0]
    assert cell["Period"] == "2023"
    assert cell["Fob"] == pytest.approx(400)
    assert cell["Cif"] == pytest.approx(456)
    assert cell["Status"] == CONSISTENT


def test_one_flagged_month_does_not_force_the_year_red():
    rows = rows_of(
        export_row("2023-01", "EGY", 36000, 90.0),
        import_row("2023-01", "EGY", 36000, 90.0),
        export_row("2023-02", "EGY", 4000, 10.0),
        import_row("2023-02", "EGY", 6000, 10.0),  # +50% alone
    )
    matched = match_mirrors(rows, "FRA")
    assert compute_cells(matched, MONTHLY)["Status"].tolist() == [CONSISTENT, FLAGGED]
    assert compute_cells(matched, YEARLY)["Status"].tolist() == [CONSISTENT]


@pytest.mark.parametrize(
    "frequency, expected",
    [
        (YEARLY, ["2023", "2023", "2024"]),
        (QUARTERLY, ["2023-Q1", "2023-Q4", "2024-Q2"]),
        (MONTHLY, ["2023-03", "2023-10", "2024-04"]),
    ],
)
def test_period_labels(frequency, expected):
    months = pd.Series(["2023-03", "2023-10", "2024-04"])
    assert period_labels(months, frequency).tolist() == expected


def test_top_partners_ranked_by_exported_value():
    rows = rows_of(
        export_row("2023-01", "EGY", 100, 1.0),
        export_row("2023-02", "EGY", 100, 1.0),
        export_row("2023-01", "MAR", 150, 1.0),
        export_row("2023-01", "DZA", 50, 1.0),
        import_row("2023-01", "ESP", 9000, 1.0),  # imports do not count
    )
    assert top_partners(rows, "FRA", n=2) == ["EGY", "MAR"]


def test_top_partners_skip_excluded_codes():
    rows = rows_of(export_row("2023-01", "_X_", 999, 1.0), export_row("2023-01", "EGY", 100, 1.0))
    assert top_partners(rows, "FRA", excluded={"_X_"}) == ["EGY"]


def test_null_quantities_are_dropped():
    rows = rows_of(
        export_row("2023-01", "EGY", 400, float("nan")),
        import_row("2023-01", "EGY", 440, 1.0),
    )
    assert match_mirrors(rows, "FRA").empty


def test_matrix_has_every_partner_and_period():
    rows = rows_of(
        export_row("2023-01", "EGY", 400, 1.0),
        import_row("2023-01", "EGY", 600, 1.0),
        export_row("2024-01", "MAR", 400, 1.0),
        import_row("2024-01", "MAR", 440, 1.0),
    )
    cells = compute_cells(match_mirrors(rows, "FRA"), YEARLY)
    matrix = build_matrix(cells, ["EGY", "MAR", "ESP"], list_periods(rows, YEARLY))
    assert matrix.loc["EGY", "2023"] == FLAGGED
    assert matrix.loc["EGY", "2024"] == NO_DATA
    assert matrix.loc["MAR", "2024"] == CONSISTENT
    assert (matrix.loc["ESP"] == NO_DATA).all()
