"""Article Explorer — browse and filter fetched PubMed articles."""

import streamlit as st

st.set_page_config(page_title="Articles — MedLit Agent", layout="wide")

from dashboard.theme import apply_theme, status_badge, pico_grid  # noqa: E402

apply_theme()


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


@st.cache_data(ttl=30)
def fetch_queries():
    return get_client().list_queries().get("data", [])


client = get_client()

st.title("Article Explorer")

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="font-family:var(--font-mono);font-size:0.62rem;'
        'letter-spacing:0.20em;text-transform:uppercase;color:var(--text-faint);'
        'margin-bottom:0.75rem;">Filters</div>',
        unsafe_allow_html=True,
    )
    queries = fetch_queries()
    query_options        = {"All": None} | {q["name"]: q["id"] for q in queries}
    selected_query_name  = st.selectbox("Clinical Query",    list(query_options.keys()))
    selected_query_id    = query_options[selected_query_name]

    status_options  = ["All", "pending", "extracted", "failed"]
    selected_status = st.selectbox("Processing Status", status_options)

    study_designs = [
        "All", "meta_analysis", "systematic_review", "rct",
        "cohort", "case_control", "case_report", "review", "other",
    ]
    selected_design = st.selectbox("Study Design",    study_designs)

    evidence_levels = ["All", "I", "II", "III", "IV", "V"]
    selected_level  = st.selectbox("Evidence Level",  evidence_levels)

    page_size = st.slider("Results per page", 10, 100, 25, 5)

# ── Pagination state ──────────────────────────────────────────────────────────
if "article_offset" not in st.session_state:
    st.session_state.article_offset = 0

# ── Fetch articles ────────────────────────────────────────────────────────────
try:
    resp = client.list_articles(
        query_id         = selected_query_id,
        processing_status= None if selected_status == "All" else selected_status,
        study_design     = None if selected_design == "All" else selected_design,
        evidence_level   = None if selected_level  == "All" else selected_level,
        limit            = page_size,
        offset           = st.session_state.article_offset,
    )
    articles = resp.get("data", [])
    total    = resp.get("total", 0)
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

# ── Pagination controls ───────────────────────────────────────────────────────
col_prev, col_page, col_next = st.columns([1, 3, 1])
if col_prev.button("← Prev") and st.session_state.article_offset >= page_size:
    st.session_state.article_offset -= page_size
    st.rerun()

current_page = st.session_state.article_offset // page_size + 1
total_pages  = max(1, (total + page_size - 1) // page_size)
col_page.markdown(
    f'<div style="text-align:center;font-family:var(--font-mono);'
    f'font-size:0.68rem;letter-spacing:0.12em;color:var(--text-faint);'
    f'padding-top:0.55rem;">'
    f'{len(articles)} of {total} articles &nbsp;·&nbsp; '
    f'page {current_page} / {total_pages}</div>',
    unsafe_allow_html=True,
)
if col_next.button("Next →") and st.session_state.article_offset + page_size < total:
    st.session_state.article_offset += page_size
    st.rerun()

st.divider()

# ── Article cards ─────────────────────────────────────────────────────────────
for article in articles:
    year = (article.get("publication_date") or "")[:4]
    journal = article.get("journal", "")
    pico = article.get("pico")
    study_design   = pico.get("study_design",  "N/A") if pico else "N/A"
    evidence_level = pico.get("evidence_level", "N/A") if pico else "N/A"

    label = (
        f"{article.get('title', 'Untitled')}"
        f"{'  —  ' + journal if journal else ''}"
        f"{'  (' + year + ')' if year else ''}"
    )
    with st.expander(label):
        col_meta, col_scores = st.columns([3, 1])

        with col_meta:
            st.markdown(
                f'<div style="font-family:var(--font-mono);font-size:0.65rem;'
                f'letter-spacing:0.10em;color:var(--text-faint);margin-bottom:0.6rem;">'
                f'PMID {article.get("pmid", "—")}'
                f'&nbsp;&nbsp;·&nbsp;&nbsp;{study_design.replace("_", " ").upper()}'
                f'&nbsp;&nbsp;·&nbsp;&nbsp;LEVEL {evidence_level}'
                f'</div>',
                unsafe_allow_html=True,
            )
            if article.get("abstract"):
                st.markdown(article["abstract"])

        with col_scores:
            relevance = article.get("relevance_score")
            if relevance is not None:
                st.metric("Relevance", f"{relevance:.2f}")
            proc_status = article.get("processing_status", "")
            st.markdown(status_badge(proc_status), unsafe_allow_html=True)

        if pico:
            st.markdown(
                pico_grid(
                    pico.get("population",   "—"),
                    pico.get("intervention", "—"),
                    pico.get("comparison",   "—"),
                    pico.get("outcome",      "—"),
                ),
                unsafe_allow_html=True,
            )

        if article.get("pmid"):
            st.link_button(
                "View on PubMed",
                f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid')}/",
            )
