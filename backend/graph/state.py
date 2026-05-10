"""
Extended LangGraph State for the Placement Platform.
"""

from typing import TypedDict, List


class PlacementState(TypedDict):
    user_id: str
    question: str
    mode: str  # "mentor", "interview_prep", "ats", "resume_match"
    context_kb: str
    context_resume: str
    context_interviews: str
    answer: str
    history: List[str]
    career_goal: str
    target_company: str
    target_role: str
