"""PICO extraction prompt template and response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Valid study designs — normalised to lowercase slugs
# ---------------------------------------------------------------------------

VALID_STUDY_DESIGNS = {
    "meta_analysis",
    "systematic_review",
    "randomized_controlled_trial",
    "rct",
    "cohort",
    "case_control",
    "cross_sectional",
    "case_report",
    "case_series",
    "other",
}

_DESIGN_ALIASES: dict[str, str] = {
    "meta-analysis": "meta_analysis",
    "meta analysis": "meta_analysis",
    "systematic review": "systematic_review",
    "randomized controlled trial": "randomized_controlled_trial",
    "randomised controlled trial": "randomized_controlled_trial",
    "rct": "randomized_controlled_trial",
    "cohort study": "cohort",
    "case-control": "case_control",
    "case control": "case_control",
    "cross-sectional": "cross_sectional",
    "cross sectional": "cross_sectional",
    "case report": "case_report",
    "case series": "case_series",
}


# ---------------------------------------------------------------------------
# Pydantic response model
# ---------------------------------------------------------------------------


class PicoExtractionResult(BaseModel):
    population: str | None = Field(None, description="Patient/participant population")
    intervention: str | None = Field(None, description="Intervention or exposure")
    comparison: str | None = Field(None, description="Comparator or control group")
    outcome: str | None = Field(None, description="Primary outcome(s) measured")
    study_design: str | None = Field(None, description="Study design type")
    sample_size: int | None = Field(None, description="Total number of participants")
    effect_size: str | None = Field(None, description="Effect size (e.g. OR=0.72, HR=0.68)")
    confidence_interval: str | None = Field(None, description="Confidence interval (e.g. 95% CI 0.55-0.90)")
    p_value: str | None = Field(None, description="P-value (e.g. p<0.001)")
    extraction_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Model's confidence in the extraction [0,1]"
    )

    @field_validator("study_design", mode="before")
    @classmethod
    def normalise_study_design(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalised = v.strip().lower()
        return _DESIGN_ALIASES.get(normalised, normalised.replace(" ", "_").replace("-", "_"))

    @field_validator("sample_size", mode="before")
    @classmethod
    def coerce_sample_size(cls, v) -> int | None:
        if v is None:
            return None
        if isinstance(v, str):
            # Strip commas (e.g. "1,234")
            cleaned = v.replace(",", "").strip()
            try:
                return int(cleaned)
            except ValueError:
                return None
        return int(v)


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a medical literature expert specialised in evidence-based medicine. \
Your task is to extract structured PICO (Population, Intervention, Comparison, Outcome) \
information from clinical research article abstracts.

Extract the following fields and return ONLY a valid JSON object — no markdown, no prose:

{
  "population": "<description of study population or null>",
  "intervention": "<intervention or exposure or null>",
  "comparison": "<comparator/control or null>",
  "outcome": "<primary outcome(s) or null>",
  "study_design": "<one of: meta_analysis, systematic_review, randomized_controlled_trial, cohort, case_control, cross_sectional, case_report, case_series, other — or null>",
  "sample_size": <integer total participants or null>,
  "effect_size": "<e.g. OR=0.72, HR=0.68, RR=0.85 — or null>",
  "confidence_interval": "<e.g. 95% CI 0.55–0.90 — or null>",
  "p_value": "<e.g. p<0.001 — or null>",
  "extraction_confidence": <float 0.0–1.0 reflecting your confidence in the extraction>
}

Rules:
- Use null (not empty string) for fields you cannot determine from the text.
- Return ONLY the JSON object — no explanation, no markdown fences.
- If the article is not in English or has no usable abstract, set all clinical fields \
to null and set extraction_confidence to 0.0.
"""


class PicoPromptTemplate:
    """Builds system/user prompts and parses + validates the LLM response."""

    @staticmethod
    def system() -> str:
        return _SYSTEM_PROMPT

    @staticmethod
    def render_user(title: str, abstract: str | None) -> str:
        """Render the user turn.

        Raises:
            ValueError: if *abstract* is None or blank (caller should mark
                the article as failed rather than sending an empty prompt).
        """
        if not abstract or not abstract.strip():
            raise ValueError("Article has no abstract — cannot extract PICO")
        return f"Title: {title}\n\nAbstract:\n{abstract}"

    @staticmethod
    def parse_response(payload: dict) -> PicoExtractionResult:
        """Validate and coerce the raw LLM JSON payload.

        Raises:
            pydantic.ValidationError: on schema violations.
        """
        return PicoExtractionResult.model_validate(payload)
