"""
alumni_metadata_extractor.py — Structured Metadata Extraction & Normalization.

Uses LLM (Gemini) with regex fallback to extract structured metadata for:
1. Alumni Resumes (student_name, email, phone, linkedin, github, company, role, skills, education, CGPA, graduation_year, certifications, projects, experience, achievements)
2. Interview Experiences (company, role, job_type, difficulty, eligibility, package, interview_mode, rounds, technologies, dsa_topics, system_design_topics, behavioral_topics)

Applies canonical normalization via normalizer.py on extracted entities.
"""

import json
import re
from typing import Dict, Any, List
from llm import llm_call
from knowledge_base.normalizer import (
    normalize_company,
    normalize_role,
    normalize_job_type,
    normalize_rounds,
    normalize_difficulty,
    normalize_skills,
)


# ──────────────────────────────────────────────────────────
# 1. Alumni Resume Metadata Extraction
# ──────────────────────────────────────────────────────────

def extract_alumni_metadata(text: str) -> Dict[str, Any]:
    """
    Extract structured metadata from an alumni resume text.
    """
    prompt = f"""Analyze the following resume text and extract structured metadata.
Respond ONLY with a valid JSON object. No markdown fences.

Resume Text:
{text[:4000]}

JSON Schema:
{{
  "student_name": "<full name>",
  "email": "<email address or null>",
  "phone": "<phone number or null>",
  "linkedin": "<linkedin URL/handle or null>",
  "github": "<github URL/handle or null>",
  "company": "<placed company or current employer>",
  "role": "<job title>",
  "department": "<degree/department, e.g. Computer Science>",
  "graduation_year": "<4-digit year, e.g. 2023>",
  "cgpa": "<CGPA value or grade>",
  "skills": ["skill1", "skill2"],
  "education": "<short education summary>",
  "certifications": ["cert1", "cert2"],
  "projects": ["project1", "project2"],
  "experience": "<summary of work experience>",
  "achievements": ["achievement1"]
}}"""

    raw = llm_call(prompt)

    try:
        cleaned = re.sub(r"```json\s*", "", raw)
        cleaned = re.sub(r"```\s*", "", cleaned).strip()
        data = json.loads(cleaned)
    except Exception as e:
        print(f"⚠️ LLM resume metadata extraction failed: {e}. Using regex fallback.")
        data = _regex_resume_fallback(text)

    # Apply Normalization
    company = normalize_company(data.get("company", "Not Specified"))
    role = normalize_role(data.get("role", "Software Engineer"))
    skills = normalize_skills(data.get("skills", []))
    grad_year = str(data.get("graduation_year", data.get("batch", "N/A")))

    return {
        "student_name": data.get("student_name", "Unknown"),
        "email": data.get("email") or "Not Specified",
        "phone": data.get("phone") or "Not Specified",
        "linkedin": data.get("linkedin") or "Not Specified",
        "github": data.get("github") or "Not Specified",
        "company": company,
        "role": role,
        "department": data.get("department", "Computer Science"),
        "graduation_year": grad_year,
        "batch": grad_year,
        "cgpa": str(data.get("cgpa", "N/A")),
        "skills": skills,
        "education": data.get("education", "Not Specified"),
        "certifications": data.get("certifications", []),
        "projects": data.get("projects", []),
        "experience": data.get("experience", "Not Specified"),
        "achievements": data.get("achievements", []),
    }


def _regex_resume_fallback(text: str) -> Dict[str, Any]:
    """Regex fallback for resume metadata."""
    lines = text.strip().split("\n")
    name = "Unknown"
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and len(stripped) < 50:
            name = stripped
            break

    email = "Not Specified"
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    if email_match:
        email = email_match.group(0)

    linkedin = "Not Specified"
    li_match = re.search(r"linkedin\.com/in/[\w-]+", text, re.I)
    if li_match:
        linkedin = li_match.group(0)

    github = "Not Specified"
    gh_match = re.search(r"github\.com/[\w-]+", text, re.I)
    if gh_match:
        github = gh_match.group(0)

    cgpa = "N/A"
    cgpa_match = re.search(r"(?:cgpa|gpa)[:\s]+(\d\.\d{1,2})", text, re.I)
    if cgpa_match:
        cgpa = cgpa_match.group(1)

    year = "N/A"
    yr_match = re.search(r"\b(20\d{2})\b", text)
    if yr_match:
        year = yr_match.group(1)

    return {
        "student_name": name,
        "email": email,
        "phone": "Not Specified",
        "linkedin": linkedin,
        "github": github,
        "company": "Not Specified",
        "role": "Software Engineer",
        "department": "Computer Science",
        "graduation_year": year,
        "cgpa": cgpa,
        "skills": [],
        "education": "Not Specified",
        "certifications": [],
        "projects": [],
        "experience": "Not Specified",
        "achievements": [],
    }


# ──────────────────────────────────────────────────────────
# 2. Interview Experience Metadata Extraction
# ──────────────────────────────────────────────────────────

def extract_interview_metadata_from_filename(filename: str) -> Dict[str, Any]:
    """Parse initial company and role signals from filename."""
    base = filename.rsplit(".", 1)[0]
    parts = base.split("_")
    company = parts[0] if parts else "Unknown"
    role = parts[1] if len(parts) > 1 else "Software Engineer"
    return {
        "company": normalize_company(company),
        "role": normalize_role(role),
    }


def extract_interview_metadata_from_content(text: str) -> Dict[str, Any]:
    """
    Extract rich interview experience metadata using LLM or regex fallback.
    """
    prompt = f"""Analyze the following interview experience text and extract metadata.
Respond ONLY with a valid JSON object. No markdown.

Interview Experience Text:
{text[:4000]}

JSON Schema:
{{
  "company": "<company name>",
  "role": "<job role>",
  "job_type": "<FTE or Internship>",
  "difficulty": "<Easy, Medium, or Hard>",
  "eligibility": "<eligibility criteria or null>",
  "package": "<compensation/package info or null>",
  "interview_mode": "<Online, Onsite, or Hybrid>",
  "rounds": ["Online Assessment", "Technical Round 1", "HR Round"],
  "technologies": ["Python", "AWS"],
  "dsa_topics": ["Sliding Window", "Trees", "Dynamic Programming"],
  "system_design_topics": ["Rate Limiter", "LRU Cache"],
  "behavioral_topics": ["Leadership Principles", "Conflict Resolution"]
}}"""

    raw = llm_call(prompt)

    try:
        cleaned = re.sub(r"```json\s*", "", raw)
        cleaned = re.sub(r"```\s*", "", cleaned).strip()
        data = json.loads(cleaned)
    except Exception as e:
        print(f"⚠️ LLM interview metadata extraction failed: {e}. Using regex fallback.")
        data = _regex_interview_fallback(text)

    # Canonical Normalization
    company = normalize_company(data.get("company", "Unknown"))
    role = normalize_role(data.get("role", "Software Engineer"))
    job_type = normalize_job_type(data.get("job_type", "FTE"))
    difficulty = normalize_difficulty(data.get("difficulty", "Medium"))
    rounds = normalize_rounds(data.get("rounds", ["Technical Round 1"]))

    return {
        "company": company,
        "role": role,
        "job_type": job_type,
        "difficulty": difficulty,
        "eligibility": data.get("eligibility") or "Not Specified",
        "package": data.get("package") or "Not Specified",
        "interview_mode": data.get("interview_mode") or "Online",
        "rounds": rounds,
        "technologies": normalize_skills(data.get("technologies", [])),
        "dsa_topics": normalize_skills(data.get("dsa_topics", [])),
        "system_design_topics": normalize_skills(data.get("system_design_topics", [])),
        "behavioral_topics": normalize_skills(data.get("behavioral_topics", [])),
    }


def _regex_interview_fallback(text: str) -> Dict[str, Any]:
    """Regex fallback for interview experience metadata."""
    comp_match = re.search(r"Company[:\s]+(.*?)(?=\s+(?:Role|Difficulty|Round|Job Type|Eligibility|Package):|\n|$)", text, re.I)
    role_match = re.search(r"Role[:\s]+(.*?)(?=\s+(?:Company|Difficulty|Round|Job Type|Eligibility|Package):|\n|$)", text, re.I)
    diff_match = re.search(r"Difficulty[:\s]+(.*?)(?=\s+(?:Company|Role|Round|Job Type|Eligibility|Package):|\n|$)", text, re.I)

    company = comp_match.group(1).strip() if comp_match else "Unknown"
    role = role_match.group(1).strip() if role_match else "Software Engineer"
    difficulty = diff_match.group(1).strip() if diff_match else "Medium"

    rounds_found = []
    text_lower = text.lower()
    if "online assessment" in text_lower or "hackerrank" in text_lower:
        rounds_found.append("Online Assessment")
    if "technical round" in text_lower or "coding round" in text_lower:
        rounds_found.append("Technical Round 1")
    if "hr round" in text_lower or "behavioral" in text_lower:
        rounds_found.append("HR / Behavioral Round")

    return {
        "company": company,
        "role": role,
        "job_type": "FTE",
        "difficulty": difficulty,
        "eligibility": "Not Specified",
        "package": "Not Specified",
        "interview_mode": "Online",
        "rounds": rounds_found or ["Technical Round 1"],
        "technologies": [],
        "dsa_topics": [],
        "system_design_topics": [],
        "behavioral_topics": [],
    }
