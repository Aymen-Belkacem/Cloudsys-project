"""Comtrade Anomalies - Step 2: Streamlit application entry point."""

import streamlit as st

st.set_page_config(page_title="Comtrade Anomalies", page_icon=":bar_chart:", layout="wide")

st.navigation(
    [
        st.Page("matrix_page.py", title="Trade anomalies"),
        st.Page("status_page.py", title="Status report"),
    ]
).run()
