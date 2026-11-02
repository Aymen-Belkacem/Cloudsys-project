"""Error display: details stay in the logs, because the app URL is public."""

import logging
import os

import streamlit as st

# Anything but an explicit "local" counts as production, so nothing leaks by default
IS_LOCAL = os.getenv("APP_ENV") == "local"

logger = logging.getLogger(__name__)


def show_error(message: str, detail: Exception | str) -> None:
    """Show a generic message, with the details only on a local run.

    AWS and driver errors can contain ARNs, the account ID or internal hosts.
    """
    logger.error("%s %s", message, detail)
    st.error(f"{message} {detail}" if IS_LOCAL else message)
