"""Semantic Search — hybrid vector + full-text search across articles."""

import streamlit as st

st.set_page_config(page_title="Search — MedLit Agent", layout="wide")

from dashboard.auth import require_login  # noqa: E402
from dashboard.theme import apply_theme  # noqa: E402

require_login()
apply_theme()


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


client = get_client()

st.title("Semantic Search")
st.markdown(
    '<p style="font-style:italic;color:var(--text-dim);">'
    'Hybrid PubMedBERT vector search + PostgreSQL full-text search across '
    'article abstracts and PICO fields.'
    '</p>',
    unsafe_allow_html=True,
)

# ── Search form ───────────────────────────────────────────────────────────────
with st.form("search_form"):
    query_text = st.text_input(
        "Query",
        placeholder="SGLT2 inhibitors reduce hospitalisation in heart failure patients",
    )
    col1, col2, col3 = st.columns(3)
    embedding_type = col1.selectbox("Embedding type", ["abstract", "pico"])
    min_similarity = col2.slider("Min similarity", 0.0, 1.0, 0.3, 0.05)
    limit          = col3.slider("Max results",    5,   50,  10,  5)

    study_design_opts = [
        "Any", "meta_analysis", "systematic_review", "rct",
        "cohort", "case_control", "case_report", "review", "other",
    ]
    study_design = st.selectbox("Study design filter", study_design_opts)
    submitted    = st.form_submit_button("Search", type="primary")

# ── Execute search ────────────────────────────────────────────────────────────
if submitted:
    if not query_text.strip():
        st.warning("Enter a search query.")
    else:
        payload: dict = {
            "query":          query_text,
            "embedding_type": embedding_type,
            "min_similarity": min_similarity,
            "limit":          limit,
        }
        if study_design != "Any":
            payload["study_design"] = study_design

        with st.spinner("Searching…"):
            try:
                results = client.search_articles(payload)
            except Exception as exc:
                st.error(f"Search failed: {exc}")
                st.stop()

        items = results.get("results", [])
        total = results.get("total", 0)

        if not items:
            st.info(
                "No results found. Try lowering the minimum similarity threshold "
                "or broadening your query."
            )
        else:
            st.markdown(
                f'<div style="font-family:var(--font-mono);font-size:0.66rem;'
                f'letter-spacing:0.14em;color:var(--text-faint);margin-bottom:1rem;">'
                f'{total} RESULTS</div>',
                unsafe_allow_html=True,
            )
            for item in items:
                score        = item.get("similarity_score", 0)
                vec          = item.get("vector_score", 0)
                fts          = item.get("fts_score", 0)
                study_design_val = (item.get("study_design") or "N/A").replace("_", " ").upper()
                ev_level     = item.get("evidence_level") or "N/A"

                # Score bar width (capped at 100%)
                bar_pct = min(int(score * 100), 100)

                with st.container(border=True):
                    col_title, col_score = st.columns([4, 1])
                    with col_title:
                        st.markdown(
                            f'<div style="font-family:var(--font-body);font-size:1.05rem;'
                            f'color:var(--text);margin-bottom:0.3rem;">'
                            f'{item.get("title", "Untitled")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f'<div style="font-family:var(--font-mono);font-size:0.62rem;'
                            f'letter-spacing:0.10em;color:var(--text-faint);">'
                            f'PMID {item.get("pmid", "—")}'
                            f'&nbsp;&nbsp;·&nbsp;&nbsp;{study_design_val}'
                            f'&nbsp;&nbsp;·&nbsp;&nbsp;LEVEL {ev_level}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        # Similarity bar
                        st.markdown(
                            f'<div style="margin-top:0.55rem;">'
                            f'<div style="height:2px;background:var(--border-2);'
                            f'border-radius:1px;overflow:hidden;">'
                            f'<div style="height:2px;width:{bar_pct}%;'
                            f'background:var(--teal);'
                            f'border-radius:1px;"></div>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                    with col_score:
                        st.metric("Score", f"{score:.3f}")
                        st.markdown(
                            f'<div style="font-family:var(--font-mono);font-size:0.60rem;'
                            f'letter-spacing:0.08em;color:var(--text-faint);">'
                            f'VEC {vec:.2f}&nbsp;&nbsp;FTS {fts:.2f}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
