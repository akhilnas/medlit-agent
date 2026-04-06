"""Clinical Query Management — CRUD + pipeline trigger."""

import streamlit as st

st.set_page_config(page_title="Queries — MedLit Agent", layout="wide")


@st.cache_resource
def get_client():
    from dashboard.api_client import MedlitAPIClient
    return MedlitAPIClient()


client = get_client()

st.title("Clinical Queries")

# ---- Fetch all queries ----
try:
    resp = client.list_queries()
    queries = resp.get("data", [])
except Exception as exc:
    st.error(f"Cannot reach the MedLit API: {exc}")
    st.stop()

# ---- Create new query form ----
with st.expander("+ Create New Query", expanded=False):
    with st.form("create_query_form"):
        name = st.text_input("Name *", placeholder="SGLT2 in Heart Failure")
        description = st.text_area("Description", placeholder="Optional clinical context")
        pubmed_query = st.text_input(
            "PubMed Query *", placeholder="SGLT2 inhibitors heart failure"
        )
        mesh_terms_raw = st.text_input(
            "MeSH Terms (comma-separated)", placeholder="Heart Failure, SGLT2 Inhibitors"
        )
        col1, col2 = st.columns(2)
        min_relevance = col1.slider("Min Relevance Score", 0.0, 1.0, 0.7, 0.05)
        schedule_cron = col2.text_input("Schedule (cron)", value="0 6 * * *")
        is_active = st.checkbox("Active", value=True)
        submitted = st.form_submit_button("Create Query")

    if submitted:
        if not name or not pubmed_query:
            st.error("Name and PubMed Query are required.")
        else:
            mesh_terms = [t.strip() for t in mesh_terms_raw.split(",") if t.strip()]
            try:
                client.create_query({
                    "name": name,
                    "description": description or None,
                    "pubmed_query": pubmed_query,
                    "mesh_terms": mesh_terms,
                    "min_relevance_score": min_relevance,
                    "schedule_cron": schedule_cron,
                    "is_active": is_active,
                })
                st.success(f"Query '{name}' created.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to create query: {exc}")

st.divider()

# ---- Query list ----
if not queries:
    st.info("No queries found. Create one above.")
else:
    for q in queries:
        with st.container(border=True):
            col_info, col_actions = st.columns([3, 1])
            with col_info:
                status_badge = ":green[Active]" if q.get("is_active") else ":red[Inactive]"
                st.markdown(f"**{q['name']}** — {status_badge}")
                if q.get("description"):
                    st.caption(q["description"])
                st.code(q["pubmed_query"], language=None)
                st.caption(f"Min relevance: {q.get('min_relevance_score', 0.7)}  |  Schedule: `{q.get('schedule_cron', '0 6 * * *')}`")

            with col_actions:
                qid = q["id"]

                if st.button("Run Pipeline", key=f"run_{qid}", type="primary"):
                    with st.spinner("Running full pipeline…"):
                        try:
                            result = client.run_full_pipeline(qid)
                            st.success(
                                f"Pipeline {result.get('phase')}. "
                                f"Found {result.get('articles_found', 0)}, "
                                f"extracted {result.get('articles_extracted', 0)}."
                            )
                        except Exception as exc:
                            st.error(f"Pipeline failed: {exc}")

                if st.button(
                    "Deactivate" if q.get("is_active") else "Activate",
                    key=f"toggle_{qid}",
                ):
                    try:
                        client.update_query(qid, {"is_active": not q.get("is_active")})
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Update failed: {exc}")

                if st.button("Delete", key=f"delete_{qid}", type="secondary"):
                    if st.session_state.get(f"confirm_delete_{qid}"):
                        try:
                            client.delete_query(qid)
                            st.success("Query deleted.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Delete failed: {exc}")
                    else:
                        st.session_state[f"confirm_delete_{qid}"] = True
                        st.warning("Click Delete again to confirm.")
