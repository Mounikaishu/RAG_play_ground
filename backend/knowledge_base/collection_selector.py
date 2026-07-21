"""
collection_selector.py — ChromaDB Collection Selection Strategy.

Selects target collections based on query intent analysis:
- "alumni_resumes" for resume, candidate, placed alumni, skills, experience queries
- "interview_experiences" for interview, round, OA, HR, coding question queries
- "placement_materials" for roadmaps, guides, DSA, strategy queries
- "institutional_kb" for university policy and general knowledge queries
"""

import logging
from typing import List, Optional
from knowledge_base.retrieval_models import QueryAnalysis

logger = logging.getLogger("uvicorn.error")

ALL_COLLECTIONS = [
    "alumni_resumes",
    "interview_experiences",
    "placement_materials",
    "institutional_kb",
]


def select_collections(
    query: str,
    analysis: Optional[QueryAnalysis] = None,
    override_collections: Optional[List[str]] = None,
) -> List[str]:
    """
    Select target ChromaDB collection names to query.

    Args:
        query: User query string
        analysis: Pre-analyzed QueryAnalysis object (optional)
        override_collections: Explicit list of collections requested by caller (optional)

    Returns:
        List of collection names to search.
    """
    if override_collections:
        # Validate requested collection names
        valid = [c for c in override_collections if c in ALL_COLLECTIONS or c.endswith("_collection") or c == "student_resumes"]
        if valid:
            return valid

    if not analysis:
        from knowledge_base.query_analyzer import analyze_query
        analysis = analyze_query(query)

    selected = []

    # ── 1. Targeted by detected document_type ────────────────────────────────
    if analysis.detected_doc_type == "interview_experience":
        selected.append("interview_experiences")
    elif analysis.detected_doc_type == "resume":
        selected.append("alumni_resumes")
    elif analysis.detected_doc_type == "placement_material":
        selected.append("placement_materials")

    # ── 2. Content signals if no strict doc_type ──────────────────────────────
    q_lower = query.lower()
    if not selected:
        if any(k in q_lower for k in ["interview", "questions", "round", "oa", "hackerrank", "bar raiser"]):
            selected.append("interview_experiences")

        if any(k in q_lower for k in ["alumni", "senior", "resume", "cv", "project", "cgpa", "who worked", "who joined"]):
            selected.append("alumni_resumes")

        if any(k in q_lower for k in ["roadmap", "guide", "dsa", "leetcode", "strategy", "preparation"]):
            selected.append("placement_materials")

    # ── 3. Multi-collection Fallback for General / Broad Queries ──────────────
    if not selected:
        selected = ["alumni_resumes", "interview_experiences", "placement_materials"]

    logger.info("🎯 CollectionSelector picked for '%s': %s", query, selected)
    return selected
