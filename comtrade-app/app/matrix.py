"""Mirror matching and anomaly rule behind the heatmap.

No Streamlit here, so the computation stays testable on its own.
Only raw columns are used: each flow is reported twice, by the exporter
(FOB) and by the importer (CIF), and the two sides are matched month by month.
"""

from collections.abc import Callable, Iterable

import pandas as pd

GAP_THRESHOLD = 0.35

YEARLY = "Yearly"
QUARTERLY = "Quarterly"
MONTHLY = "Monthly"
FREQUENCIES = (YEARLY, QUARTERLY, MONTHLY)

CONSISTENT = "consistent"
FLAGGED = "flagged"
NO_DATA = "no data"

FOB_ABOVE_CIF = "FOB > CIF"
GAP_TOO_HIGH = "Gap > 35%"


def is_flagged(fob, cif):
    """Apply the anomaly rule. Works on numbers and on pandas Series."""
    return (fob > cif) | ((cif - fob) / fob > GAP_THRESHOLD)


def match_mirrors(rows: pd.DataFrame, exporter: str) -> pd.DataFrame:
    """Join each export with its mirror import. Months without a mirror are dropped."""
    valid = rows[(rows["Value_USD"] > 0) & (rows["Qty_t"] > 0)]
    exports = valid[(valid["Flow"] == "Export") & (valid["Reporter"] == exporter)]
    imports = valid[(valid["Flow"] == "Import") & (valid["Partner"] == exporter)]
    exports = exports.rename(
        columns={"Partner": "Importer", "Value_USD": "Fob_value", "Qty_t": "Fob_qty"}
    )[["YearMonth", "Importer", "Fob_value", "Fob_qty"]]
    imports = imports.rename(
        columns={"Reporter": "Importer", "Value_USD": "Cif_value", "Qty_t": "Cif_qty"}
    )[["YearMonth", "Importer", "Cif_value", "Cif_qty"]]
    return exports.merge(imports, on=["YearMonth", "Importer"])


def period_labels(months: pd.Series, frequency: str) -> pd.Series:
    """Turn YYYY-MM values into period labels: 2023, 2023-Q2 or 2023-05."""
    if frequency == MONTHLY:
        return months
    years = months.str[:4]
    if frequency == YEARLY:
        return years
    quarters = (months.str[5:7].astype(int) + 2) // 3
    return years + "-Q" + quarters.astype(str)


def list_periods(rows: pd.DataFrame, frequency: str) -> list[str]:
    return sorted(period_labels(rows["YearMonth"], frequency).unique())


def top_partners(
    rows: pd.DataFrame, exporter: str, n: int = 10, excluded: Iterable[str] = ()
) -> list[str]:
    """Importers ranked by value exported, over all periods."""
    exports = rows[(rows["Flow"] == "Export") & (rows["Reporter"] == exporter)]
    exports = exports[~exports["Partner"].isin(excluded)]
    totals = exports.groupby("Partner")["Value_USD"].sum()
    return totals.sort_values(ascending=False).head(n).index.tolist()


def compute_cells(matched: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """Compute one row per importer and period.

    Unit prices are recomputed over the period (total value / total quantity),
    so a period is weighted by the quantities traded and not by its months.
    """
    period = period_labels(matched["YearMonth"], frequency).rename("Period")
    cells = (
        matched.groupby(["Importer", period])[["Fob_value", "Fob_qty", "Cif_value", "Cif_qty"]]
        .sum()
        .reset_index()
    )
    cells["Fob"] = cells["Fob_value"] / cells["Fob_qty"]
    cells["Cif"] = cells["Cif_value"] / cells["Cif_qty"]
    cells["Gap"] = (cells["Cif"] - cells["Fob"]) / cells["Fob"]
    flagged = is_flagged(cells["Fob"], cells["Cif"])
    cells["Status"] = flagged.map({True: FLAGGED, False: CONSISTENT})
    cells["Anomaly_type"] = None
    cells.loc[cells["Gap"] > GAP_THRESHOLD, "Anomaly_type"] = GAP_TOO_HIGH
    cells.loc[cells["Fob"] > cells["Cif"], "Anomaly_type"] = FOB_ABOVE_CIF
    return cells


def route_gap(matched: pd.DataFrame, importer: str) -> float:
    """Gap of a route over all its months, used as historical context."""
    route = matched[matched["Importer"] == importer]
    fob = route["Fob_value"].sum() / route["Fob_qty"].sum()
    cif = route["Cif_value"].sum() / route["Cif_qty"].sum()
    return (cif - fob) / fob


def build_anomaly_event(
    cell: pd.Series,
    exporter: str,
    product: tuple[int, str],
    historical_gap: float,
    country_name: Callable[[str], str],
) -> dict:
    """Build the input of the AI Lambda.

    Its keys are the ones read by the Lambda code: a missing key would silently
    end up as "None" in the prompt sent to the LLM. Names are easier for the LLM
    than codes. The id keeps the codes, because it also names the report file.
    """
    importer = cell["Importer"]
    hs4, product_name = product
    return {
        "anomaly_id": f"{exporter}_{importer}_{hs4}_{cell['Period']}",
        "period": cell["Period"],
        "reporter": country_name(exporter),
        "partner": country_name(importer),
        "hs_code": str(hs4),
        "product_name": product_name,
        "fob_unit_price": round(float(cell["Fob"]), 2),
        "cif_unit_price": round(float(cell["Cif"]), 2),
        "gap_pct": round(float(cell["Gap"]) * 100, 1),
        "anomaly_type": cell["Anomaly_type"],
        "historical_context": f"Historical gap on this route: {historical_gap:+.1%}.",
    }


def build_matrix(cells: pd.DataFrame, partners: list[str], periods: list[str]) -> pd.DataFrame:
    """Status table with partners as rows and periods as columns."""
    return (
        cells.pivot(index="Importer", columns="Period", values="Status")
        .reindex(index=partners, columns=periods)
        .fillna(NO_DATA)
    )
