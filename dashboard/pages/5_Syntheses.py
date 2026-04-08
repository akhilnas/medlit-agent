"""Evidence Synthesis Viewer — narrative summaries, key findings, evidence gaps."""

import html as _html

import streamlit as st

st.set_page_config(page_title="Syntheses — MedLit Agent", layout="wide")

from dashboard.auth import require_login  # noqa: E402
from dashboard.theme import apply_theme, grade_badge, status_badge  # noqa: E402

require_login()
apply_theme()


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


@st.cache_data(ttl=30)
def fetch_queries():
    return get_client().list_queries().get("data", [])


client  = get_client()
queries = fetch_queries()

st.title("Evidence Syntheses")

query_options      = {"All Queries": None} | {q["name"]: q["id"] for q in queries}
selected_query_name = st.selectbox("Filter by query", list(query_options.keys()))
selected_query_id   = query_options[selected_query_name]

try:
    resp      = client.list_syntheses(query_id=selected_query_id, limit=20)
    syntheses = resp.get("data", [])
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

if not syntheses:
    st.info("No syntheses found. Run the pipeline to generate evidence summaries.")
    st.stop()

# ── Synthesis selector ────────────────────────────────────────────────────────
selected_id = st.selectbox(
    "Select synthesis",
    options=[s["id"] for s in syntheses],
    format_func=lambda sid: next(
        (
            f"{s.get('evidence_grade', 'N/A').upper()}  ·  "
            f"{s.get('article_count', 0)} articles  ·  "
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

# ── Synthesis header ──────────────────────────────────────────────────────────
grade     = s.get("evidence_grade") or "N/A"
consensus = s.get("consensus_status") or "N/A"
count     = s.get("article_count", 0)

st.markdown(
    f"""
    <div style="
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1.5rem;
      padding: 1rem 1.4rem;
      background: var(--bg-card);
      border: 1px solid var(--border-2);
      border-left: 3px solid var(--accent-border);
      border-radius: 0 var(--r) var(--r) 0;
    ">
      <div>
        <div style="
          font-family: var(--font-mono);
          font-size: 0.58rem;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: var(--text-faint);
          margin-bottom: 0.25rem;
        ">Evidence Grade</div>
        {grade_badge(grade)}
      </div>
      <div style="width:1px;height:32px;background:var(--border-2);margin:0 0.25rem;"></div>
      <div>
        <div style="
          font-family: var(--font-mono);
          font-size: 0.58rem;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: var(--text-faint);
          margin-bottom: 0.25rem;
        ">Consensus</div>
        {status_badge(consensus)}
      </div>
      <div style="width:1px;height:32px;background:var(--border-2);margin:0 0.25rem;"></div>
      <div>
        <div style="
          font-family: var(--font-mono);
          font-size: 0.58rem;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: var(--text-faint);
          margin-bottom: 0.25rem;
        ">Articles</div>
        <span style="
          font-family: var(--font-mono);
          font-size: 1.5rem;
          font-weight: 300;
          color: var(--teal);
        ">{count}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ── Summary ───────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-family:var(--font-mono);font-size:0.62rem;letter-spacing:0.18em;'
    'text-transform:uppercase;color:var(--text-faint);margin-bottom:0.75rem;">'
    'Summary</div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div style="font-family:var(--font-body);font-size:1.1rem;line-height:1.85;'
    f'color:var(--text);max-width:800px;">'
    f'{_html.escape(s.get("summary_text", "") or "_No summary available._")}'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Key Findings ──────────────────────────────────────────────────────────────
key_findings = s.get("key_findings") or []
if key_findings:
    st.divider()
    st.markdown(
        '<div style="font-family:var(--font-mono);font-size:0.62rem;letter-spacing:0.18em;'
        'text-transform:uppercase;color:var(--text-faint);margin-bottom:0.75rem;">'
        'Key Findings</div>',
        unsafe_allow_html=True,
    )
    for i, finding in enumerate(key_findings, 1):
        raw  = finding.get("finding") or finding.get("text") or str(finding) \
               if isinstance(finding, dict) else str(finding)
        text = _html.escape(raw)
        st.markdown(
            f"""
            <div style="
              display: flex;
              gap: 0.9rem;
              background: var(--bg-card);
              border: 1px solid var(--border-2);
              border-radius: var(--r);
              padding: 0.75rem 1rem;
              margin-bottom: 0.5rem;
              align-items: flex-start;
            ">
              <span style="
                font-family: var(--font-mono);
                font-size: 0.72rem;
                font-weight: 500;
                color: var(--accent);
                min-width: 1.4rem;
                padding-top: 0.1rem;
              ">{i:02d}</span>
              <span style="
                font-family: var(--font-body);
                font-size: 1rem;
                color: var(--text-dim);
                line-height: 1.65;
              ">{text}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Evidence Gaps ─────────────────────────────────────────────────────────────
evidence_gaps = s.get("evidence_gaps") or []
if evidence_gaps:
    st.divider()
    st.markdown(
        '<div style="font-family:var(--font-mono);font-size:0.62rem;letter-spacing:0.18em;'
        'text-transform:uppercase;color:var(--text-faint);margin-bottom:0.75rem;">'
        'Evidence Gaps</div>',
        unsafe_allow_html=True,
    )
    for gap in evidence_gaps:
        raw  = gap.get("gap") or gap.get("text") or str(gap) \
               if isinstance(gap, dict) else str(gap)
        text = _html.escape(raw)
        st.markdown(
            f"""
            <div style="
              display: flex;
              gap: 0.75rem;
              background: var(--bg-card);
              border: 1px solid var(--border-2);
              border-left: 3px solid var(--rose-dim);
              border-radius: 0 var(--r) var(--r) 0;
              padding: 0.7rem 1rem;
              margin-bottom: 0.45rem;
              align-items: flex-start;
            ">
              <span style="
                font-family: var(--font-mono);
                font-size: 0.72rem;
                color: var(--rose);
                min-width: 0.9rem;
              ">△</span>
              <span style="
                font-family: var(--font-body);
                font-size: 1rem;
                color: var(--text-dim);
                line-height: 1.65;
              ">{text}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    f'<div style="font-family:var(--font-mono);font-size:0.60rem;letter-spacing:0.10em;'
    f'color:var(--text-faint);">'
    f'Generated {s.get("created_at", "")[:19]}'
    f'&nbsp;&nbsp;·&nbsp;&nbsp;'
    f'Model {s.get("synthesis_model", "N/A")}'
    f'</div>',
    unsafe_allow_html=True,
)
