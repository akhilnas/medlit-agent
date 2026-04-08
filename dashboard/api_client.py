"""Synchronous httpx client for the MedLit FastAPI backend.

Uses a synchronous httpx.Client (not async) because Streamlit runs its own
event loop and mixing asyncio inside Streamlit callbacks causes errors.

The client is designed to be cached via ``@st.cache_resource`` so the
connection pool is reused across Streamlit reruns.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_BASE_URL = os.environ.get("MEDLIT_API_URL", "http://localhost:8000")
_API_KEY = os.environ.get("API_KEY", "")
_TIMEOUT = 30.0
_PIPELINE_TIMEOUT = 600.0  # full pipeline can take several minutes


class MedlitAPIClient:
    """Thin wrapper around the MedLit FastAPI backend."""

    def __init__(self, base_url: str = _BASE_URL) -> None:
        headers = {"X-API-Key": _API_KEY} if _API_KEY else {}
        self._client = httpx.Client(base_url=base_url, timeout=_TIMEOUT, headers=headers)

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # Clinical queries
    # ------------------------------------------------------------------

    def list_queries(
        self,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        params: dict = {"limit": limit, "offset": offset}
        if is_active is not None:
            params["is_active"] = is_active
        return self._get("/v1/queries", params=params)

    def get_query(self, query_id: str) -> dict:
        return self._get(f"/v1/queries/{query_id}")

    def create_query(self, payload: dict) -> dict:
        return self._post("/v1/queries", json=payload)

    def update_query(self, query_id: str, payload: dict) -> dict:
        return self._patch(f"/v1/queries/{query_id}", json=payload)

    def delete_query(self, query_id: str) -> None:
        self._delete(f"/v1/queries/{query_id}")

    # ------------------------------------------------------------------
    # Articles
    # ------------------------------------------------------------------

    def list_articles(
        self,
        query_id: str | None = None,
        processing_status: str | None = None,
        study_design: str | None = None,
        evidence_level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        params: dict = {"limit": limit, "offset": offset}
        if query_id:
            params["clinical_query_id"] = query_id
        if processing_status:
            params["processing_status"] = processing_status
        if study_design:
            params["study_design"] = study_design
        if evidence_level:
            params["evidence_level"] = evidence_level
        return self._get("/v1/articles", params=params)

    def search_articles(self, payload: dict) -> dict:
        return self._post("/v1/articles/search", json=payload)

    # ------------------------------------------------------------------
    # Syntheses
    # ------------------------------------------------------------------

    def list_syntheses(self, query_id: str | None = None, limit: int = 20) -> dict:
        params: dict = {"limit": limit}
        if query_id:
            params["query_id"] = query_id
        return self._get("/v1/syntheses", params=params)

    def get_synthesis(self, synthesis_id: str) -> dict:
        return self._get(f"/v1/syntheses/{synthesis_id}")

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def trigger_pipeline(
        self,
        query_id: str,
        trigger_type: str = "manual",
        max_results: int = 20,
    ) -> dict:
        return self._post(
            "/v1/pipeline/trigger",
            json={
                "query_id": query_id,
                "trigger_type": trigger_type,
                "max_results": max_results,
            },
        )

    def run_full_pipeline(self, query_id: str) -> dict:
        return self._post("/v1/pipeline/run", json={"query_id": query_id}, timeout=_PIPELINE_TIMEOUT)

    def list_pipeline_runs(
        self,
        query_id: str | None = None,
        limit: int = 20,
    ) -> dict:
        params: dict = {"limit": limit}
        if query_id:
            params["query_id"] = query_id
        return self._get("/v1/pipeline/runs", params=params)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> Any:
        r = self._client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: dict | None = None, timeout: float | None = None) -> Any:
        r = self._client.post(path, json=json, timeout=timeout or _TIMEOUT)
        r.raise_for_status()
        return r.json()

    def _patch(self, path: str, json: dict | None = None) -> Any:
        r = self._client.patch(path, json=json)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> None:
        r = self._client.delete(path)
        r.raise_for_status()
