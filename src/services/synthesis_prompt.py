"""Evidence synthesis prompt templates and response models."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Valid values
# ---------------------------------------------------------------------------

VALID_EVIDENCE_GRADES: set[str] = {"A", "B", "C", "D", "I", "II", "III"}
VALID_CONSENSUS_STATUSES: set[str] = {"consistent", "inconsistent", "insufficient"}


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class SynthesisResult(BaseModel):
    summary_text: str = Field(..., description="Narrative synthesis of the evidence")
    evidence_grade: str | None = Field(
        None, description="Overall evidence grade (A/B/C/D or I/II/III)"
    )
    consensus_status: str | None = Field(
        None, description="Degree of consensus across studies"
    )
    key_findings: list[str] = Field(
        default_factory=list, description="Bullet-point key findings"
    )
    evidence_gaps: list[str] = Field(
        default_factory=list, description="Identified evidence gaps"
    )
    article_count: int = Field(..., ge=0, description="Number of articles synthesised")

    @field_validator("evidence_grade", mode="before")
    @classmethod
    def normalise_grade(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalised = v.strip().upper()
        if normalised not in VALID_EVIDENCE_GRADES:
            raise ValueError(
                f"evidence_grade must be one of {VALID_EVIDENCE_GRADES}, got '{v}'"
            )
        return normalised

    @field_validator("consensus_status", mode="before")
    @classmethod
    def validate_consensus(cls, v: str | None) -> str | None:
        if v is None:
            return None
        lower = v.strip().lower()
        if lower not in VALID_CONSENSUS_STATUSES:
            raise ValueError(
                f"consensus_status must be one of {VALID_CONSENSUS_STATUSES}, got '{v}'"
            )
        return lower


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a senior medical evidence synthesiser with expertise in systematic review \
and evidence-based medicine. Your task is to synthesise findings from multiple \
clinical research articles into a concise, structured evidence summary.

Return ONLY a valid JSON object with the following fields:

{
  "summary_text": "<2-4 sentence narrative summary of the overall evidence>",
  "evidence_grade": "<one of: A, B, C, D, I, II, III — or null if unclear>",
  "consensus_status": "<one of: consistent, inconsistent, insufficient>",
  "key_findings": ["<finding 1>", "<finding 2>", ...],
  "evidence_gaps": ["<gap 1>", "<gap 2>", ...],
  "article_count": <integer — number of articles you reviewed>
}

Evidence grade scale:
  A = Consistent, high-quality RCT or meta-analysis evidence
  B = Consistent, lower-quality RCT or high-quality observational evidence
  C = Inconsistent or limited evidence
  D = Very limited evidence, expert opinion only
  I/II/III = Insufficient evidence to recommend

Consensus status:
  consistent = Studies agree on direction and magnitude of effect
  inconsistent = Studies disagree on direction or magnitude
  insufficient = Too few or too heterogeneous to assess consensus

Rules:
- Return ONLY the JSON object — no markdown fences, no prose before or after.
- key_findings and evidence_gaps must be non-empty arrays of strings.
- article_count must match the number of articles provided.
"""


def _format_article(idx: int, article: dict) -> str:
    parts = [f"[{idx + 1}] {article.get('title', 'Untitled')}"]
    if article.get("abstract"):
        parts.append(f"Abstract: {article['abstract'][:600]}")
    for field in ("intervention", "population", "outcome", "study_design",
                  "effect_size", "confidence_interval", "p_value"):
        val = article.get(field)
        if val:
            parts.append(f"{field.replace('_', ' ').title()}: {val}")
    return "\n".join(parts)


class SynthesisPromptTemplate:
    """Builds prompts for evidence synthesis and parses the LLM response."""

    @staticmethod
    def system() -> str:
        return _SYSTEM_PROMPT

    @staticmethod
    def render_user(*, clinical_query: str, articles: list[dict]) -> str:
        """Render the user turn for evidence synthesis.

        Args:
            clinical_query: The original PubMed query string.
            articles: List of article dicts with keys like title, abstract,
                      intervention, population, outcome, study_design, etc.

        Raises:
            ValueError: If articles list is empty.
        """
        if not articles:
            raise ValueError("Synthesis requires at least one article")

        header = (
            f"Clinical Query: {clinical_query}\n"
            f"Number of articles: {len(articles)}\n\n"
            "Articles to synthesise:\n"
            + "=" * 60 + "\n"
        )
        body = ("\n" + "-" * 40 + "\n").join(
            _format_article(i, a) for i, a in enumerate(articles)
        )
        footer = (
            "\n" + "=" * 60 + "\n"
            "Synthesise the evidence from these articles and return ONLY the JSON object."
        )
        return header + body + footer

    @staticmethod
    def parse_response(payload: dict) -> SynthesisResult:
        """Validate and coerce the raw LLM JSON payload.

        Raises:
            pydantic.ValidationError: on schema violations.
        """
        return SynthesisResult.model_validate(payload)
