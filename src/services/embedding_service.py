"""PubMedBERT embedding service for semantic article search.

Wraps sentence-transformers with:
- Lazy model loading (loaded once on first use)
- GPU auto-detection with CPU fallback
- Async batch encoding via thread executor (never blocks the event loop)
- Pure helper functions for building article text inputs
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.core.config import settings

if TYPE_CHECKING:
    from src.models.article import Article
    from src.models.pico_extraction import PicoExtraction

logger = logging.getLogger(__name__)

_EMBEDDING_DIM = 768


@dataclass(frozen=True)
class EmbeddingInput:
    """A single text+type pair ready for encoding."""
    embedding_type: str   # "abstract" or "pico"
    text: str


class EmbeddingService:
    """Generates PubMedBERT embeddings for article text.

    Usage::

        svc = EmbeddingService()
        vectors = await svc.embed_texts(["SGLT2 in heart failure", ...])
        # vectors[i] is a list[float] of length 768
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.embedding_model_name
        self._model = None   # lazy — loaded on first encode call
        self._device: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode *texts* and return a list of 768-dim float vectors.

        Runs the synchronous sentence-transformers encode() in a thread
        executor so the asyncio event loop is never blocked.
        """
        if not texts:
            return []
        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(None, self._encode_sync, texts)
        return vectors

    def build_inputs(
        self,
        article: "Article",
        pico: "PicoExtraction | None",
    ) -> list[EmbeddingInput]:
        """Return the embedding inputs for *article*.

        Always produces the ``abstract`` input.  Produces the ``pico``
        input only when at least one PICO field is non-empty.
        """
        inputs: list[EmbeddingInput] = []

        abstract_text = _build_abstract_text(article.title, article.abstract)
        inputs.append(EmbeddingInput(embedding_type="abstract", text=abstract_text))

        if pico is not None:
            pico_text = _build_pico_text(pico)
            if pico_text:
                inputs.append(EmbeddingInput(embedding_type="pico", text=pico_text))

        return inputs

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Load PubMedBERT once; detect GPU/CPU device."""
        if self._model is not None:
            return

        import torch
        from sentence_transformers import SentenceTransformer

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(
            "Loading embedding model %s on %s", self._model_name, self._device
        )
        self._model = SentenceTransformer(self._model_name, device=self._device)
        logger.info("Embedding model loaded (dim=%d)", _EMBEDDING_DIM)

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous encode — called from a thread executor."""
        import time

        from src.core.metrics import embedding_generation_seconds

        self._load_model()
        start = time.perf_counter()
        vectors = self._model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        embedding_generation_seconds.observe(time.perf_counter() - start)
        return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Pure text-building helpers
# ---------------------------------------------------------------------------

def _build_abstract_text(title: str, abstract: str | None) -> str:
    """Combine title and abstract into a single string for embedding."""
    if abstract and abstract.strip():
        return f"{title}. {abstract}"
    return title


def _build_pico_text(pico: "PicoExtraction") -> str | None:
    """Concatenate non-empty PICO fields.  Returns None if all are empty."""
    parts = [
        pico.population,
        pico.intervention,
        pico.comparison,
        pico.outcome,
    ]
    text = " ".join(p for p in parts if p)
    return text if text.strip() else None
