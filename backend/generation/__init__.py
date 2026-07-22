"""
generation/ — Phase 3: Query Rewriting & Dynamic Generation Utilities

Modules:
    query_rewriter          — Production-quality query rewriting before retrieval
    structured_evidence     — Structured evidence extraction, scoring & aggregation engine
    dynamic_mentor          — Intent-driven retrieval-grounded AI Placement Mentor
"""

from generation.query_rewriter import QueryRewriter
from generation.structured_evidence import (
    extract_structured_evidence,
    compute_deterministic_recommendations,
    aggregate_alumni_evidence,
)
from generation.dynamic_mentor import generate_dynamic_mentor_response

__all__ = [
    "QueryRewriter",
    "extract_structured_evidence",
    "compute_deterministic_recommendations",
    "aggregate_alumni_evidence",
    "generate_dynamic_mentor_response",
]
