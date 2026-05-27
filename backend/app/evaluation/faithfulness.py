"""Citation faithfulness — does the summary cite only real chunks?

Per the proposal: zero hallucinations on cited figures. We measure this
by extracting every `[chunk_id]` from the LLM-produced summary and
checking it exists in the ingestion-produced allow-list. A perfect
faithfulness score is 1.0 (every citation valid); anything less is a
hallucination event that needs human review.

The companion check is *coverage*: how many of the claims actually
carry a citation. A summary with one citation and ten un-cited claims
is still bad for FEATERS even if the citation is valid.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.explainability.summary import RiskSummary, extract_citations


class FaithfulnessReport(BaseModel):
    citations_total: int
    citations_valid: int
    invalid_citations: list[str] = Field(default_factory=list)
    faithfulness: float = Field(description="valid / total — 1.0 means no hallucinations")
    uncited_sentence_count: int = Field(
        description="Sentences in body that contain no citation; lower is better"
    )
    sentence_citation_coverage: float = Field(
        description="Fraction of body sentences that contain at least one citation"
    )


def _split_sentences(text: str) -> list[str]:
    # Cheap sentence-ish splitter — full NLTK is overkill for what we measure.
    out: list[str] = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in ".!?":
            sentence = "".join(buf).strip()
            if sentence:
                out.append(sentence)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def score_faithfulness(
    summary: RiskSummary, allowed_chunk_ids: list[str]
) -> FaithfulnessReport:
    citations = extract_citations(summary.headline) + extract_citations(summary.body)
    allow = set(allowed_chunk_ids)
    valid = [c for c in citations if c in allow]
    invalid = sorted({c for c in citations if c not in allow})

    sentences = _split_sentences(summary.body)
    cited_sentences = sum(1 for s in sentences if extract_citations(s))
    coverage = cited_sentences / len(sentences) if sentences else 1.0

    return FaithfulnessReport(
        citations_total=len(citations),
        citations_valid=len(valid),
        invalid_citations=invalid,
        faithfulness=(len(valid) / len(citations)) if citations else 1.0,
        uncited_sentence_count=len(sentences) - cited_sentences,
        sentence_citation_coverage=coverage,
    )
