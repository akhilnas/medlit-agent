"""Tests for src/services/synthesis_prompt.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.services.synthesis_prompt import (
    SynthesisResult,
    SynthesisPromptTemplate,
    VALID_EVIDENCE_GRADES,
    VALID_CONSENSUS_STATUSES,
)


# ---------------------------------------------------------------------------
# SynthesisResult model
# ---------------------------------------------------------------------------

def test_synthesis_result_valid():
    result = SynthesisResult(
        summary_text="SGLT2i reduce hospitalizations in HF patients.",
        evidence_grade="A",
        consensus_status="consistent",
        key_findings=["Reduced HHF by 25%", "CV death reduced"],
        evidence_gaps=["Long-term data lacking"],
        article_count=5,
    )
    assert result.summary_text.startswith("SGLT2i")
    assert result.evidence_grade == "A"
    assert result.consensus_status == "consistent"
    assert len(result.key_findings) == 2
    assert result.article_count == 5


def test_synthesis_result_optional_fields_default():
    result = SynthesisResult(
        summary_text="Some summary.",
        article_count=3,
    )
    assert result.evidence_grade is None
    assert result.consensus_status is None
    assert result.key_findings == []
    assert result.evidence_gaps == []


def test_synthesis_result_requires_summary_text():
    with pytest.raises(ValidationError):
        SynthesisResult(article_count=3)


def test_synthesis_result_requires_article_count():
    with pytest.raises(ValidationError):
        SynthesisResult(summary_text="hello")


def test_synthesis_result_evidence_grade_normalised_uppercase():
    result = SynthesisResult(summary_text="s", article_count=1, evidence_grade="b")
    assert result.evidence_grade == "B"


def test_synthesis_result_invalid_evidence_grade_rejected():
    with pytest.raises(ValidationError):
        SynthesisResult(summary_text="s", article_count=1, evidence_grade="Z")


def test_synthesis_result_invalid_consensus_status_rejected():
    with pytest.raises(ValidationError):
        SynthesisResult(summary_text="s", article_count=1, consensus_status="maybe")


def test_synthesis_result_valid_consensus_statuses():
    for status in VALID_CONSENSUS_STATUSES:
        r = SynthesisResult(summary_text="s", article_count=1, consensus_status=status)
        assert r.consensus_status == status


def test_synthesis_result_valid_evidence_grades():
    for grade in VALID_EVIDENCE_GRADES:
        r = SynthesisResult(summary_text="s", article_count=1, evidence_grade=grade)
        assert r.evidence_grade == grade


# ---------------------------------------------------------------------------
# SynthesisPromptTemplate
# ---------------------------------------------------------------------------

def _make_articles(n: int = 3) -> list[dict]:
    return [
        {
            "title": f"Study {i}",
            "abstract": f"Abstract {i}",
            "intervention": "Empagliflozin",
            "population": "Adults with HF",
            "outcome": "CV death",
            "study_design": "randomized_controlled_trial",
            "effect_size": "HR=0.75",
            "confidence_interval": "95% CI 0.60-0.90",
            "p_value": "p<0.001",
        }
        for i in range(n)
    ]


def test_system_prompt_returns_string():
    assert isinstance(SynthesisPromptTemplate.system(), str)
    assert len(SynthesisPromptTemplate.system()) > 50


def test_render_user_includes_query():
    articles = _make_articles(2)
    prompt = SynthesisPromptTemplate.render_user(
        clinical_query="SGLT2 inhibitors AND heart failure", articles=articles
    )
    assert "SGLT2 inhibitors AND heart failure" in prompt
    assert "Study 0" in prompt
    assert "Study 1" in prompt


def test_render_user_raises_on_empty_articles():
    with pytest.raises(ValueError, match="at least one article"):
        SynthesisPromptTemplate.render_user(
            clinical_query="SGLT2", articles=[]
        )


def test_parse_response_valid():
    payload = {
        "summary_text": "SGLT2i are effective.",
        "evidence_grade": "A",
        "consensus_status": "consistent",
        "key_findings": ["Reduced mortality"],
        "evidence_gaps": [],
        "article_count": 3,
    }
    result = SynthesisPromptTemplate.parse_response(payload)
    assert isinstance(result, SynthesisResult)
    assert result.evidence_grade == "A"


def test_parse_response_raises_on_invalid():
    with pytest.raises((ValueError, Exception)):
        SynthesisPromptTemplate.parse_response({"article_count": 2})  # missing summary_text


def test_render_user_lists_article_count():
    articles = _make_articles(4)
    prompt = SynthesisPromptTemplate.render_user(
        clinical_query="some query", articles=articles
    )
    assert "4" in prompt
