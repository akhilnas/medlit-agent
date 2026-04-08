"""Pipeline Status Dashboard — run history, success/failure rates, processing times."""

import html as _html

import streamlit as st

st.set_page_config(page_title="Pipeline — MedLit Agent", layout="wide")

from dashboard.auth import require_login  # noqa: E402
from dashboard.theme import apply_theme, status_badge, PLOTLY_LAYOUT  # noqa: E402

require_login()
apply_theme()

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


@st.cache_data(ttl=15)
def fetch_queries():
    return get_client().list_queries().get("data", [])


@st.cache_data(ttl=15)
def fetch_runs(query_id: str | None, limit: int):
    return get_client().list_pipeline_runs(query_id=query_id, limit=limit)


client  = get_client()
queries = fetch_queries()

st.title("Pipeline Status")

query_options  = {"All Queries": None} | {q["name"]: q["id"] for q in queries}
col_filter, col_limit = st.columns([3, 1])
selected_name  = col_filter.selectbox("Filter by query", list(query_options.keys()))
selected_id    = query_options[selected_name]
limit          = col_limit.slider("Show last N runs", 5, 100, 20)

try:
    resp = fetch_runs(selected_id, limit)
    runs = resp.get("data", [])
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

if not runs:
    st.info("No pipeline runs found.")
    st.stop()

# ── Summary metrics ───────────────────────────────────────────────────────────
total     = len(runs)
completed = sum(1 for r in runs if r.get("status") == "completed")
failed    = sum(1 for r in runs if r.get("status") == "failed")
running   = sum(1 for r in runs if r.get("status") == "running")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Runs",  total)
m2.metric("Completed",   completed, delta=f"{completed/total*100:.0f}%" if total else None)
m3.metric("Failed",      failed,    delta=f"-{failed}" if failed else None, delta_color="inverse")
m4.metric("Running",     running)

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
if HAS_PLOTLY and runs:
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        status_counts: dict[str, int] = {}
        for r in runs:
            s = r.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        fig_pie = px.pie(
            values=list(status_counts.values()),
            names=list(status_counts.keys()),
            title="Run Status Distribution",
            color=list(status_counts.keys()),
            color_discrete_map={
                "completed": "#52b788",
                "failed":    "#e05c5c",
                "running":   "#4aacc8",
                "cancelled": "#3d4160",
            },
            hole=0.45,
        )
        fig_pie.update_layout(**PLOTLY_LAYOUT)
        fig_pie.update_traces(
            textfont={"family": "Azeret Mono, monospace", "size": 9},
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        run_labels        = [r.get("started_at", "")[:10] for r in runs[-10:]]
        articles_found    = [r.get("articles_found",    0) for r in runs[-10:]]
        articles_extracted = [r.get("articles_extracted", 0) for r in runs[-10:]]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            name="Found",
            x=run_labels, y=articles_found,
            marker_color="#4aacc8",
            marker_opacity=0.85,
        ))
        fig_bar.add_trace(go.Bar(
            name="Extracted",
            x=run_labels, y=articles_extracted,
            marker_color="#52b788",
            marker_opacity=0.85,
        ))
        bar_layout = {**PLOTLY_LAYOUT, "barmode": "group"}
        bar_layout["title_text"] = "Articles per Run (last 10)"
        bar_layout["xaxis"] = {**PLOTLY_LAYOUT["xaxis"], "title": {"text": "Run date"}}
        bar_layout["yaxis"] = {**PLOTLY_LAYOUT["yaxis"], "title": {"text": "Count"}}
        fig_bar.update_layout(**bar_layout)
        st.plotly_chart(fig_bar, use_container_width=True)

# ── Run history ───────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-family:var(--font-mono);font-size:0.62rem;letter-spacing:0.20em;'
    'text-transform:uppercase;color:var(--text-faint);margin-bottom:0.75rem;">'
    'Run History</div>',
    unsafe_allow_html=True,
)

for run in runs:
    run_status = run.get("status", "unknown")
    started    = run.get("started_at", "")[:19]
    found      = run.get("articles_found", 0)
    extracted  = run.get("articles_extracted", 0)

    badge_html = status_badge(run_status)
    header = (
        f"{started}"
        f"  ·  found {found}"
        f"  ·  extracted {extracted}"
    )

    with st.expander(header):
        st.markdown(
            f'<div style="margin-bottom:0.75rem;">{badge_html}</div>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        completed_str = (run.get("completed_at") or "Still running")[:19]
        col1.markdown(
            f'<div style="font-family:var(--font-mono);font-size:0.72rem;'
            f'color:var(--text-dim);line-height:1.8;">'
            f'<span style="color:var(--text-faint);">Started&nbsp;&nbsp;&nbsp;</span> {run.get("started_at","N/A")[:19]}<br>'
            f'<span style="color:var(--text-faint);">Completed</span> {completed_str}'
            f'</div>',
            unsafe_allow_html=True,
        )
        col2.markdown(
            f'<div style="font-family:var(--font-mono);font-size:0.72rem;'
            f'color:var(--text-dim);line-height:1.8;">'
            f'<span style="color:var(--text-faint);">Trigger</span> {_html.escape(run.get("trigger_type","N/A"))}<br>'
            f'<span style="color:var(--text-faint);">Run ID&nbsp;</span> {_html.escape(str(run.get("id",""))[:8])}…'
            f'</div>',
            unsafe_allow_html=True,
        )
        if run.get("error_message"):
            st.markdown(
                f'<div style="font-family:var(--font-mono);font-size:0.75rem;'
                f'color:var(--rose);background:var(--rose-dim);border:1px solid var(--rose);'
                f'border-radius:var(--r);padding:0.6rem 0.9rem;margin-top:0.6rem;">'
                f'{_html.escape(run["error_message"])}</div>',
                unsafe_allow_html=True,
            )

st.divider()
if st.button("⟳  Refresh"):
    st.cache_data.clear()
    st.rerun()
