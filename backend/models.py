"""
Pydantic models for the Placement Platform.
"""

from pydantic import BaseModel
from typing import List, Optional

# ---- Student Models ----

class ATSScoreResponse(BaseModel):
    overall: int
    categories: dict
    summary: str
    keywords_found: List[str] = []
    keywords_missing: List[str] = []


class ResumeMatchResult(BaseModel):
    name: str
    relevance_score: int
    skills: List[str] = []
    department: str = ""
    company_placed: str = ""
