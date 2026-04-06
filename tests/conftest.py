"""Shared fixtures and helpers for the test suite."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.models.clinical_query import ClinicalQuery

FIXED_TIME = datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------

def make_clinical_query(**overrides) -> ClinicalQuery:
    defaults = dict(
        id=uuid.uuid4(),
        name="SGLT2 Heart Failure",
        description="Monitoring SGLT2i evidence in HF",
        pubmed_query="SGLT2 inhibitors AND heart failure",
        mesh_terms=["Heart Failure", "SGLT2 Inhibitors"],
        min_relevance_score=0.0,  # 0.0 so all articles pass threshold in most tests
        is_active=True,
        schedule_cron="0 6 * * 1",
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    defaults.update(overrides)
    return ClinicalQuery(**defaults)


@pytest.fixture
def sample_query() -> ClinicalQuery:
    return make_clinical_query()


# ---------------------------------------------------------------------------
# DB mock helpers
# ---------------------------------------------------------------------------

def scalar_result(value: int) -> MagicMock:
    """Mock execute() result supporting .scalar_one()."""
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def rows_result(rows: list) -> MagicMock:
    """Mock execute() result supporting .scalars().all()."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    return r


@pytest.fixture
def mock_db() -> AsyncMock:
    """AsyncMock AsyncSession with a refresh side-effect that stamps timestamps."""
    db = AsyncMock()
    db.add = MagicMock()

    async def _refresh(obj) -> None:
        if not getattr(obj, "created_at", None):
            obj.created_at = FIXED_TIME
        if not getattr(obj, "updated_at", None):
            obj.updated_at = FIXED_TIME

    db.refresh.side_effect = _refresh
    return db


# ---------------------------------------------------------------------------
# FastAPI test client with DB override
# ---------------------------------------------------------------------------

@pytest.fixture
def app_with_db(mock_db):
    """FastAPI app with get_db replaced by mock_db."""
    from main import app
    from src.core.database import get_db

    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def api_client(app_with_db):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_db), base_url="http://test"
    ) as c:
        yield c
