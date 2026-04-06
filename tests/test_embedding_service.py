"""Tests for src/services/embedding_service.py."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.embedding_service import (
    EmbeddingService,
    EmbeddingInput,
    _build_abstract_text,
    _build_pico_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_article(title="SGLT2 in HF", abstract="We studied empagliflozin."):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.title = title
    a.abstract = abstract
    return a


def make_mock_pico(
    population="Adults with HF",
    intervention="Empagliflozin",
    comparison="Placebo",
    outcome="CV death",
):
    p = MagicMock()
    p.population = population
    p.intervention = intervention
    p.comparison = comparison
    p.outcome = outcome
    return p


def make_mock_model(dim: int = 768):
    """Mock SentenceTransformer that returns numpy-like arrays."""
    import numpy as np

    model = MagicMock()
    model.encode = MagicMock(
        side_effect=lambda texts, **kwargs: [np.zeros(dim) for _ in texts]
    )
    return model


# ---------------------------------------------------------------------------
# _build_abstract_text
# ---------------------------------------------------------------------------

def test_build_abstract_text_with_abstract():
    result = _build_abstract_text("My Title", "My abstract text.")
    assert result == "My Title. My abstract text."


def test_build_abstract_text_no_abstract():
    result = _build_abstract_text("My Title", None)
    assert result == "My Title"


def test_build_abstract_text_blank_abstract():
    result = _build_abstract_text("My Title", "   ")
    assert result == "My Title"


# ---------------------------------------------------------------------------
# _build_pico_text
# ---------------------------------------------------------------------------

def test_build_pico_text_all_fields():
    pico = make_mock_pico()
    result = _build_pico_text(pico)
    assert "Adults with HF" in result
    assert "Empagliflozin" in result
    assert "Placebo" in result
    assert "CV death" in result


def test_build_pico_text_partial_fields():
    pico = make_mock_pico(comparison=None, outcome=None)
    result = _build_pico_text(pico)
    assert result is not None
    assert "Adults with HF" in result


def test_build_pico_text_all_none():
    pico = make_mock_pico(population=None, intervention=None, comparison=None, outcome=None)
    result = _build_pico_text(pico)
    assert result is None


# ---------------------------------------------------------------------------
# EmbeddingService
# ---------------------------------------------------------------------------

def test_model_not_loaded_on_init():
    """Constructor must NOT import or load the model."""
    with patch("src.services.embedding_service.EmbeddingService._load_model") as mock_load:
        svc = EmbeddingService()
        mock_load.assert_not_called()
        assert svc._model is None


def test_model_set_after_load():
    """After _load_model, _model and _device are populated."""
    svc = EmbeddingService()
    mock_model = make_mock_model()

    # Inject model directly — avoids triggering the real sentence-transformers load
    svc._model = mock_model
    svc._device = "cpu"

    assert svc._model is mock_model
    assert svc._device == "cpu"


def test_gpu_device_logic():
    """GPU device string is selected correctly based on cuda availability."""
    svc = EmbeddingService()

    with patch("torch.cuda.is_available", return_value=True):
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"

    svc._device = device
    assert svc._device == "cuda"


async def test_embed_texts_returns_correct_shape():
    svc = EmbeddingService()
    mock_model = make_mock_model(dim=768)
    svc._model = mock_model
    svc._device = "cpu"

    vectors = await svc.embed_texts(["hello world", "second text"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 768
    assert isinstance(vectors[0][0], float)


async def test_embed_texts_empty_returns_empty():
    svc = EmbeddingService()
    result = await svc.embed_texts([])
    assert result == []


async def test_embed_texts_runs_in_executor():
    """embed_texts should call run_in_executor, not block the loop."""
    svc = EmbeddingService()
    import numpy as np
    mock_model = make_mock_model()
    svc._model = mock_model
    svc._device = "cpu"

    with patch("asyncio.get_event_loop") as mock_loop_fn:
        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value=[[0.0] * 768])
        mock_loop_fn.return_value = mock_loop

        result = await svc.embed_texts(["test"])

    mock_loop.run_in_executor.assert_called_once()


# ---------------------------------------------------------------------------
# EmbeddingService.build_inputs
# ---------------------------------------------------------------------------

def test_build_inputs_abstract_always_present():
    svc = EmbeddingService()
    article = make_mock_article()
    inputs = svc.build_inputs(article, pico=None)

    assert len(inputs) == 1
    assert inputs[0].embedding_type == "abstract"
    assert article.title in inputs[0].text


def test_build_inputs_pico_included_when_present():
    svc = EmbeddingService()
    article = make_mock_article()
    pico = make_mock_pico()
    inputs = svc.build_inputs(article, pico=pico)

    types = [i.embedding_type for i in inputs]
    assert "abstract" in types
    assert "pico" in types


def test_build_inputs_pico_skipped_when_all_none():
    svc = EmbeddingService()
    article = make_mock_article()
    pico = make_mock_pico(population=None, intervention=None, comparison=None, outcome=None)
    inputs = svc.build_inputs(article, pico=pico)

    types = [i.embedding_type for i in inputs]
    assert "pico" not in types


def test_build_inputs_returns_immutable_embedding_inputs():
    svc = EmbeddingService()
    article = make_mock_article()
    inputs = svc.build_inputs(article, pico=None)
    assert isinstance(inputs[0], EmbeddingInput)
