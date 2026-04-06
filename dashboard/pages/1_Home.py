"""Home page — active clinical queries and latest evidence syntheses."""

import streamlit as st

st.set_page_config(page_title="Home — MedLit Agent", layout="wide")


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


def _grade_colour(grade: str | None) -> str:
    return {
        "strong": "green",
        "moderate": "blue",
        "weak": "orange",
        "insufficient": "red",
    }.get((grade or "").lower(), "gray")


def _consensus_icon(status: str | None) -> str:
    return {
        "consensus": "",
        "conflicting": "",
        "insufficient": "",
    }.get((status or "").lower(), "")


st.title("Home")
st.caption("Active clinical queries and latest evidence syntheses")

client = get_client()

try:
    queries_resp = client.list_queries(is_active=True)
    syntheses_resp = client.list_syntheses(limit=5)
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

queries = queries_resp.get("data", [])
syntheses = syntheses_resp.get("data", [])

col_q, col_s = st.columns(2)

# ---- Active Queries ----
with col_q:
    st.subheader(f"Active Queries ({len(queries)})")
    if not queries:
        st.info("No active queries. Create one on the Queries page.")
    for q in queries:
        with st.container(border=True):
            st.markdown(f"**{q['name']}**")
            if q.get("description"):
                st.caption(q["description"])
            st.code(q["pubmed_query"], language=None)
            st.caption(f"Schedule: `{q.get('schedule_cron', '0 6 * * *')}`")

# ---- Latest Syntheses ----
with col_s:
    st.subheader(f"Latest Syntheses ({len(syntheses)})")
    if not syntheses:
        st.info("No syntheses yet. Run the pipeline to generate evidence summaries.")
    for s in syntheses:
        grade = s.get("evidence_grade", "")
        consensus = s.get("consensus_status", "")
        with st.container(border=True):
            st.markdown(
                f":{_grade_colour(grade)}[**Grade: {grade.upper() if grade else 'N/A'}**]  "
                f"{_consensus_icon(consensus)} {consensus.title() if consensus else ''}"
            )
            st.caption(
                f"Articles: {s.get('article_count', 0)}  |  "
                f"Created: {s.get('created_at', '')[:10]}"
            )
            summary = s.get("summary_text", "")
            if summary:
                st.markdown(summary[:300] + ("…" if len(summary) > 300 else ""))

st.divider()
if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()
