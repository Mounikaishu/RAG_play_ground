"""
Pydantic models for the Placement & Career Guidance Platform.
"""

from pydantic import BaseModel, field_validator
from typing import List, Optional


# ---- Auth Models ----

class RegisterRequest(BaseModel):
    name: str
    roll_no: str
    department: str
    college_email: str  # must be @svecw.edu.in
    passing_out_year: int  # e.g., 2028
    role: str = "student"  # "student" or "placement_cell"
    skills: List[str] = []
    # Password is NOT taken — default password is auto-assigned

    @field_validator("college_email")
    @classmethod
    def validate_college_email(cls, v):
        if not v.strip().lower().endswith("@svecw.edu.in"):
            raise ValueError("College email must end with @svecw.edu.in")
        return v.strip().lower()

    @field_validator("roll_no")
    @classmethod
    def normalize_roll_no(cls, v):
        return v.strip().lower()


class LoginRequest(BaseModel):
    roll_no: str
    password: str

    @field_validator("roll_no")
    @classmethod
    def normalize_roll_no(cls, v):
        return v.strip().lower()


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 6:
            raise ValueError("New password must be at least 6 characters long")
        return v


class LoginResponse(BaseModel):
    token: str
    user: dict


class UserProfile(BaseModel):
    name: str
    roll_no: str
    department: str
    college_email: str = ""
    role: str
    skills: List[str] = []
    resume_uploaded: bool = False
    passing_out_year: int = 0
    year_of_study: int = 0
    password_is_default: bool = True


# ---- Bulk Registration (Placement Cell) ----

class BulkRegisterItem(BaseModel):
    name: str
    roll_no: str
    department: str
    college_email: str  # must be @svecw.edu.in
    passing_out_year: int

    @field_validator("college_email")
    @classmethod
    def validate_college_email(cls, v):
        if not v.strip().lower().endswith("@svecw.edu.in"):
            raise ValueError("College email must end with @svecw.edu.in")
        return v.strip().lower()

    @field_validator("roll_no")
    @classmethod
    def normalize_roll_no(cls, v):
        return v.strip().lower()


class BulkRegisterRequest(BaseModel):
    students: List[BulkRegisterItem]


# ---- Student Models ----

class ChatRequest(BaseModel):
    question: str
    mode: str = "mentor"  # "mentor", "interview_prep", "ats", "resume_match"
    career_goal: Optional[str] = None
    target_company: Optional[str] = None
    target_role: Optional[str] = None


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


# ---- Placement Cell Models ----

class SearchQuery(BaseModel):
    query: str
    department_filter: Optional[str] = None
    year_filter: Optional[int] = None
    k: int = 10


class KBUploadRequest(BaseModel):
    title: str
    content: str
    category: str  # "alumni", "interview", "roadmap", "resource", "ats_template"
    company: Optional[str] = None
    role: Optional[str] = None
    round_type: Optional[str] = None


class InterviewExperienceUpload(BaseModel):
    company: str
    role: str
    round_type: str  # "technical", "hr", "system_design", "coding"
    questions: List[str]
    tips: str = ""
    difficulty: str = "medium"


class CandidateResult(BaseModel):
    name: str
    roll_no: str
    department: str
    skills: List[str]
    relevance_score: int
    matched_skills: List[str] = []
    excerpts: List[str] = []
    passing_out_year: int = 0
