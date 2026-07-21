"""
query_analyzer.py — Query Parsing & Filter Extraction Engine.

Analyzes user queries to detect metadata intent:
- Company names (Google, Amazon, Microsoft, Deloitte, NVIDIA, etc.)
- Document types (Resume, Interview Experience, Placement Material)
- Roles (Software Engineer, Data Analyst, AI Engineer)
- Job types (FTE, Internship)
- Interview rounds & difficulties (Easy, Medium, Hard)
- Section titles (Projects, Skills, Technical Round, Questions Asked)

Builds clean ChromaDB 'where' filter dictionaries.
"""

import re
import logging
from typing import Dict, Any, Optional

from knowledge_base.retrieval_models import QueryAnalysis
from knowledge_base.normalizer import (
    normalize_company,
    normalize_role,
    normalize_job_type,
    normalize_difficulty,
    COMPANY_CANONICAL_MAP,
    ROLE_CANONICAL_MAP,
)

logger = logging.getLogger("uvicorn.error")

# Document Type keywords
_DOC_TYPE_KEYWORDS = {
    "interview": "interview_experience",
    "interview experience": "interview_experience",
    "interviews": "interview_experience",
    "rounds": "interview_experience",
    "oa": "interview_experience",
    "questions": "interview_experience",
    "resume": "resume",
    "resumes": "resume",
    "cv": "resume",
    "alumni": "resume",
    "students": "resume",
    "roadmap": "placement_material",
    "placement material": "placement_material",
    "guide": "placement_material",
    "dsa": "placement_material",
}

# Section keywords
_SECTION_KEYWORDS = {
    "projects": "Projects",
    "project": "Projects",
    "skills": "Skills",
    "skill": "Skills",
    "education": "Education",
    "experience": "Experience",
    "work experience": "Experience",
    "technical round": "Technical Round",
    "hr round": "HR Round",
    "behavioral": "HR Round",
    "online assessment": "Online Assessment",
    "questions asked": "Questions Asked",
    "tips": "Tips",
}

# Section mappings to actual ChromaDB keys (with case/name variations)
_SECTION_MAPPINGS = {
    "Skills": ["SKILLS", "TECHNICAL SKILLS", "Skills", "Technical Skills"],
    "Projects": ["WORK EXPERIENCE & KEY PROJECTS", "PROJECTS", "Projects", "Key Projects", "Projects & Experience"],
    "Education": ["EDUCATION", "Education"],
    "Experience": ["WORK EXPERIENCE & KEY PROJECTS", "WORK EXPERIENCE", "EMPLOYMENT & PLACEMENT DETAILS", "EXPERIENCE", "Experience"],
}


def analyze_query(query: str) -> QueryAnalysis:
    """
    Parse a user query and return a structured QueryAnalysis with ChromaDB filters.

    Example:
        Query: "Show Hard Amazon interview experiences"
        Output: QueryAnalysis(
            original_query="Show Hard Amazon interview experiences",
            detected_company="Amazon",
            detected_difficulty="Hard",
            detected_doc_type="interview_experience",
            filters={"$and": [{"company": "Amazon"}, {"difficulty": "Hard"}]}
        )
    """
    q_lower = query.lower().strip()
    cleaned_query = query

    detected_company: Optional[str] = None
    detected_role: Optional[str] = None
    detected_job_type: Optional[str] = None
    detected_difficulty: Optional[str] = None
    detected_doc_type: Optional[str] = None
    detected_round: Optional[str] = None
    detected_section: Optional[str] = None

    # ── 1. Company Detection ─────────────────────────────────────────────
    # Scan query for matches against canonical patterns
    for pattern, canonical in COMPANY_CANONICAL_MAP.items():
        if re.search(pattern, q_lower):
            detected_company = canonical
            break

    # ── 2. Document Type Detection ───────────────────────────────────────
    for kw, doc_t in _DOC_TYPE_KEYWORDS.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
            detected_doc_type = doc_t
            break

    # ── 3. Role Detection ────────────────────────────────────────────────
    # Scan query for matches against canonical patterns
    for pattern, canonical in ROLE_CANONICAL_MAP.items():
        if re.search(pattern, q_lower):
            detected_role = canonical
            break

    # ── 4. Job Type Detection ────────────────────────────────────────────
    if any(k in q_lower for k in ["intern", "internship", "co-op"]):
        detected_job_type = "Internship"
    elif any(k in q_lower for k in ["fte", "full time", "full-time"]):
        detected_job_type = "FTE"

    # ── 5. Difficulty Detection ──────────────────────────────────────────
    if "easy" in q_lower:
        detected_difficulty = "Easy"
    elif "hard" in q_lower or "difficult" in q_lower:
        detected_difficulty = "Hard"
    elif "medium" in q_lower:
        detected_difficulty = "Medium"

    # ── 6. Interview Round Detection ─────────────────────────────────────
    if "oa" in q_lower or "online assessment" in q_lower or "coding test" in q_lower:
        detected_round = "Online Assessment"
    elif "technical round" in q_lower or "coding round" in q_lower:
        detected_round = "Technical Round 1"
    elif "hr round" in q_lower or "behavioral" in q_lower:
        detected_round = "HR / Behavioral Round"

    # ── 7. Section Detection ─────────────────────────────────────────────
    for kw, sec_t in _SECTION_KEYWORDS.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
            detected_section = sec_t
            break

    # ── 8. Build ChromaDB 'where' clause ────────────────────────────────
    conditions = []
    if detected_company:
        conditions.append({"company": detected_company})
    if detected_role:
        conditions.append({"role": detected_role})
    if detected_difficulty:
        conditions.append({"difficulty": detected_difficulty})
    if detected_job_type:
        conditions.append({"job_type": detected_job_type})
    
    # Redundant/Missing: category/document_type is handled by collection routing.
    # We do NOT add document_type to the hard where clause to prevent zero results.
    
    # section_title is kept in QueryAnalysis but not added to strict ChromaDB where_filters 
    # to allow semantic search to retrieve relevant chunks across all sections.

    if len(conditions) == 1:
        where_filters = conditions[0]
    elif len(conditions) > 1:
        where_filters = {"$and": conditions}
    else:
        where_filters = {}

    analysis = QueryAnalysis(
        original_query=query,
        cleaned_query=cleaned_query,
        detected_company=detected_company,
        detected_role=detected_role,
        detected_job_type=detected_job_type,
        detected_difficulty=detected_difficulty,
        detected_doc_type=detected_doc_type,
        detected_round=detected_round,
        detected_section=detected_section,
        filters=where_filters,
    )

    logger.info("🔍 Query Analysis for '%s': company=%s, doc_type=%s, difficulty=%s, filters=%s",
                query, detected_company, detected_doc_type, detected_difficulty, where_filters)

    return analysis
