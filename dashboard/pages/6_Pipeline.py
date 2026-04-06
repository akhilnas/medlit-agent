"""Pipeline Status Dashboard — run history, success/failure rates, processing times."""

import streamlit as st

st.set_page_config(page_title="Pipeline — MedLit Agent", layout="wide")

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


client = get_client()

st.title("Pipeline Status")

queries = fetch_queries()
query_options = {"All Queries": None} | {q["name"]: q["id"] for q in queries}

col_filter, col_limit = st.columns([3, 1])
selected_name = col_filter.selectbox("Filter by query", list(query_options.keys()))
selected_id = query_options[selected_name]
limit = col_limit.slider("Show last N runs", 5, 100, 20)

try:
    resp = fetch_runs(selected_id, limit)
    runs = resp.get("data", [])
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

if not runs:
    st.info("No pipeline runs found.")
    st.stop()

# ---- Summary metrics ----
total = len(runs)
completed = sum(1 for r in runs if r.get("status") == "completed")
failed = sum(1 for r in runs if r.get("status") == "failed")
running = sum(1 for r in runs if r.get("status") == "running")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Runs", total)
m2.metric("Completed", completed, delta=f"{completed/total*100:.0f}%" if total else None)
m3.metric("Failed", failed, delta=f"-{failed}" if failed else None, delta_color="inverse")
m4.metric("Running", running)

st.divider()

# ---- Charts ----
if HAS_PLOTLY and runs:
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # Status breakdown pie chart
        status_counts = {}
        for r in runs:
            s = r.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
        fig_pie = px.pie(
            values=list(status_counts.values()),
            names=list(status_counts.keys()),
            title="Run Status Distribution",
            color=list(status_counts.keys()),
            color_discrete_map={
                "completed": "#00cc44",
                "failed": "#ff4444",
                "running": "#4488ff",
                "cancelled": "#aaaaaa",
            },
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        # Articles found per run bar chart
        run_labels = [r.get("started_at", "")[:10] for r in runs[-10:]]
        articles_found = [r.get("articles_found", 0) for r in runs[-10:]]
        articles_extracted = [r.get("articles_extracted", 0) for r in runs[-10:]]
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(name="Found", x=run_labels, y=articles_found, marker_color="#4488ff"))
        fig_bar.add_trace(go.Bar(name="Extracted", x=run_labels, y=articles_extracted, marker_color="#00cc44"))
        fig_bar.update_layout(
            title="Articles per Run (last 10)",
            barmode="group",
            xaxis_title="Run date",
            yaxis_title="Count",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ---- Run history table ----
st.subheader("Run History")
for run in runs:
    status = run.get("status", "unknown")
    colour = {"completed": "green", "failed": "red", "running": "blue", "cancelled": "gray"}.get(status, "gray")
    with st.expander(
        f":{colour}[{status.upper()}]  "
        f"{run.get('started_at', '')[:19]}  |  "
        f"Found: {run.get('articles_found', 0)}  Extracted: {run.get('articles_extracted', 0)}"
    ):
        col1, col2 = st.columns(2)
        col1.markdown(f"**Started:** {run.get('started_at', 'N/A')[:19]}")
        col1.markdown(f"**Completed:** {run.get('completed_at', 'N/A') or 'Still running'}")
        col2.markdown(f"**Trigger:** {run.get('trigger_type', 'N/A')}")
        col2.markdown(f"**ID:** `{run.get('id', '')}`")
        if run.get("error_message"):
            st.error(run["error_message"])

if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()
