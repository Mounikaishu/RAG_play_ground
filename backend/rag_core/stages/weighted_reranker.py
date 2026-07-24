"""
weighted_reranker.py — Multi-Signal Weighted Reranker

Position in the pipeline:
    Retrieve → RRF (rerank_chunks) → WeightedReranker → Context Refinement

Why this exists:
    RRF combines embedding distance + keyword overlap but weights them
    equally and ignores richer signals like metadata completeness,
    section importance, and chunk length quality.

    This module applies a configurable weighted scoring formula:

        final_score =
            0.45 * semantic_score      — cosine similarity (embedding space)
          + 0.20 * metadata_score      — metadata completeness / richness
          + 0.15 * section_score       — importance of the source section
          + 0.10 * completeness_score  — text length & density signal
          + 0.10 * retrieval_score     — normalised RRF / distance signal

Design principles (SOLID):
    S — Single Responsibility: each score_* function does exactly one thing.
    O — Open/Closed: add a new signal by adding a new function + a weight key.
    L — No inheritance needed; functions are the extension point.
    I — One public entry point: `weighted_rerank()`.
    D — Dependencies (embeddings model) are injected via the existing singleton;
        no hard coupling to the rest of the pipeline.

Safety guarantees:
    • chunk["text"] and chunk["metadata"] are NEVER mutated.
    • A new "final_score" key is added to a shallow copy.
    • Any exception → original list returned unchanged (pipeline never breaks).
    • Empty chunks → empty list returned immediately.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configurable Weights
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RerankerWeights:
    """
    Weights for the weighted scoring formula.

    All weights must sum to 1.0.  Defaults mirror the project specification:
        semantic=0.45, metadata=0.20, section=0.15,
        completeness=0.10, retrieval=0.10
    """
    semantic: float = 0.45
    metadata: float = 0.20
    section: float = 0.15
    completeness: float = 0.10
    retrieval: float = 0.10

    def validate(self) -> None:
        """Raise ValueError if weights do not sum to ~1.0."""
        total = self.semantic + self.metadata + self.section + self.completeness + self.retrieval
        if not math.isclose(total, 1.0, abs_tol=1e-3):
            raise ValueError(
                f"RerankerWeights must sum to 1.0, got {total:.4f}. "
                f"Adjust weights: {self!r}"
            )


_DEFAULT_WEIGHTS = RerankerWeights()

# ──────────────────────────────────────────────────────────────────────────────
# Section importance mapping
# ──────────────────────────────────────────────────────────────────────────────

_SECTION_SCORES: dict[str, float] = {
    "experience":          1.0,
    "work experience":     1.0,
    "professional experience": 1.0,
    "projects":            0.9,
    "skills":              0.85,
    "technical skills":    0.85,
    "education":           0.70,
    "summary":             0.65,
    "profile":             0.65,
    "certifications":      0.60,
    "achievements":        0.60,
    "interview experience": 0.80,
    "rounds":              0.75,
    "tips":                0.65,
}

# ──────────────────────────────────────────────────────────────────────────────
# Individual Scoring Components
# ──────────────────────────────────────────────────────────────────────────────

def semantic_score(query: str, chunk_text: str) -> float:
    """
    Compute cosine similarity between the query embedding and the chunk
    text embedding using the project's existing embedding model.

    Returns:
        float in [0.0, 1.0], where 1.0 = identical vectors.

    Falls back to 0.0 on any exception so the pipeline never breaks.
    """
    if not query or not chunk_text:
        return 0.0
    try:
        from rag_core.db.chromadb_store import embed_query, embed_texts

        q_vec: list[float] = embed_query(query)
        c_vec: list[float] = embed_texts([chunk_text])[0]

        # Cosine similarity
        dot = sum(a * b for a, b in zip(q_vec, c_vec))
        norm_q = math.sqrt(sum(a * a for a in q_vec))
        norm_c = math.sqrt(sum(b * b for b in c_vec))

        if norm_q == 0.0 or norm_c == 0.0:
            return 0.0

        sim = dot / (norm_q * norm_c)
        # Clamp to [0, 1] — cosine can be slightly outside due to float precision
        return max(0.0, min(1.0, (sim + 1.0) / 2.0))
    except Exception as exc:
        logger.debug("semantic_score failed (%s); returning 0.0", exc)
        return 0.0


def metadata_score(metadata: dict) -> float:
    """
    Score how complete and rich the chunk's metadata is.

    Checks for the presence of:
        source_file (0.30), document_id (0.25),
        collection   (0.25), section    (0.20)

    Returns:
        float in [0.0, 1.0].
    """
    if not metadata:
        return 0.0

    score = 0.0

    # source_file — identifies the origin document
    if metadata.get("source_file") or metadata.get("filename"):
        score += 0.30

    # document_id — unique document identifier
    if (
        metadata.get("document_id")
        or metadata.get("roll_no")
        or metadata.get("student_name")
    ):
        score += 0.25

    # collection — know which knowledge domain this chunk came from
    if metadata.get("collection") or metadata.get("category"):
        score += 0.25

    # section — structural metadata for context quality
    if metadata.get("section") or metadata.get("section_title"):
        score += 0.20

    return round(min(1.0, score), 4)


def section_score(metadata: dict) -> float:
    """
    Score the chunk based on which section of the document it came from.

    High-value sections (experience, projects, skills) get higher scores
    than lower-signal sections (education, certifications).

    Returns:
        float in [0.0, 1.0]; 0.5 if section is unknown; 0.0 if no metadata.
    """
    if not metadata:
        return 0.0

    raw_section: str = (
        metadata.get("section")
        or metadata.get("section_title")
        or metadata.get("document_type")
        or ""
    )

    if not raw_section:
        return 0.5  # Neutral — assume section may be valuable

    lower = raw_section.lower().strip()

    # Exact match first
    if lower in _SECTION_SCORES:
        return _SECTION_SCORES[lower]

    # Substring match for partial section names
    for key, val in _SECTION_SCORES.items():
        if key in lower or lower in key:
            return val

    return 0.4  # Unrecognised section — slight penalty


def completeness_score(chunk_text: str) -> float:
    """
    Score chunk text quality based on length and token density.

    Heuristics:
        - Very short chunks (<30 words)  → low quality (fragments)
        - Moderate chunks (30–200 words) → ideal range for RAG
        - Very long chunks (>300 words)  → diminishing returns

    Returns:
        float in [0.0, 1.0].
    """
    if not chunk_text or not chunk_text.strip():
        return 0.0

    words = chunk_text.split()
    word_count = len(words)

    if word_count < 10:
        return 0.10  # Near-empty fragment
    if word_count < 30:
        return 0.40  # Short but might be a keyword list
    if word_count <= 100:
        return 1.00  # Ideal concise chunk
    if word_count <= 200:
        return 0.85  # Good medium chunk
    if word_count <= 300:
        return 0.70  # Acceptable, slightly verbose
    # > 300 words — too large, risk of diluting relevance signal
    return max(0.40, 0.70 - (word_count - 300) * 0.001)


def _retrieval_score_from_chunk(chunk: dict) -> float:
    """
    Derive a normalised retrieval score from existing chunk fields.

    Priority:
        1. rrf_score  (already 0–1-ish, normalised by dividing by theoretical max)
        2. distance   (ChromaDB cosine distance 0=best, 2=worst → invert)
        3. Default 0.5
    """
    # RRF score: theoretical max ≈ 1/60 + 1/60 ≈ 0.033 when both ranks=0
    # Normalise to [0, 1] assuming max ≈ 0.033
    rrf = chunk.get("rrf_score")
    if rrf is not None:
        return min(1.0, float(rrf) / 0.033)

    dist = chunk.get("distance")
    if dist is not None:
        # cosine distance ∈ [0, 2]; invert and normalise to [0, 1]
        return max(0.0, 1.0 - float(dist) / 2.0)

    return 0.5


# ──────────────────────────────────────────────────────────────────────────────
# Public Entry Point
# ──────────────────────────────────────────────────────────────────────────────

def weighted_rerank(
    query: str,
    chunks: List[dict],
    weights: Optional[RerankerWeights] = None,
) -> List[dict]:
    """
    Rerank chunks using a weighted combination of five scoring signals.

    Formula:
        final_score =
            w.semantic     * semantic_score(query, chunk_text)
          + w.metadata     * metadata_score(chunk_metadata)
          + w.section      * section_score(chunk_metadata)
          + w.completeness * completeness_score(chunk_text)
          + w.retrieval    * retrieval_score_from_chunk(chunk)

    Args:
        query:   The rewritten query string used for the retrieval step.
        chunks:  List of chunk dicts from RRF reranking stage.
                 Each dict must have at minimum: {"text": str, "metadata": dict}.
        weights: Optional RerankerWeights instance. Uses default weights if None.

    Returns:
        A new sorted list of chunk dicts (best first).
        Each chunk gets an additional "final_score" key (float).
        "text" and "metadata" are NEVER modified.

    On any error, returns the original chunks unchanged so the pipeline
    never breaks regardless of reranker failures.
    """
    if not chunks:
        return []

    w = weights or _DEFAULT_WEIGHTS

    try:
        w.validate()
    except ValueError as exc:
        logger.warning("WeightedReranker: invalid weights (%s). Using defaults.", exc)
        w = _DEFAULT_WEIGHTS

    try:
        ranked: List[dict] = []
        for chunk in chunks:
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {}) or {}

            sem   = semantic_score(query, text)
            meta_ = metadata_score(meta)
            sec   = section_score(meta)
            comp  = completeness_score(text)
            ret   = _retrieval_score_from_chunk(chunk)

            score = (
                w.semantic     * sem
                + w.metadata   * meta_
                + w.section    * sec
                + w.completeness * comp
                + w.retrieval  * ret
            )

            # Shallow copy — preserves all existing keys, adds "final_score"
            scored_chunk = {**chunk, "final_score": round(score, 6)}
            ranked.append(scored_chunk)

        ranked.sort(key=lambda c: c["final_score"], reverse=True)

        logger.info(
            "[weighted_reranker] Reranked %d chunks | top score=%.4f | bottom score=%.4f",
            len(ranked),
            ranked[0]["final_score"] if ranked else 0.0,
            ranked[-1]["final_score"] if ranked else 0.0,
        )
        return ranked

    except Exception as exc:
        logger.error(
            "[weighted_reranker] Reranking failed (%s). "
            "Returning original RRF ordering to preserve pipeline.",
            exc,
            exc_info=True,
        )
        return chunks
