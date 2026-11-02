"""Country names for the codes used by the trade data."""

import pycountry

# Comtrade aggregates: they are not countries, so never partners of the heatmap
NON_COUNTRY_CODES = {"_X_", "EUR_OTHERS", "OTHER_ASIA"}

# Real countries that do not use their ISO3 code in the data
CUSTOM_NAMES = {"ALBA": "Albania", "CURAC": "Curacao", "NORTH_MACED": "North Macedonia"}


def country_name(code: str) -> str:
    """Return the country name, or the code itself when it is unknown."""
    if code in CUSTOM_NAMES:
        return CUSTOM_NAMES[code]
    country = pycountry.countries.get(alpha_3=code)
    if country is None:
        return code
    return getattr(country, "common_name", country.name)
