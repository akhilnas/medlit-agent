"""Semantic Search — hybrid vector + full-text search across articles."""

import streamlit as st

st.set_page_config(page_title="Search — MedLit Agent", layout="wide")


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


client = get_client()

st.title("Semantic Search")
st.caption("Searches article abstracts and PICO data using PubMedBERT embeddings + PostgreSQL full-text search.")

# ---- Search form ----
with st.form("search_form"):
    query_text = st.text_input(
        "Search query",
        placeholder="SGLT2 inhibitors reduce hospitalisation in heart failure patients",
    )
    col1, col2, col3 = st.columns(3)
    embedding_type = col1.selectbox("Embedding type", ["abstract", "pico"])
    min_similarity = col2.slider("Min similarity", 0.0, 1.0, 0.3, 0.05)
    limit = col3.slider("Max results", 5, 50, 10, 5)

    study_design_opts = [
        "Any", "meta_analysis", "systematic_review", "rct",
        "cohort", "case_control", "case_report", "review", "other",
    ]
    study_design = st.selectbox("Study design filter", study_design_opts)
    submitted = st.form_submit_button("Search", type="primary")

# ---- Execute search ----
if submitted:
    if not query_text.strip():
        st.warning("Enter a search query.")
    else:
        payload: dict = {
            "query": query_text,
            "embedding_type": embedding_type,
            "min_similarity": min_similarity,
            "limit": limit,
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
            st.success(f"Found {total} results")
            for item in items:
                with st.container(border=True):
                    col_title, col_score = st.columns([4, 1])
                    with col_title:
                        st.markdown(f"**{item.get('title', 'Untitled')}**")
                        st.caption(
                            f"PMID: {item.get('pmid', '')}  |  "
                            f"Study design: {item.get('study_design', 'N/A')}  |  "
                            f"Evidence level: {item.get('evidence_level', 'N/A')}"
                        )
                    with col_score:
                        score = item.get("similarity_score", 0)
                        st.metric("Score", f"{score:.3f}")
                        vec = item.get("vector_score", 0)
                        fts = item.get("fts_score", 0)
                        st.caption(f"Vec: {vec:.2f}  FTS: {fts:.2f}")
