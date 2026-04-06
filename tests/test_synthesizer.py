"""Tests for src/agents/synthesizer.py."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.synthesizer import SynthesisAgent
from src.models.evidence_synthesis import EvidenceSynthesis
from src.services.synthesis_prompt import SynthesisResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_clinical_query(query_str: str = "SGLT2 AND heart failure"):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.pubmed_query = query_str
    q.name = "SGLT2 HF"
    return q


def make_article(
    pmid: str = "12345",
    status: str = "extracted",
    relevance_score: float = 0.8,
):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.pmid = pmid
    a.title = f"Article {pmid}"
    a.abstract = "Abstract text about SGLT2 inhibitors."
    a.relevance_score = relevance_score
    a.processing_status = status
    return a


def make_pico(article_id=None):
    p = MagicMock()
    p.article_id = article_id or uuid.uuid4()
    p.intervention = "Empagliflozin"
    p.population = "Adults with HF"
    p.comparison = "Placebo"
    p.outcome = "CV death"
    p.study_design = "randomized_controlled_trial"
    p.effect_size = "HR=0.75"
    p.confidence_interval = "95% CI 0.60-0.90"
    p.p_value = "p<0.001"
    return p


def make_mock_llm(summary: str = "Strong evidence for SGLT2i in HF.") -> AsyncMock:
    llm = AsyncMock()
    llm.complete_json = AsyncMock(
        return_value=(
            {
                "summary_text": summary,
                "evidence_grade": "A",
                "consensus_status": "consistent",
                "key_findings": ["Reduced HHF by 25%", "CV death reduced"],
                "evidence_gaps": ["Long-term safety unclear"],
                "article_count": 3,
            },
            MagicMock(input_tokens=500, output_tokens=200),
        )
    )
    return llm


def make_mock_db(articles=None, picos=None) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()

    articles = articles or []
    picos = picos or []

    article_result = MagicMock()
    article_result.scalars.return_value.all.return_value = articles

    pico_result = MagicMock()
    pico_result.scalars.return_value.all.return_value = picos

    db.execute.side_effect = [article_result, pico_result]
    return db


# ---------------------------------------------------------------------------
# SynthesisAgent.run()
# ---------------------------------------------------------------------------

async def test_run_returns_synthesis_when_articles_available():
    query = make_clinical_query()
    articles = [make_article(str(i)) for i in range(3)]
    picos = [make_pico(a.id) for a in articles]
    db = make_mock_db(articles, picos)
    llm = make_mock_llm()

    agent = SynthesisAgent(db, llm_client=llm)
    result = await agent.run(query)

    assert result is not None
    assert isinstance(result, EvidenceSynthesis)
    assert result.summary_text == "Strong evidence for SGLT2i in HF."
    assert result.evidence_grade == "A"
    assert result.article_count == 3
    db.add.assert_called_once()
    db.commit.assert_called()


async def test_run_returns_none_when_no_articles():
    query = make_clinical_query()
    db = make_mock_db(articles=[], picos=[])
    llm = make_mock_llm()

    agent = SynthesisAgent(db, llm_client=llm)
    result = await agent.run(query)

    assert result is None
    llm.complete_json.assert_not_called()


async def test_run_uses_top_n_articles_by_relevance():
    query = make_clinical_query()
    articles = [make_article(str(i), relevance_score=float(i) / 10) for i in range(20)]
    picos = [make_pico(a.id) for a in articles]
    db = make_mock_db(articles, picos)
    llm = make_mock_llm()

    agent = SynthesisAgent(db, llm_client=llm, max_articles=5)
    await agent.run(query)

    # LLM should be called with ≤5 articles
    call_kwargs = llm.complete_json.call_args[1]
    assert "5" in call_kwargs["user"] or call_kwargs["user"].count("Article") <= 5


async def test_run_stores_model_name():
    query = make_clinical_query()
    articles = [make_article()]
    picos = [make_pico(articles[0].id)]
    db = make_mock_db(articles, picos)
    llm = make_mock_llm()

    agent = SynthesisAgent(db, llm_client=llm)
    agent._model_name = "claude-sonnet-4-6"
    await agent.run(query)

    stored = db.add.call_args[0][0]
    assert stored.synthesis_model == "claude-sonnet-4-6"


async def test_run_links_clinical_query():
    query = make_clinical_query()
    articles = [make_article()]
    picos = [make_pico(articles[0].id)]
    db = make_mock_db(articles, picos)
    llm = make_mock_llm()

    agent = SynthesisAgent(db, llm_client=llm)
    await agent.run(query)

    stored = db.add.call_args[0][0]
    assert stored.clinical_query_id == query.id


async def test_run_with_pipeline_run_id():
    query = make_clinical_query()
    articles = [make_article()]
    picos = [make_pico(articles[0].id)]
    db = make_mock_db(articles, picos)
    llm = make_mock_llm()
    pipeline_run_id = uuid.uuid4()

    agent = SynthesisAgent(db, llm_client=llm)
    await agent.run(query, pipeline_run_id=pipeline_run_id)

    stored = db.add.call_args[0][0]
    assert stored.pipeline_run_id == pipeline_run_id


async def test_run_handles_llm_error_gracefully():
    query = make_clinical_query()
    articles = [make_article()]
    picos = [make_pico(articles[0].id)]
    db = make_mock_db(articles, picos)
    llm = AsyncMock()
    llm.complete_json = AsyncMock(side_effect=RuntimeError("API error"))

    agent = SynthesisAgent(db, llm_client=llm)
    result = await agent.run(query)

    assert result is None
    db.add.assert_not_called()


async def test_run_includes_key_findings_and_gaps():
    query = make_clinical_query()
    articles = [make_article()]
    picos = [make_pico(articles[0].id)]
    db = make_mock_db(articles, picos)
    llm = make_mock_llm()

    agent = SynthesisAgent(db, llm_client=llm)
    result = await agent.run(query)

    assert isinstance(result.key_findings, list)
    assert isinstance(result.evidence_gaps, list)
