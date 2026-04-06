"""Async Google Gemini API client with retry/backoff, JSON parsing, and token tracking."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

from google import genai
from google.genai import errors as google_errors
from google.genai import types as genai_types

from src.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash"
_MAX_RETRIES = 4
_BASE_DELAY = 1.0  # seconds


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens


class GeminiClient:
    """Thin async wrapper around the Google Gemini SDK.

    Features:
    - Exponential-backoff retry on ResourceExhausted and 5xx server errors
    - ``complete_json()`` strips markdown fences and parses JSON
    - Per-call and session-level token usage tracking via :attr:`usage`
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_MODEL,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        resolved_key = api_key or settings.gemini_api_key
        self._client = genai.Client(api_key=resolved_key)
        self._model = model
        self._max_retries = max_retries
        self.usage = TokenUsage()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> tuple[str, TokenUsage]:
        """Send a single-turn message and return ``(text, call_usage)``.

        Retries up to *max_retries* times with exponential backoff on rate
        limit or transient server errors.
        """
        call_usage = TokenUsage()
        delay = _BASE_DELAY

        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=config,
                )
                call_usage = TokenUsage(
                    input_tokens=response.usage_metadata.prompt_token_count or 0,
                    output_tokens=response.usage_metadata.candidates_token_count or 0,
                )
                self.usage.add(call_usage)
                # Track token usage in Prometheus
                from src.core.metrics import llm_tokens_used_total
                llm_tokens_used_total.labels(model=self._model, direction="input").inc(call_usage.input_tokens)
                llm_tokens_used_total.labels(model=self._model, direction="output").inc(call_usage.output_tokens)
                text = response.text
                logger.debug(
                    "Gemini call succeeded | model=%s in=%d out=%d",
                    self._model,
                    call_usage.input_tokens,
                    call_usage.output_tokens,
                )
                return text, call_usage

            except google_errors.ClientError as exc:
                # 429 = rate limited
                if getattr(exc, "status_code", None) != 429:
                    raise
                if attempt == self._max_retries:
                    logger.error("Gemini rate limit — giving up after %d retries", attempt)
                    raise
                logger.warning(
                    "Gemini rate limit (attempt %d/%d) — sleeping %.1fs",
                    attempt + 1,
                    self._max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= 2

            except google_errors.ServerError:
                if attempt == self._max_retries:
                    raise
                logger.warning(
                    "Gemini server error (attempt %d/%d) — sleeping %.1fs",
                    attempt + 1,
                    self._max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= 2

        # Unreachable — loop always raises or returns
        raise RuntimeError("Exceeded max retries")  # pragma: no cover

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> tuple[dict, TokenUsage]:
        """Like :meth:`complete` but parses the response as JSON.

        Strips optional markdown code fences (`` ```json ... ``` ``) before
        parsing.  Raises :class:`ValueError` if the text is not valid JSON.
        """
        text, call_usage = await self.complete(
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        payload = _extract_json(text)
        return payload, call_usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON from *text*."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        result = json.loads(cleaned)
        if not isinstance(result, dict):
            raise ValueError(f"Expected a JSON object, got {type(result).__name__}")
        return result
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response is not valid JSON: {exc}\n---\n{text}") from exc
