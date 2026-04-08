"""MedLit Agent — Streamlit dashboard entry point.

Run with:
    streamlit run dashboard/app.py

Or via Docker Compose:
    docker compose -f docker-compose.prod.yml up streamlit
"""

import streamlit as st

st.set_page_config(
    page_title="MedLit Agent",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.theme import apply_theme  # noqa: E402

apply_theme()

# ── Sidebar branding ─────────────────────────────────────────────────────────
st.sidebar.markdown(
    """
    <div style="
      padding: 1.6rem 0.6rem 1.2rem;
      border-bottom: 1px solid var(--border-2);
      margin-bottom: 0.5rem;
    ">
      <div style="
        font-family: var(--font-head);
        font-size: 1.4rem;
        letter-spacing: 0.22em;
        color: var(--text);
        line-height: 1;
        margin-bottom: 0.35rem;
      ">MEDLIT AGENT</div>
      <div style="
        font-family: var(--font-mono);
        font-size: 0.58rem;
        letter-spacing: 0.16em;
        color: var(--accent);
        text-transform: uppercase;
      ">Literature Triage · Evidence Synthesis</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="
      padding: 3.5rem 1rem 2.5rem;
      text-align: center;
      max-width: 680px;
      margin: 0 auto;
    ">
      <div style="
        font-family: 'Cormorant SC', serif;
        font-size: 5.2rem;
        font-weight: 300;
        letter-spacing: 0.28em;
        color: var(--text);
        line-height: 1;
        margin-bottom: 0.15rem;
      ">MEDLIT</div>
      <div style="
        font-family: 'Cormorant SC', serif;
        font-size: 1.9rem;
        font-weight: 400;
        letter-spacing: 0.42em;
        color: var(--accent);
        margin-bottom: 1.6rem;
      ">AGENT</div>
      <div style="
        width: 48px;
        height: 1px;
        background: var(--accent-border);
        margin: 0 auto 1.4rem;
      "></div>
      <p style="
        font-family: 'Crimson Pro', serif;
        font-style: italic;
        font-size: 1.12rem;
        color: var(--text-dim);
        letter-spacing: 0.02em;
        line-height: 1.7;
        margin: 0;
      ">
        Automated medical literature triage, PICO extraction,<br>
        and evidence synthesis.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Navigation index ──────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="
      font-family: var(--font-mono);
      font-size: 0.62rem;
      letter-spacing: 0.20em;
      text-transform: uppercase;
      color: var(--text-faint);
      text-align: center;
      margin-bottom: 1.2rem;
    ">Navigation</div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
col1.page_link("pages/1_Home.py",       label="Home — Queries & Syntheses")
col2.page_link("pages/2_Queries.py",    label="Clinical Queries")
col3.page_link("pages/3_Articles.py",   label="Article Explorer")

col4, col5, col6 = st.columns(3)
col4.page_link("pages/4_Search.py",     label="Semantic Search")
col5.page_link("pages/5_Syntheses.py",  label="Evidence Syntheses")
col6.page_link("pages/6_Pipeline.py",   label="Pipeline Status")
