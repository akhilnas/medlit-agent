"""Home page — active clinical queries and latest evidence syntheses."""

import html as _html

import streamlit as st

st.set_page_config(page_title="Home — MedLit Agent", layout="wide")

from dashboard.theme import apply_theme, grade_badge, status_badge, section_header  # noqa: E402

apply_theme()


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


def _consensus_icon(status: str | None) -> str:
    return {
        "consensus":    "◉",
        "conflicting":  "◎",
        "insufficient": "○",
    }.get((status or "").lower(), "○")


client = get_client()

st.title("Home")
st.caption("Active clinical queries and latest evidence syntheses")

try:
    queries_resp  = client.list_queries(is_active=True)
    syntheses_resp = client.list_syntheses(limit=5)
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

queries   = queries_resp.get("data", [])
syntheses = syntheses_resp.get("data", [])

col_q, col_s = st.columns(2)

# ── Active Queries ────────────────────────────────────────────────────────────
with col_q:
    st.markdown(
        section_header("Active Queries", f"{len(queries)} monitored"),
        unsafe_allow_html=True,
    )
    if not queries:
        st.info("No active queries. Create one on the Queries page.")
    for q in queries:
        name    = _html.escape(q.get("name", ""))
        desc    = _html.escape(q.get("description", ""))
        pq      = _html.escape(q.get("pubmed_query", ""))
        cron    = _html.escape(q.get("schedule_cron", "0 6 * * *"))
        desc_el = (
            f'<div style="font-family:var(--font-body);font-size:0.9rem;'
            f'color:var(--text-dim);font-style:italic;margin-bottom:0.55rem;">{desc}</div>'
            if desc else ""
        )
        st.markdown(
            f"""
            <div style="
              background: var(--bg-card);
              border: 1px solid var(--border-2);
              border-left: 3px solid var(--accent-border);
              border-radius: 0 var(--r) var(--r) 0;
              padding: 1rem 1.2rem;
              margin-bottom: 0.75rem;
            ">
              <div style="
                font-family: var(--font-head);
                font-size: 1.1rem;
                letter-spacing: 0.06em;
                color: var(--text);
                margin-bottom: 0.3rem;
              ">{name}</div>
              {desc_el}
              <div style="
                font-family: var(--font-mono);
                font-size: 0.78rem;
                color: var(--teal);
                background: var(--bg-card-2);
                border: 1px solid var(--border-2);
                border-radius: 2px;
                padding: 0.3em 0.6em;
                display: inline-block;
                margin-bottom: 0.5rem;
              ">{pq}</div>
              <div style="
                font-family: var(--font-mono);
                font-size: 0.60rem;
                letter-spacing: 0.12em;
                color: var(--text-faint);
              ">CRON {cron}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Latest Syntheses ──────────────────────────────────────────────────────────
with col_s:
    st.markdown(
        section_header("Latest Syntheses", f"{len(syntheses)} recent"),
        unsafe_allow_html=True,
    )
    if not syntheses:
        st.info("No syntheses yet. Run the pipeline to generate evidence summaries.")
    for s in syntheses:
        grade     = s.get("evidence_grade", "")
        consensus = s.get("consensus_status", "")
        icon      = _consensus_icon(consensus)
        summary   = _html.escape(s.get("summary_text", ""))
        summary_trunc = (summary[:300] + "…") if len(summary) > 300 else summary
        st.markdown(
            f"""
            <div style="
              background: var(--bg-card);
              border: 1px solid var(--border-2);
              border-left: 3px solid var(--border-2);
              border-radius: 0 var(--r) var(--r) 0;
              padding: 1rem 1.2rem;
              margin-bottom: 0.75rem;
            ">
              <div style="
                display: flex;
                align-items: center;
                gap: 0.55rem;
                margin-bottom: 0.4rem;
              ">
                {grade_badge(grade)}
                <span style="
                  font-family: var(--font-mono);
                  font-size: 0.68rem;
                  letter-spacing: 0.10em;
                  color: var(--text-faint);
                ">{icon} {_html.escape(consensus.upper()) if consensus else ''}</span>
              </div>
              <div style="
                font-family: var(--font-mono);
                font-size: 0.60rem;
                letter-spacing: 0.10em;
                color: var(--text-faint);
                margin-bottom: 0.55rem;
              ">{s.get('article_count', 0)} ARTICLES · {_html.escape(s.get('created_at', '')[:10])}</div>
              <div style="
                font-family: var(--font-body);
                font-size: 0.95rem;
                color: var(--text-dim);
                line-height: 1.65;
              ">{summary_trunc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()
if st.button("⟳  Refresh"):
    st.rerun()
