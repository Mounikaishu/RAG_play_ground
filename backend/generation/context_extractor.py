"""
context_extractor.py — Structured Context Extractor & Generator Logger for PlaceAI.

Rule 11: Generation Logging (chunk counts, names, companies, skills, projects, validation).
Rule 12: Pre-generation structured context extraction.
Rule 13: Priority handling (Student Resume > Alumni > Interviews > Placement).
Rule 14: Preserve retrieved details (names, companies, projects).
"""

import re
from typing import Dict, List, Any

def extract_structured_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts structured representation of Student, Alumni, Interview, and Placement context
    from the LangGraph state.
    """
    resume_raw = state.get("context_resume", "")
    alumni_raw = state.get("context_alumni", "")
    kb_raw = state.get("context_kb", "")
    interview_raw = state.get("context_interviews", "")
    placement_raw = state.get("context_placement", "")

    # Count Chunks
    resume_chunks_count = 1 if resume_raw and resume_raw.strip() != "No resume uploaded yet." else 0
    alumni_chunks_count = alumni_raw.count("### Chunk") if "### Chunk" in alumni_raw else (1 if alumni_raw.strip() else 0)
    interview_chunks_count = interview_raw.count("### Chunk") if "### Chunk" in interview_raw else (1 if interview_raw.strip() else 0)
    placement_chunks_count = placement_raw.count("### Chunk") if "### Chunk" in placement_raw else (1 if placement_raw.strip() else 0)

    # 1. Extract Student Profile
    student_profile = {
        "name": state.get("student_name", "Student"),
        "department": state.get("student_dept", "Unknown"),
        "known_skills": state.get("student_skills", "None specified"),
        "has_resume": resume_raw and resume_raw.strip() != "No resume uploaded yet.",
        "raw_resume": resume_raw if resume_raw and resume_raw.strip() != "No resume uploaded yet." else None,
        "skills": [],
        "projects": [],
        "education": [],
        "experience": [],
        "certifications": [],
        "achievements": [],
    }

    if student_profile["has_resume"]:
        # Extract skills, projects, etc. from resume_raw
        student_profile["skills"] = _extract_skills_from_text(resume_raw)
        if not student_profile["skills"] and state.get("student_skills"):
            student_profile["skills"] = [s.strip() for s in state["student_skills"].split(",") if s.strip()]
        student_profile["projects"] = _extract_projects_from_text(resume_raw)
    elif state.get("student_skills") and state.get("student_skills") != "None specified":
        student_profile["skills"] = [s.strip() for s in state["student_skills"].split(",") if s.strip()]

    # 2. Extract Alumni Profiles
    alumni_profiles = _extract_alumni_profiles(alumni_raw + "\n\n" + kb_raw)

    # 3. Extract Interview Experiences
    interview_experiences = _extract_interview_experiences(interview_raw)

    # 4. Extract Placement Materials Summary
    placement_materials = _extract_placement_materials(placement_raw)

    # Aggregate extracted entities for logging & validation
    all_names = list(set([a["name"] for a in alumni_profiles if a["name"] and a["name"] != "Unknown Alumni"]))
    all_companies = list(set(
        [a["company"] for a in alumni_profiles if a["company"] and a["company"] != "Unknown Company"] +
        [i["company"] for i in interview_experiences if i["company"] and i["company"] != "Unknown Company"]
    ))
    all_skills = list(set(student_profile["skills"] + [s for a in alumni_profiles for s in a.get("skills", [])]))
    all_projects = list(set(student_profile["projects"] + [p for a in alumni_profiles for p in a.get("projects", [])]))

    extracted = {
        "student": student_profile,
        "alumni": alumni_profiles,
        "interviews": interview_experiences,
        "placement": placement_materials,
        "stats": {
            "resume_chunks": resume_chunks_count,
            "alumni_chunks": alumni_chunks_count,
            "interview_chunks": interview_chunks_count,
            "placement_chunks": placement_chunks_count,
            "names": all_names,
            "companies": all_companies,
            "skills": all_skills,
            "projects": all_projects,
        }
    }

    # Rule 11: Generation Logging
    _log_extraction_stats(extracted["stats"])

    return extracted


def _log_extraction_stats(stats: Dict[str, Any]):
    print("\n" + "═" * 60)
    print("📊 [GENERATION LOGGING] Structured Context Extraction")
    print("═" * 60)
    print(f"  • Chunks Loaded   : Resume={stats['resume_chunks']}, Alumni={stats['alumni_chunks']}, Interviews={stats['interview_chunks']}, Placement={stats['placement_chunks']}")
    print(f"  • Names Extracted : {stats['names'] if stats['names'] else 'None found'}")
    print(f"  • Companies       : {stats['companies'] if stats['companies'] else 'None found'}")
    print(f"  • Skills Extracted: {stats['skills'][:10]}{'...' if len(stats['skills']) > 10 else ''}")
    print(f"  • Projects        : {stats['projects'][:5]}{'...' if len(stats['projects']) > 5 else ''}")
    print("═" * 60 + "\n")


def _extract_skills_from_text(text: str) -> List[str]:
    skills = []
    # Common tech keywords regex matching
    common_skills = [
        "Python", "Java", "C++", "C#", "JavaScript", "TypeScript", "React", "Node.js", "Express",
        "HTML", "CSS", "SQL", "PostgreSQL", "MongoDB", "MySQL", "Docker", "Kubernetes", "AWS",
        "Azure", "GCP", "Git", "Linux", "Machine Learning", "Deep Learning", "NLP", "PyTorch",
        "TensorFlow", "Scikit-Learn", "OpenCV", "Pandas", "NumPy", "Flask", "FastAPI", "Django",
        "MLOps", "Spark", "Hadoop", "Tableau", "Power BI", "Data Structures", "Algorithms"
    ]
    text_lower = text.lower()
    for sk in common_skills:
        pattern = r"\b" + re.escape(sk.lower()) + r"\b"
        if re.search(pattern, text_lower):
            skills.append(sk)
    return list(dict.fromkeys(skills))


def _extract_projects_from_text(text: str) -> List[str]:
    projects = []
    # Match bullet points under Project headers or lines containing 'project'
    lines = text.split("\n")
    in_project_sec = False
    for line in lines:
        l_str = line.strip()
        if not l_str:
            continue
        if re.search(r"project", l_str, re.IGNORECASE):
            in_project_sec = True
            continue
        if in_project_sec:
            if l_str.startswith("#") or l_str.startswith("**Experience") or l_str.startswith("**Education"):
                in_project_sec = False
                continue
            if l_str.startswith("-") or l_str.startswith("*") or l_str.startswith("•"):
                p_name = re.sub(r"^[-*•\s]+", "", l_str).split(":")[0].strip()
                if len(p_name) > 3 and len(p_name) < 60:
                    projects.append(p_name)
    return list(dict.fromkeys(projects))[:5]


def _extract_alumni_profiles(raw_text: str) -> List[Dict[str, Any]]:
    profiles = []
    if not raw_text or not raw_text.strip():
        return profiles

    # Split by Chunk if available or process as blocks
    chunks = raw_text.split("### Chunk ") if "### Chunk " in raw_text else [raw_text]

    for chunk in chunks:
        if not chunk.strip():
            continue
        lines = chunk.strip().split("\n")
        header = lines[0] if lines else ""

        name = "Unknown Alumni"
        company = "Unknown Company"
        role = "Software Engineer"
        dept = "CS"

        # Regex for header: Resume — Name, Company: X | Role: Y
        name_match = re.search(r"Resume\s*—\s*([^\n\*\#\|]+)", header, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()

        comp_match = re.search(r"Company\*\*\s*:\s*([^\|]+)", chunk, re.IGNORECASE) or re.search(r"company\s*:\s*([^,\|\n]+)", chunk, re.IGNORECASE)
        if comp_match:
            company = comp_match.group(1).strip()

        role_match = re.search(r"Role\*\*\s*:\s*([^\|]+)", chunk, re.IGNORECASE) or re.search(r"role\s*:\s*([^,\|\n]+)", chunk, re.IGNORECASE)
        if role_match:
            role = role_match.group(1).strip()

        skills = _extract_skills_from_text(chunk)
        projects = _extract_projects_from_text(chunk)

        # If name wasn't in header, try body regex e.g. "Aarav Sharma", "Priya Sharma", etc.
        if name == "Unknown Alumni":
            name_in_body = re.search(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", chunk)
            if name_in_body:
                cand = name_in_body.group(1)
                if cand not in ["Software Engineer", "Machine Learning", "Data Scientist", "Full Stack", "Computer Science", "Unknown Alumni"]:
                    name = cand

        profiles.append({
            "name": name,
            "company": company,
            "role": role,
            "skills": skills,
            "projects": projects,
            "full_text": chunk.strip()
        })

    return profiles


def _extract_interview_experiences(raw_text: str) -> List[Dict[str, Any]]:
    experiences = []
    if not raw_text or not raw_text.strip():
        return experiences

    chunks = raw_text.split("### Chunk ") if "### Chunk " in raw_text else [raw_text]

    for chunk in chunks:
        if not chunk.strip():
            continue
        company = "Unknown Company"
        role = "Software Engineer"
        difficulty = "Medium"

        comp_match = re.search(r"Interview Experience\s*—\s*([^\(\n\|]+)", chunk, re.IGNORECASE) or re.search(r"Company\*\*\s*:\s*([^\|]+)", chunk, re.IGNORECASE)
        if comp_match:
            company = comp_match.group(1).strip()

        diff_match = re.search(r"Difficulty\*\*\s*:\s*([^\|]+)", chunk, re.IGNORECASE)
        if diff_match:
            difficulty = diff_match.group(1).strip()

        # Try to find senior name
        author = "Senior Alumni"
        author_match = re.search(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", chunk)
        if author_match and author_match.group(1) not in ["Hacker Rank", "Data Structures", "Computer Science", "Software Engineer"]:
            author = author_match.group(1)

        experiences.append({
            "company": company,
            "role": role,
            "difficulty": difficulty,
            "author": author,
            "full_text": chunk.strip()
        })

    return experiences


def _extract_placement_materials(raw_text: str) -> str:
    return raw_text.strip() if raw_text else ""
