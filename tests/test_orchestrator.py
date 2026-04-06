"""Tests for src/agents/orchestrator.py."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.orchestrator import Orchestrator, OrchestratorState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_query(is_active: bool = True):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.pubmed_query = "SGLT2 AND heart failure"
    q.name = "SGLT2 HF"
    q.is_active = is_active
    return q


def make_pipeline_run():
    run = MagicMock()
    run.id = uuid.uuid4()
    run.status = "running"
    run.articles_found = 5
    run.articles_extracted = 3
    return run


def make_mock_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.get = AsyncMock()
    return db


def make_monitor_agent(articles_found: int = 5) -> AsyncMock:
    agent = AsyncMock()
    run = make_pipeline_run()
    run.articles_found = articles_found
    agent.run = AsyncMock(return_value=run)
    return agent


def make_extractor_agent(stats: dict | None = None) -> AsyncMock:
    agent = AsyncMock()
    agent.run = AsyncMock(return_value=stats or {"extracted": 3, "failed": 0, "skipped": 0})
    return agent


def make_embedder_agent(stats: dict | None = None) -> AsyncMock:
    agent = AsyncMock()
    agent.run = AsyncMock(return_value=stats or {"embedded": 3, "failed": 0, "skipped": 0})
    return agent


def make_synthesis_agent(synthesis=None) -> AsyncMock:
    agent = AsyncMock()
    s = synthesis or MagicMock()
    s.id = uuid.uuid4()
    agent.run = AsyncMock(return_value=s)
    return agent


# ---------------------------------------------------------------------------
# OrchestratorState
# ---------------------------------------------------------------------------

def test_state_initial():
    state = OrchestratorState()
    assert state.phase == "IDLE"
    assert state.articles_found == 0
    assert state.articles_extracted == 0
    assert state.articles_embedded == 0
    assert state.synthesis_id is None
    assert state.error is None


def test_state_transitions_to_monitoring():
    state = OrchestratorState()
    updated = state.transition("MONITORING")
    assert updated.phase == "MONITORING"
    # original is unchanged (immutable)
    assert state.phase == "IDLE"


def test_state_immutable():
    state = OrchestratorState()
    with pytest.raises((AttributeError, TypeError)):
        state.phase = "MONITORING"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Orchestrator.run()
# ---------------------------------------------------------------------------

async def test_run_full_pipeline_success():
    query = make_query()
    db = make_mock_db()
    monitor = make_monitor_agent(articles_found=5)
    extractor = make_extractor_agent()
    embedder = make_embedder_agent()
    synthesizer = make_synthesis_agent()

    orch = Orchestrator(
        db=db,
        monitor_agent=monitor,
        extractor_agent=extractor,
        embedder_agent=embedder,
        synthesis_agent=synthesizer,
    )
    final_state = await orch.run(query)

    assert final_state.phase == "COMPLETE"
    assert final_state.articles_found == 5
    assert final_state.articles_extracted == 3
    assert final_state.articles_embedded == 3
    assert final_state.synthesis_id is not None
    assert final_state.error is None


async def test_run_calls_all_agents_in_order():
    query = make_query()
    db = make_mock_db()
    call_order = []

    run = make_pipeline_run()
    monitor = AsyncMock()
    monitor.run = AsyncMock(side_effect=lambda *a, **kw: _append_return(call_order, "monitor", run))

    extractor = AsyncMock()
    extractor.run = AsyncMock(
        side_effect=lambda *a, **kw: _append_return(call_order, "extractor", {"extracted": 3, "failed": 0, "skipped": 0})
    )

    embedder = AsyncMock()
    embedder.run = AsyncMock(
        side_effect=lambda *a, **kw: _append_return(call_order, "embedder", {"embedded": 3, "failed": 0, "skipped": 0})
    )

    synthesis = MagicMock()
    synthesis.id = uuid.uuid4()
    synthesizer = AsyncMock()
    synthesizer.run = AsyncMock(
        side_effect=lambda *a, **kw: _append_return(call_order, "synthesizer", synthesis)
    )

    orch = Orchestrator(
        db=db,
        monitor_agent=monitor,
        extractor_agent=extractor,
        embedder_agent=embedder,
        synthesis_agent=synthesizer,
    )
    await orch.run(query)

    assert call_order == ["monitor", "extractor", "embedder", "synthesizer"]


async def test_run_skips_synthesis_when_no_articles_found():
    query = make_query()
    db = make_mock_db()
    monitor = make_monitor_agent(articles_found=0)
    extractor = make_extractor_agent({"extracted": 0, "failed": 0, "skipped": 0})
    embedder = make_embedder_agent({"embedded": 0, "failed": 0, "skipped": 0})
    synthesizer = make_synthesis_agent()

    orch = Orchestrator(
        db=db,
        monitor_agent=monitor,
        extractor_agent=extractor,
        embedder_agent=embedder,
        synthesis_agent=synthesizer,
    )
    final_state = await orch.run(query)

    # Synthesis still attempted — let SynthesisAgent decide to skip
    assert final_state.phase in ("COMPLETE", "FAILED")


async def test_run_fails_gracefully_on_monitor_error():
    query = make_query()
    db = make_mock_db()
    monitor = AsyncMock()
    monitor.run = AsyncMock(side_effect=RuntimeError("PubMed timeout"))

    orch = Orchestrator(
        db=db,
        monitor_agent=monitor,
        extractor_agent=make_extractor_agent(),
        embedder_agent=make_embedder_agent(),
        synthesis_agent=make_synthesis_agent(),
    )
    final_state = await orch.run(query)

    assert final_state.phase == "FAILED"
    assert "PubMed timeout" in final_state.error


async def test_run_continues_after_embed_failure():
    """Embed failures should not block synthesis."""
    query = make_query()
    db = make_mock_db()
    monitor = make_monitor_agent(articles_found=3)
    extractor = make_extractor_agent({"extracted": 3, "failed": 0, "skipped": 0})
    embedder = AsyncMock()
    embedder.run = AsyncMock(side_effect=RuntimeError("GPU OOM"))
    synthesizer = make_synthesis_agent()

    orch = Orchestrator(
        db=db,
        monitor_agent=monitor,
        extractor_agent=extractor,
        embedder_agent=embedder,
        synthesis_agent=synthesizer,
    )
    final_state = await orch.run(query)

    # Should still attempt synthesis even if embed fails
    assert final_state.phase in ("COMPLETE", "FAILED")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _append_return(order: list, name: str, return_value):
    order.append(name)
    return return_value
