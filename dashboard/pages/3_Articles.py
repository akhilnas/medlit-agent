"""Article Explorer — browse and filter fetched PubMed articles."""

import streamlit as st

st.set_page_config(page_title="Articles — MedLit Agent", layout="wide")


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


@st.cache_data(ttl=30)
def fetch_queries():
    return get_client().list_queries().get("data", [])


client = get_client()

st.title("Article Explorer")

# ---- Sidebar filters ----
with st.sidebar:
    st.header("Filters")
    queries = fetch_queries()
    query_options = {"All": None} | {q["name"]: q["id"] for q in queries}
    selected_query_name = st.selectbox("Clinical Query", list(query_options.keys()))
    selected_query_id = query_options[selected_query_name]

    status_options = ["All", "pending", "extracted", "failed"]
    selected_status = st.selectbox("Processing Status", status_options)

    study_designs = [
        "All", "meta_analysis", "systematic_review", "rct",
        "cohort", "case_control", "case_report", "review", "other",
    ]
    selected_design = st.selectbox("Study Design", study_designs)

    evidence_levels = ["All", "I", "II", "III", "IV", "V"]
    selected_level = st.selectbox("Evidence Level", evidence_levels)

    page_size = st.slider("Results per page", 10, 100, 25, 5)

# ---- Pagination state ----
if "article_offset" not in st.session_state:
    st.session_state.article_offset = 0

# ---- Fetch articles ----
try:
    resp = client.list_articles(
        query_id=selected_query_id,
        processing_status=None if selected_status == "All" else selected_status,
        study_design=None if selected_design == "All" else selected_design,
        evidence_level=None if selected_level == "All" else selected_level,
        limit=page_size,
        offset=st.session_state.article_offset,
    )
    articles = resp.get("data", [])
    total = resp.get("total", 0)
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

st.caption(f"Showing {len(articles)} of {total} articles")

# ---- Pagination controls ----
col_prev, col_page, col_next = st.columns([1, 3, 1])
if col_prev.button("← Previous") and st.session_state.article_offset >= page_size:
    st.session_state.article_offset -= page_size
    st.rerun()
col_page.caption(
    f"Page {st.session_state.article_offset // page_size + 1} / "
    f"{max(1, (total + page_size - 1) // page_size)}"
)
if col_next.button("Next →") and st.session_state.article_offset + page_size < total:
    st.session_state.article_offset += page_size
    st.rerun()

st.divider()

# ---- Article cards ----
for article in articles:
    with st.expander(
        f"**{article.get('title', 'Untitled')}** — "
        f"{article.get('journal', '')} "
        f"({article.get('publication_date', '')[:4] if article.get('publication_date') else ''})"
    ):
        col_meta, col_scores = st.columns([3, 1])

        with col_meta:
            st.caption(
                f"PMID: {article.get('pmid', '')}  |  "
                f"Study design: {article.get('pico', {}).get('study_design', 'N/A') if article.get('pico') else 'N/A'}  |  "
                f"Evidence level: {article.get('pico', {}).get('evidence_level', 'N/A') if article.get('pico') else 'N/A'}"
            )
            if article.get("abstract"):
                st.markdown(article["abstract"])

        with col_scores:
            relevance = article.get("relevance_score")
            if relevance is not None:
                st.metric("Relevance", f"{relevance:.2f}")
            status = article.get("processing_status", "")
            colour = {"extracted": "green", "pending": "orange", "failed": "red"}.get(status, "gray")
            st.markdown(f":{colour}[**{status.title()}**]")

        pico = article.get("pico")
        if pico:
            st.markdown("**PICO Extraction**")
            pico_cols = st.columns(4)
            pico_cols[0].markdown(f"**P:** {pico.get('population', '—')}")
            pico_cols[1].markdown(f"**I:** {pico.get('intervention', '—')}")
            pico_cols[2].markdown(f"**C:** {pico.get('comparison', '—')}")
            pico_cols[3].markdown(f"**O:** {pico.get('outcome', '—')}")

        if article.get("doi"):
            st.link_button("View on PubMed", f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid')}/")
