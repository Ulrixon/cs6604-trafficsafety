"""
Traffic Safety Index Dashboard - Main Entry Point

This is the main entry point for the multipage Streamlit application.
The app automatically redirects to the Home page.

Run with:
    streamlit run app.py
"""

import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Traffic Safety Dashboard",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Redirect to the Dashboard page
st.switch_page("pages/0_🏠_Dashboard.py")
