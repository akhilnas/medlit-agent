"""Evidence Synthesis Viewer — narrative summaries, key findings, evidence gaps."""

import streamlit as st

st.set_page_config(page_title="Syntheses — MedLit Agent", layout="wide")


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


@st.cache_data(ttl=30)
def fetch_queries():
    return get_client().list_queries().get("data", [])


def _grade_badge(grade: str | None) -> str:
    colours = {"strong": "green", "moderate": "blue", "weak": "orange", "insufficient": "red"}
    g = (grade or "unknown").lower()
    return f":{colours.get(g, 'gray')}[**{g.upper()}**]"


def _consensus_badge(status: str | None) -> str:
    colours = {"consensus": "green", "conflicting": "orange", "insufficient": "red"}
    s = (status or "unknown").lower()
    return f":{colours.get(s, 'gray')}[{s.title()}]"


client = get_client()

st.title("Evidence Syntheses")

queries = fetch_queries()
query_options = {"All Queries": None} | {q["name"]: q["id"] for q in queries}

selected_query_name = st.selectbox("Filter by query", list(query_options.keys()))
selected_query_id = query_options[selected_query_name]

try:
    resp = client.list_syntheses(query_id=selected_query_id, limit=20)
    syntheses = resp.get("data", [])
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

if not syntheses:
    st.info("No syntheses found. Run the pipeline to generate evidence summaries.")
    st.stop()

# ---- Synthesis list ----
selected_id = st.selectbox(
    "Select synthesis",
    options=[s["id"] for s in syntheses],
    format_func=lambda sid: next(
        (
            f"{s.get('evidence_grade', 'N/A').upper()} — "
            f"{s.get('article_count', 0)} articles — "
            f"{s.get('created_at', '')[:10]}"
            for s in syntheses if s["id"] == sid
        ),
        sid,
    ),
)

if not selected_id:
    st.stop()

try:
    s = client.get_synthesis(selected_id)
except Exception as exc:
    st.error(f"Failed to load synthesis: {exc}")
    st.stop()

# ---- Synthesis detail ----
col_grade, col_consensus, col_count = st.columns(3)
col_grade.metric("Evidence Grade", (s.get("evidence_grade") or "N/A").upper())
col_consensus.metric("Consensus", (s.get("consensus_status") or "N/A").title())
col_count.metric("Articles Included", s.get("article_count", 0))

st.divider()

st.subheader("Summary")
st.markdown(s.get("summary_text", "_No summary available._"))

key_findings = s.get("key_findings") or []
if key_findings:
    st.subheader("Key Findings")
    for i, finding in enumerate(key_findings, 1):
        if isinstance(finding, dict):
            st.info(f"**{i}.** {finding.get('finding') or finding.get('text') or str(finding)}")
        else:
            st.info(f"**{i}.** {finding}")

evidence_gaps = s.get("evidence_gaps") or []
if evidence_gaps:
    st.subheader("Evidence Gaps")
    for gap in evidence_gaps:
        if isinstance(gap, dict):
            st.warning(gap.get("gap") or gap.get("text") or str(gap))
        else:
            st.warning(gap)

st.caption(
    f"Generated: {s.get('created_at', '')[:19]}  |  "
    f"Model: {s.get('synthesis_model', 'N/A')}"
)
