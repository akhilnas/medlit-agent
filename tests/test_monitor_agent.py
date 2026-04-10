"""Tests for src/agents/monitor.py.

The DB session and PubMedClient are both injected mocks so no real database
or network calls are made.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.monitor import MonitorAgent, _score_relevance
from src.services.pubmed_client import ArticleData, AuthorData
from tests.conftest import make_clinical_query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_article_data(
    pmid: str = "12345",
    title: str = "SGLT2 inhibitors in heart failure patients",
    abstract: str = "We investigated SGLT2 inhibitors for heart failure treatment.",
    mesh_headings: list[str] | None = None,
) -> ArticleData:
    return ArticleData(
        pmid=pmid,
        title=title,
        abstract=abstract,
        authors=[AuthorData(name="John Smith", affiliation="MIT")],
        journal="NEJM",
        publication_date=date(2024, 3, 15),
        doi="10.1234/test",
        mesh_headings=mesh_headings or ["Heart Failure"],
        article_type="Randomized Controlled Trial",
    )


def make_mock_pubmed(
    pmids: list[str] | None = None,
    articles: list[ArticleData] | None = None,
) -> MagicMock:
    """PubMedClient mock with pre-configured esearch/efetch responses."""
    client = MagicMock()
    client.esearch = AsyncMock(return_value=pmids or [])
    client.efetch = AsyncMock(return_value=articles or [])
    return client


def make_mock_db(existing_pmids: list[str] | None = None) -> AsyncMock:
    """AsyncSession mock whose execute() returns given existing PMIDs for dedup."""
    db = AsyncMock()
    db.add = MagicMock()
    # _deduplicate iterates directly over the execute result
    db.execute.return_value = [(p,) for p in (existing_pmids or [])]
    return db


# ---------------------------------------------------------------------------
# _score_relevance unit tests
# ---------------------------------------------------------------------------

def test_score_relevance_matching_keywords():
    query = make_clinical_query(
        name="SGLT2 Heart Failure",
        pubmed_query="SGLT2 inhibitors heart failure",
        mesh_terms=["Heart Failure"],
        description=None,
    )
    article = make_article_data(
        title="SGLT2 inhibitors in heart failure",
        abstract="Randomized trial of SGLT2 inhibitors.",
    )
    score = _score_relevance(article, query)
    assert score > 0.0
    assert score <= 1.0


def test_score_relevance_no_keyword_match():
    query = make_clinical_query(
        name="SGLT2 Heart Failure",
        pubmed_query="SGLT2 inhibitors heart failure",
        mesh_terms=[],
        description=None,
    )
    article = make_article_data(
        title="Unrelated ophthalmology study",
        abstract="We examined retinal detachment.",
        mesh_headings=["Retinal Detachment"],
    )
    score = _score_relevance(article, query)
    assert score == 0.0


def test_score_relevance_returns_half_when_query_has_no_keywords():
    # Query whose words are all stop-words or very short → no keywords
    query = make_clinical_query(
        name="A or",
        pubmed_query="a b c",  # all ≤2 chars
        mesh_terms=[],
        description=None,
    )
    article = make_article_data()
    assert _score_relevance(article, query) == 0.5


def test_score_relevance_capped_at_one():
    query = make_clinical_query(
        name="SGLT2 inhibitors heart failure treatment",
        pubmed_query="SGLT2 heart failure",
        mesh_terms=["Heart Failure", "SGLT2 Inhibitors"],
    )
    # Article that explicitly contains every keyword
    article = make_article_data(
        title="SGLT2 inhibitors for heart failure treatment outcomes",
        abstract="SGLT2 inhibitors significantly reduce heart failure hospitalization.",
        mesh_headings=["Heart Failure", "SGLT2 Inhibitors"],
    )
    score = _score_relevance(article, query)
    assert score <= 1.0


def test_score_relevance_uses_mesh_headings():
    query = make_clinical_query(
        name="query",
        pubmed_query="diabetes",
        mesh_terms=["Diabetes Mellitus"],
        description=None,
    )
    article = make_article_data(
        title="Glucose study",
        abstract="We looked at glucose.",
        mesh_headings=["Diabetes Mellitus"],
    )
    score = _score_relevance(article, query)
    assert score > 0.0


# ---------------------------------------------------------------------------
# MonitorAgent.run() — happy path
# ---------------------------------------------------------------------------

async def test_run_inserts_new_articles():
    # min_relevance_score=0.4 — below the article's keyword-overlap score (~0.57)
    query = make_clinical_query(min_relevance_score=0.4)
    article = make_article_data()
    pubmed = make_mock_pubmed(pmids=["12345"], articles=[article])
    db = make_mock_db(existing_pmids=[])

    agent = MonitorAgent(db, pubmed_client=pubmed)
    run = await agent.run(query, trigger_type="api")

    assert run.status == "completed"
    assert run.articles_found == 1
    assert run.articles_extracted == 1
    # One Article was added to the session
    assert db.add.call_count >= 3  # PipelineRun + PipelineStep + Article
    db.commit.assert_called_once()


async def test_run_deduplicates_existing_pmids():
    query = make_clinical_query(min_relevance_score=0.0)
    article = make_article_data(pmid="12345")
    pubmed = make_mock_pubmed(pmids=["12345"], articles=[article])
    db = make_mock_db(existing_pmids=["12345"])  # already known

    agent = MonitorAgent(db, pubmed_client=pubmed)
    run = await agent.run(query)

    assert run.status == "completed"
    assert run.articles_found == 1
    assert run.articles_extracted == 0
    # efetch should NOT be called — no new PMIDs to fetch
    pubmed.efetch.assert_not_called()


async def test_run_empty_search_results():
    query = make_clinical_query(min_relevance_score=0.0)
    pubmed = make_mock_pubmed(pmids=[], articles=[])
    db = make_mock_db()

    agent = MonitorAgent(db, pubmed_client=pubmed)
    run = await agent.run(query)

    assert run.status == "completed"
    assert run.articles_found == 0
    assert run.articles_extracted == 0
    pubmed.efetch.assert_not_called()


async def test_run_below_threshold_articles_skipped():
    query = make_clinical_query(min_relevance_score=0.99)  # very high threshold
    article = make_article_data(
        title="Unrelated article about ophthalmology",
        abstract="Retinal detachment study.",
        mesh_headings=["Retinal Detachment"],
    )
    pubmed = make_mock_pubmed(pmids=["99"], articles=[article])
    db = make_mock_db(existing_pmids=[])

    agent = MonitorAgent(db, pubmed_client=pubmed)
    run = await agent.run(query)

    assert run.status == "completed"
    assert run.articles_extracted == 0


async def test_run_marks_pipeline_failed_on_pubmed_error():
    query = make_clinical_query()
    pubmed = MagicMock()
    pubmed.esearch = AsyncMock(side_effect=RuntimeError("network error"))
    db = make_mock_db()

    agent = MonitorAgent(db, pubmed_client=pubmed)
    with pytest.raises(RuntimeError, match="network error"):
        await agent.run(query)

    # commit is still called (to persist the failed state)
    db.commit.assert_called_once()


async def test_run_trigger_type_recorded():
    query = make_clinical_query(min_relevance_score=0.0)
    pubmed = make_mock_pubmed(pmids=[], articles=[])
    db = make_mock_db()

    agent = MonitorAgent(db, pubmed_client=pubmed)
    run = await agent.run(query, trigger_type="scheduled")

    assert run.trigger_type == "scheduled"


async def test_run_passes_date_range_to_esearch():
    query = make_clinical_query(min_relevance_score=0.0)
    pubmed = make_mock_pubmed(pmids=[], articles=[])
    db = make_mock_db()

    agent = MonitorAgent(db, pubmed_client=pubmed)
    await agent.run(query, date_range=("2024/01/01", "2024/12/31"))

    pubmed.esearch.assert_called_once_with(
        query.pubmed_query,
        max_results=100,
        date_range=("2024/01/01", "2024/12/31"),
    )


async def test_run_multiple_articles_partial_below_threshold():
    query = make_clinical_query(min_relevance_score=0.4)
    articles = [
        make_article_data(pmid="1", title="SGLT2 heart failure study"),
        make_article_data(pmid="2", title="SGLT2 heart failure outcomes"),
    ]
    pubmed = make_mock_pubmed(pmids=["1", "2"], articles=articles)
    db = make_mock_db(existing_pmids=[])

    agent = MonitorAgent(db, pubmed_client=pubmed)
    run = await agent.run(query)

    assert run.articles_extracted == 2


async def test_run_creates_pipeline_step_with_monitor_name():
    query = make_clinical_query(min_relevance_score=0.0)
    pubmed = make_mock_pubmed(pmids=[], articles=[])
    db = make_mock_db()

    agent = MonitorAgent(db, pubmed_client=pubmed)
    await agent.run(query)

    # Check that a PipelineStep with step_name="monitor" was added
    added_objects = [c.args[0] for c in db.add.call_args_list]
    from src.models.pipeline import PipelineStep
    steps = [o for o in added_objects if isinstance(o, PipelineStep)]
    assert len(steps) == 1
    assert steps[0].step_name == "monitor"


async def test_run_uses_injected_pubmed_client():
    """When a client is injected, it should be used (not a new one created)."""
    query = make_clinical_query(min_relevance_score=0.0)
    pubmed = make_mock_pubmed(pmids=[], articles=[])
    db = make_mock_db()

    with patch("src.agents.monitor.PubMedClient") as MockClient:
        agent = MonitorAgent(db, pubmed_client=pubmed)
        await agent.run(query)
        MockClient.assert_not_called()  # injected client was used instead
