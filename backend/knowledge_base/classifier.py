"""
classifier.py — Automatic Document Classifier for PlaceAI Ingestion.

Classifies documents into supported types:
- Alumni Resume
- Interview Experience
- Placement Material
- Student Resume
- Unknown

Uses content analysis + filename signals to route misplaced files correctly.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("uvicorn.error")


def classify_document(filename: str, text_sample: str, folder_type: str = "") -> Tuple[str, float]:
    """
    Classify a document based on its text content and filename.

    Args:
        filename: Original filename (e.g. "Amazon_SDE1_AllRounds.pdf")
        text_sample: Extracted text or section titles (first 3000 chars)
        folder_type: Original folder directory hint

    Returns:
        Tuple of (detected_document_type, confidence_score)
        where detected_document_type is one of:
          - "Alumni Resume"
          - "Interview Experience"
          - "Placement Material"
          - "Student Resume"
          - "Unknown"
    """
    text_lower = text_sample.lower()
    fn_lower = filename.lower()

    # Signals score dict
    scores = {
        "Alumni Resume": 0.0,
        "Interview Experience": 0.0,
        "Placement Material": 0.0,
        "Student Resume": 0.0,
    }

    # ── 1. Interview Experience Signals ──────────────────────────────────────
    interview_keywords = [
        "interview experience", "online assessment", "coding round", "technical round",
        "hr round", "bar raiser", "questions asked", "hackerrank", "eligibility criteria",
        "rounds", "difficulty", "compensation", "package", "onsite round"
    ]
    for kw in interview_keywords:
        if kw in text_lower:
            scores["Interview Experience"] += 1.5
        if kw in fn_lower:
            scores["Interview Experience"] += 2.0

    if re.search(r"round\s*\d|oa|technical|behavioral|salary|ctc|stipend", fn_lower):
        scores["Interview Experience"] += 1.5

    # ── 2. Resume Signals (Alumni vs Student) ─────────────────────────────────
    resume_keywords = [
        "education", "work experience", "projects", "skills", "certifications",
        "cgpa", "b.tech", "m.tech", "github.com", "linkedin.com", "achievements"
    ]
    for kw in resume_keywords:
        if kw in text_lower:
            scores["Alumni Resume"] += 1.0
            scores["Student Resume"] += 1.0

    # Distinguish Alumni vs Student Resume
    alumni_signals = ["placed at", "experience", "senior engineer", "work experience", "batch of 20", "alumni", "company:"]
    student_signals = ["roll no", "semester", "student id", "current student", "internship target"]

    for kw in alumni_signals:
        if kw in text_lower:
            scores["Alumni Resume"] += 1.5
        if kw in fn_lower:
            scores["Alumni Resume"] += 2.0

    for kw in student_signals:
        if kw in text_lower:
            scores["Student Resume"] += 1.5
        if kw in fn_lower:
            scores["Student Resume"] += 2.0

    # ── 3. Placement Material Signals ─────────────────────────────────────────
    placement_keywords = [
        "ats guide", "career roadmap", "dsa questions", "leetcode patterns",
        "system design guide", "placement handbook", "preparation strategy",
        "cheat sheet", "syllabus", "company wise questions"
    ]
    for kw in placement_keywords:
        if kw in text_lower:
            scores["Placement Material"] += 1.5
        if kw in fn_lower:
            scores["Placement Material"] += 2.0

    # ── 4. Folder Hint Boost ──────────────────────────────────────────────────
    folder_map = {
        "alumni_resumes": "Alumni Resume",
        "interview_experiences": "Interview Experience",
        "interview_experiencee": "Interview Experience",
        "placement_materials": "Placement Material",
        "student_resumes": "Student Resume",
    }
    hint = folder_map.get(folder_type)
    if hint and hint in scores:
        scores[hint] += 1.0

    # ── Determine Winner ─────────────────────────────────────────────────────
    best_type = max(scores, key=scores.get)
    max_score = scores[best_type]

    if max_score < 1.5:
        return "Unknown", 0.0

    confidence = min(1.0, max_score / 6.0)
    logger.info("🏷️ Document '%s' classified as '%s' (confidence: %.2f)", filename, best_type, confidence)

    return best_type, confidence
