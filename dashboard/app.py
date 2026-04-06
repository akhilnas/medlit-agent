"""MedLit Agent — Streamlit dashboard entry point.

Run with:
    streamlit run dashboard/app.py

Or via Docker Compose:
    docker compose -f docker-compose.prod.yml up streamlit
"""

import streamlit as st

st.set_page_config(
    page_title="MedLit Agent",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar branding
st.sidebar.title("MedLit Agent")
st.sidebar.caption("Medical Literature Triage & Evidence Synthesis")
st.sidebar.divider()

# Redirect to Home page content inline (acts as the landing page)
st.title("MedLit Agent")
st.markdown(
    "**Automated medical literature triage, PICO extraction, and evidence synthesis.**"
)
st.info("Use the sidebar to navigate between pages.")

col1, col2, col3 = st.columns(3)
col1.page_link("pages/1_Home.py", label="Home — Queries & Syntheses", icon="")
col2.page_link("pages/3_Articles.py", label="Article Explorer", icon="")
col3.page_link("pages/4_Search.py", label="Semantic Search", icon="")

col4, col5 = st.columns(2)
col4.page_link("pages/5_Syntheses.py", label="Evidence Syntheses", icon="")
col5.page_link("pages/6_Pipeline.py", label="Pipeline Status", icon="")
