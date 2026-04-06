"""Tests for src/agents/extractor.py and src/services/pico_prompt.py."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions

from src.agents.extractor import EVIDENCE_LEVELS, ExtractionAgent
from src.models.article import Article
from src.services.gemini_client import GeminiClient, TokenUsage, _extract_json
from src.services.pico_prompt import PicoExtractionResult, PicoPromptTemplate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_PAYLOAD = {
    "population": "Adults with type 2 diabetes and heart failure",
    "intervention": "SGLT2 inhibitor (empagliflozin 10 mg daily)",
    "comparison": "Placebo",
    "outcome": "Cardiovascular death or hospitalisation for heart failure",
    "study_design": "randomized_controlled_trial",
    "sample_size": 3730,
    "effect_size": "HR=0.75",
    "confidence_interval": "95% CI 0.65-0.86",
    "p_value": "p<0.001",
    "extraction_confidence": 0.95,
}


def make_article(
    pmid: str = "12345",
    title: str = "SGLT2 inhibitors in heart failure",
    abstract: str | None = "We conducted a randomised trial of empagliflozin.",
    processing_status: str = "pending",
) -> Article:
    return Article(
        id=uuid.uuid4(),
        pmid=pmid,
        title=title,
        abstract=abstract,
        authors=[],
        journal="NEJM",
        publication_date=date(2024, 3, 15),
        doi="10.1234/test",
        mesh_headings=["Heart Failure"],
        article_type="Randomized Controlled Trial",
        clinical_query_id=uuid.uuid4(),
        relevance_score=0.9,
        processing_status=processing_status,
        fetched_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )


def make_mock_llm(payload: dict | None = None, side_effect=None) -> MagicMock:
    llm = MagicMock(spec=GeminiClient)
    llm._model = "gemini-2.5-pro"
    llm.usage = TokenUsage()
    call_usage = TokenUsage(input_tokens=500, output_tokens=150)
    if side_effect is not None:
        llm.complete_json = AsyncMock(side_effect=side_effect)
    else:
        llm.complete_json = AsyncMock(return_value=(payload or _GOOD_PAYLOAD, call_usage))
    return llm


def make_mock_db(articles: list[Article] | None = None) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = articles or []
    db.execute.return_value = result
    return db


# ---------------------------------------------------------------------------
# _extract_json unit tests
# ---------------------------------------------------------------------------

def test_extract_json_plain():
    text = '{"key": "value"}'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_strips_markdown_fence():
    text = "```json\n{\"key\": \"value\"}\n```"
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_strips_bare_fence():
    text = "```\n{\"key\": \"value\"}\n```"
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_raises_on_invalid():
    with pytest.raises(ValueError, match="not valid JSON"):
        _extract_json("this is not json")


def test_extract_json_raises_on_list():
    with pytest.raises(ValueError, match="Expected a JSON object"):
        _extract_json("[1, 2, 3]")


# ---------------------------------------------------------------------------
# PicoExtractionResult validation
# ---------------------------------------------------------------------------

def test_pico_result_normalises_study_design():
    result = PicoExtractionResult.model_validate({**_GOOD_PAYLOAD, "study_design": "meta-analysis"})
    assert result.study_design == "meta_analysis"


def test_pico_result_normalises_rct_alias():
    result = PicoExtractionResult.model_validate({**_GOOD_PAYLOAD, "study_design": "randomized controlled trial"})
    assert result.study_design == "randomized_controlled_trial"


def test_pico_result_coerces_sample_size_string():
    result = PicoExtractionResult.model_validate({**_GOOD_PAYLOAD, "sample_size": "1,234"})
    assert result.sample_size == 1234


def test_pico_result_null_fields_allowed():
    result = PicoExtractionResult.model_validate({
        "population": None, "intervention": None, "comparison": None,
        "outcome": None, "study_design": None, "sample_size": None,
        "effect_size": None, "confidence_interval": None, "p_value": None,
        "extraction_confidence": 0.0,
    })
    assert result.population is None
    assert result.extraction_confidence == 0.0


# ---------------------------------------------------------------------------
# PicoPromptTemplate
# ---------------------------------------------------------------------------

def test_render_user_raises_on_missing_abstract():
    with pytest.raises(ValueError, match="no abstract"):
        PicoPromptTemplate.render_user("Some title", None)


def test_render_user_raises_on_blank_abstract():
    with pytest.raises(ValueError, match="no abstract"):
        PicoPromptTemplate.render_user("Some title", "   ")


def test_render_user_includes_title_and_abstract():
    text = PicoPromptTemplate.render_user("My Title", "The abstract text.")
    assert "My Title" in text
    assert "The abstract text." in text


def test_system_prompt_contains_pico():
    system = PicoPromptTemplate.system()
    assert "Population" in system
    assert "Intervention" in system
    assert "Comparison" in system
    assert "Outcome" in system


# ---------------------------------------------------------------------------
# EVIDENCE_LEVELS mapping
# ---------------------------------------------------------------------------

def test_evidence_levels_meta_analysis():
    assert EVIDENCE_LEVELS["meta_analysis"] == "I"
    assert EVIDENCE_LEVELS["systematic_review"] == "I"


def test_evidence_levels_rct():
    assert EVIDENCE_LEVELS["randomized_controlled_trial"] == "II"


def test_evidence_levels_cohort():
    assert EVIDENCE_LEVELS["cohort"] == "III"
    assert EVIDENCE_LEVELS["case_control"] == "III"


# ---------------------------------------------------------------------------
# ExtractionAgent.run() — success path
# ---------------------------------------------------------------------------

async def test_run_extracts_article_successfully():
    article = make_article()
    llm = make_mock_llm(_GOOD_PAYLOAD)
    db = make_mock_db([article])

    agent = ExtractionAgent(db, gemini_client=llm)
    stats = await agent.run()

    assert stats["extracted"] == 1
    assert stats["failed"] == 0
    assert stats["skipped"] == 0
    db.add.assert_called_once()
    db.commit.assert_called()
    assert article.processing_status == "extracted"


async def test_run_skips_article_without_abstract():
    article = make_article(abstract=None)
    llm = make_mock_llm()
    db = make_mock_db([article])

    agent = ExtractionAgent(db, gemini_client=llm)
    stats = await agent.run()

    assert stats["skipped"] == 1
    assert stats["extracted"] == 0
    llm.complete_json.assert_not_called()
    assert article.processing_status == "failed"


async def test_run_marks_failed_on_malformed_json():
    article = make_article()
    llm = make_mock_llm(side_effect=ValueError("not valid JSON: blah"))
    db = make_mock_db([article])

    agent = ExtractionAgent(db, gemini_client=llm)
    stats = await agent.run()

    assert stats["failed"] == 1
    assert stats["extracted"] == 0
    assert article.processing_status == "failed"


async def test_run_marks_failed_on_rate_limit():
    article = make_article()
    exc = google_exceptions.ResourceExhausted("rate limit")
    llm = make_mock_llm(side_effect=exc)
    db = make_mock_db([article])

    agent = ExtractionAgent(db, gemini_client=llm)
    stats = await agent.run()

    assert stats["failed"] == 1
    assert article.processing_status == "failed"


async def test_run_processes_multiple_articles():
    articles = [make_article(pmid=str(i)) for i in range(5)]
    llm = make_mock_llm(_GOOD_PAYLOAD)
    db = make_mock_db(articles)

    agent = ExtractionAgent(db, gemini_client=llm)
    stats = await agent.run()

    assert stats["extracted"] == 5
    assert llm.complete_json.call_count == 5


async def test_run_respects_limit():
    """When limit=2, only 2 articles are queried (tested via execute call)."""
    llm = make_mock_llm(_GOOD_PAYLOAD)
    db = make_mock_db([])  # executor returns empty; we just verify limit passed

    agent = ExtractionAgent(db, gemini_client=llm)
    await agent.run(limit=2)

    # stmt passed to execute should include a LIMIT — we can't inspect SQLAlchemy
    # objects directly, but we can verify execute was called once.
    db.execute.assert_called_once()


async def test_run_assigns_evidence_level():
    article = make_article()
    payload = {**_GOOD_PAYLOAD, "study_design": "meta_analysis"}
    llm = make_mock_llm(payload)
    db = make_mock_db([article])

    agent = ExtractionAgent(db, gemini_client=llm)
    await agent.run()

    # Check the PicoExtraction added to the db has evidence_level "I"
    added_pico = db.add.call_args[0][0]
    assert added_pico.evidence_level == "I"


async def test_run_no_evidence_level_when_no_study_design():
    article = make_article()
    payload = {**_GOOD_PAYLOAD, "study_design": None}
    llm = make_mock_llm(payload)
    db = make_mock_db([article])

    agent = ExtractionAgent(db, gemini_client=llm)
    await agent.run()

    added_pico = db.add.call_args[0][0]
    assert added_pico.evidence_level is None


async def test_run_uses_injected_llm_client():
    """When a client is injected, GeminiClient() constructor is NOT called."""
    article = make_article()
    llm = make_mock_llm(_GOOD_PAYLOAD)
    db = make_mock_db([article])

    with patch("src.agents.extractor.GeminiClient") as MockClient:
        agent = ExtractionAgent(db, gemini_client=llm)
        await agent.run()
        MockClient.assert_not_called()


async def test_run_partial_failure():
    """One article fails, others succeed — totals are correct."""
    ok_article = make_article(pmid="1")
    fail_article = make_article(pmid="2", abstract=None)  # will be skipped

    llm = make_mock_llm(_GOOD_PAYLOAD)
    db = make_mock_db([ok_article, fail_article])

    agent = ExtractionAgent(db, gemini_client=llm)
    stats = await agent.run()

    assert stats["extracted"] == 1
    assert stats["skipped"] == 1
    assert stats["failed"] == 0
