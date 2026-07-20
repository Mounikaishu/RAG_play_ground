"""
Extended LangGraph State for the Placement Platform.
"""

from typing import TypedDict, List


class PlacementState(TypedDict):
    user_id: str
    student_name: str
    student_dept: str
    student_skills: str
    question: str
    mode: str  # "mentor", "interview_prep", "resume_match"
    context_kb: str
    context_resume: str
    context_interviews: str
    context_alumni: str         # Alumni resume retrieval context
    context_placement: str      # Placement materials context
    answer: str
    history: List[str]
    career_goal: str
    target_company: str
    target_role: str
    rewritten_query: str
    source_documents: List[str]
