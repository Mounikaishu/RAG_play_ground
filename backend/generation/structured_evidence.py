"""
structured_evidence.py — Structured Evidence Processing, Deterministic Recommendation Engine & Confidence Model.

Architecture & Principles:
1. Converts raw retrieved state & metadata into typed, structured Evidence Objects.
2. Metadata-first extraction with dynamic, graceful fallback.
3. LLM JSON Fallback — only invoked if critical fields are missing.
4. Deterministic Reasoning Engine (Python calculates skill overlap, missing skills, match score, confidence score).
"""

import re
import json
from typing import Dict, List, Any, Optional
from llm import llm_call

class StudentProfile:
    def __init__(self, name: str = "Student", dept: str = "Unknown", skills: List[str] = None, raw_text: str = ""):
        self.evidence_id = "student_profile_1"
        self.name = name or "Student"
        self.department = dept or "Unknown"
        self.skills = set(skills or [])
        self.projects = []
        self.experience = []
        self.education = []
        self.certifications = []
        self.achievements = []
        self.raw_text = raw_text or ""
        self.has_resume = bool(raw_text and raw_text.strip() and raw_text.strip() != "No resume uploaded yet.")
        if self.has_resume:
            self._parse_raw_text()

    def _parse_raw_text(self):
        lines = self.raw_text.split("\n")
        in_projects = False
        for line in lines:
            l = line.strip()
            if not l:
                continue
            if re.search(r"\bproject(s)?\b", l, re.IGNORECASE):
                in_projects = True
                continue
            if in_projects:
                if l.startswith("#") or re.search(r"\b(experience|education|skills|certifications)\b", l, re.IGNORECASE):
                    in_projects = False
                elif l.startswith("-") or l.startswith("*") or l.startswith("•"):
                    clean_p = re.sub(r"^[-*•\s]+", "", l).split(":")[0].strip()
                    if 3 < len(clean_p) < 60:
                        self.projects.append(clean_p)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "name": self.name,
            "department": self.department,
            "skills": sorted(list(self.skills)),
            "projects": self.projects[:5],
            "experience": self.experience,
            "has_resume": self.has_resume,
        }

class AlumniProfile:
    def __init__(self, evidence_id: str, name: str, company: str, role: str, dept: str = "", skills: List[str] = None, projects: List[Dict[str, Any]] = None, raw_text: str = "", kwargs=None):
        if kwargs is None: kwargs = {}
        self.evidence_id = evidence_id
        self.name = name or "Alumni Senior"
        self.company = company or "Placed Company"
        self.role = role or "Software Engineer"
        self.department = dept or "CS"
        self.designation = kwargs.get("designation", self.role)
        self.experience = kwargs.get("experience", [])
        self.skills = set(skills or [])
        self.technologies = set(kwargs.get("technologies", []))
        self.projects = projects or []
        self.certifications = kwargs.get("certifications", [])
        self.achievements = kwargs.get("achievements", [])
        self.education = kwargs.get("education", [])
        self.career_path = kwargs.get("career_path", [])
        self.summary = kwargs.get("summary", "")
        self.confidence = kwargs.get("confidence", 0.0)
        self.raw_text = raw_text or ""
        self.source_document = kwargs.get("source_document", "")

        if raw_text and not self.skills:
            self._parse_text_skills_and_tech()

    def _parse_text_skills_and_tech(self):
        skill_keywords = ["Data Structures", "Algorithms", "Object Oriented Programming", "System Design", "Agile", "REST API", "GraphQL"]
        tech_keywords = [
            "Python", "Java", "C++", "JavaScript", "TypeScript", "React", "Node.js", "SQL",
            "PostgreSQL", "MongoDB", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "Linux",
            "Machine Learning", "Deep Learning", "NLP", "PyTorch", "TensorFlow", "Scikit-Learn",
            "FastAPI", "Django", "MLOps", "Spark", "CUDA", "LangChain", "LangGraph", "RAG", "Vector DB"
        ]
        text_lower = self.raw_text.lower()
        for sk in skill_keywords:
            if re.search(r"\b" + re.escape(sk.lower()) + r"\b", text_lower):
                self.skills.add(sk)
        for t in tech_keywords:
            if re.search(r"\b" + re.escape(t.lower()) + r"\b", text_lower):
                self.technologies.add(t)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "name": self.name,
            "company": self.company,
            "role": self.role,
            "designation": self.designation,
            "department": self.department,
            "experience": self.experience,
            "skills": sorted(list(self.skills)),
            "technologies": sorted(list(self.technologies)),
            "projects": self.projects,
            "certifications": self.certifications,
            "achievements": self.achievements,
            "education": self.education,
            "career_path": self.career_path,
        }

class InterviewExperience:
    def __init__(self, evidence_id: str, company: str, role: str, difficulty: str, author: str = "", rounds: List[str] = None, topics: List[str] = None, raw_text: str = ""):
        self.evidence_id = evidence_id
        self.company = company or "Interviewed Company"
        self.role = role or "Software Engineer"
        self.difficulty = difficulty or "Medium"
        self.author = author or "Senior"
        self.rounds = rounds or []
        self.topics = topics or []
        self.raw_text = raw_text or ""

class PlacementMaterial:
    def __init__(self, evidence_id: str, title: str, doc_type: str = "", raw_text: str = ""):
        self.evidence_id = evidence_id
        self.title = title or "Placement Guide"
        self.doc_type = doc_type or "Material"
        self.raw_text = raw_text or ""

def _llm_extract_alumni_profile(raw_text: str) -> Dict[str, Any]:
    prompt = f"""Extract the following fields from the alumni resume chunk below as a STRICT JSON object.
Do NOT fabricate information. If a field is missing, return an empty string or empty list appropriately.

JSON SCHEMA:
{{
  "name": "string",
  "company": "string (latest or most prominent)",
  "role": "string",
  "designation": "string",
  "experience": [
    {{"company": "string", "role": "string", "duration": "string", "responsibilities": ["string"]}}
  ],
  "projects": [
    {{"title": "string", "description": "string", "technologies": ["string"], "domain": "string", "impact": "string"}}
  ],
  "technologies": ["string (e.g. Python, PyTorch)"],
  "skills": ["string (e.g. Agile, Machine Learning)"],
  "certifications": ["string"],
  "achievements": ["string"],
  "education": ["string"],
  "career_path": ["string"],
  "summary": "string"
}}

RESUME CHUNK:
{raw_text}

Return ONLY valid JSON:"""
    try:
        response = llm_call(prompt)
        # Strip markdown code blocks
        clean_json = re.sub(r"^```json\s*", "", response.strip())
        clean_json = re.sub(r"```$", "", clean_json.strip())
        data = json.loads(clean_json)
        return data
    except Exception as e:
        print(f"⚠️ [LLM EXTRACTION FAILED] {e}")
        return {}

def _print_alumni_extraction_report(alumni: AlumniProfile, source: str):
    print("\n" + "="*48)
    print("Alumni Extraction Report")
    print(f"Source: {source}")
    print(f"Name\n✓ {alumni.name}") if alumni.name and alumni.name != "Alumni Senior" else print("Name\nNot Found")
    print(f"Company\n✓ {alumni.company}") if alumni.company and alumni.company != "Placed Company" else print("Company\nNot Found")
    print(f"Role\n✓ {alumni.role}") if alumni.role and alumni.role != "Software Engineer" else print("Role\nNot Found")
    
    if alumni.experience:
        print(f"Experience\n✓ {len(alumni.experience)} entries")
    else:
        print("Experience\nNot Found\nReason: Section not detected or missing.")
        
    if alumni.projects:
        print(f"Projects\n✓ {len(alumni.projects)}")
    else:
        print("Projects\nNot Found\nReason: Section not detected or missing.")
        
    print(f"Technologies\n✓ {len(alumni.technologies)}")
    print(f"Skills\n✓ {len(alumni.skills)}")
    print(f"Certifications\n✓ {len(alumni.certifications)}")
    print(f"Achievements\n✓ {len(alumni.achievements)}")
    print(f"Confidence\n{alumni.confidence:.2f}")
    print("="*48 + "\n")


def extract_structured_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Student Profile
    student_skills_str = state.get("student_skills", "")
    known_skills = [s.strip() for s in student_skills_str.split(",") if s.strip() and s.strip() != "None specified"]
    student = StudentProfile(
        name=state.get("student_name", "Student"),
        dept=state.get("student_dept", "Unknown"),
        skills=known_skills,
        raw_text=state.get("context_resume", "")
    )

    # 2. Alumni Profiles
    alumni_list: List[AlumniProfile] = []
    alumni_raw = state.get("context_alumni", "") + "\n\n" + state.get("context_kb", "")
    chunks = alumni_raw.split("### Chunk ") if "### Chunk " in alumni_raw else [alumni_raw]

    for idx, chunk in enumerate(chunks, 1):
        if not chunk.strip():
            continue

        name, company, role = None, None, None
        projects_parsed, experience_parsed = [], []
        tech_parsed, cert_parsed = [], []
        
        # Simple Deterministic Parsing (Metadata and early headers)
        name_m = re.search(r"Resume\s*—\s*([^\n\*\#\|]+)", chunk, re.IGNORECASE) or re.search(r"Name:\s*([^\n]+)", chunk, re.IGNORECASE)
        if name_m: name = name_m.group(1).strip()
        
        comp_m = re.search(r"\*\*Company\*\*\s*:\s*([^\|\n]+)", chunk, re.IGNORECASE) or re.search(r"company\s*:\s*([^,\|\n]+)", chunk, re.IGNORECASE)
        if comp_m: company = comp_m.group(1).strip()
        
        role_m = re.search(r"\*\*Role\*\*\s*:\s*([^\|\n]+)", chunk, re.IGNORECASE) or re.search(r"role\s*:\s*([^,\|\n]+)", chunk, re.IGNORECASE)
        if role_m: role = role_m.group(1).strip()
        
        # Check if critical fields are missing
        needs_llm = False
        if not name or name.lower() == "alumni": needs_llm = True
        if not company: needs_llm = True
        if not re.search(r"\bproject(s)?\b", chunk, re.IGNORECASE):
            # No explicit projects found easily
            needs_llm = True
            
        kwargs = {}
        if needs_llm and ("resume" in chunk.lower() or name or company or role):
            print(f"🔍 [EXTRACTION] Deterministic parsing incomplete for Alumni chunk {idx}. Invoking LLM Fallback...")
            extracted_json = _llm_extract_alumni_profile(chunk)
            
            if extracted_json:
                name = name or extracted_json.get("name")
                company = company or extracted_json.get("company")
                role = role or extracted_json.get("role")
                kwargs["designation"] = extracted_json.get("designation", "")
                kwargs["experience"] = extracted_json.get("experience", [])
                kwargs["certifications"] = extracted_json.get("certifications", [])
                kwargs["achievements"] = extracted_json.get("achievements", [])
                kwargs["education"] = extracted_json.get("education", [])
                kwargs["career_path"] = extracted_json.get("career_path", [])
                kwargs["summary"] = extracted_json.get("summary", "")
                
                projects_parsed = extracted_json.get("projects", [])
                tech_parsed = extracted_json.get("technologies", [])
                
        # Final name fallback
        if not name or name == "Alumni":
            candidate_names = re.findall(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", chunk)
            for cand in candidate_names:
                if cand not in ["Software Engineer", "Machine Learning", "Data Scientist", "Full Stack", "Computer Science", "Unknown Alumni"]:
                    name = cand
                    break

        if name or company or role or "resume" in chunk.lower():
            kwargs["technologies"] = tech_parsed
            alumni_prof = AlumniProfile(
                evidence_id=f"alumni_ev_{idx}",
                name=name,
                company=company,
                role=role,
                projects=projects_parsed,
                raw_text=chunk.strip(),
                kwargs=kwargs
            )
            alumni_prof.confidence = 0.95 if (alumni_prof.name and alumni_prof.company) else 0.6
            _print_alumni_extraction_report(alumni_prof, f"alumni_chunk_{idx}")
            alumni_list.append(alumni_prof)

    # 3. Interview Experiences
    interview_list: List[InterviewExperience] = []
    interview_raw = state.get("context_interviews", "")
    i_chunks = interview_raw.split("### Chunk ") if "### Chunk " in interview_raw else [interview_raw]

    for idx, chunk in enumerate(i_chunks, 1):
        if not chunk.strip(): continue
        comp = None
        diff = "Medium"
        comp_m = re.search(r"Interview Experience\s*—\s*([^\(\n\|]+)", chunk, re.IGNORECASE) or re.search(r"\*\*Company\*\*\s*:\s*([^\|\n]+)", chunk, re.IGNORECASE)
        if comp_m: comp = comp_m.group(1).strip()
        diff_m = re.search(r"\*\*Difficulty\*\*\s*:\s*([^\|\n]+)", chunk, re.IGNORECASE)
        if diff_m: diff = diff_m.group(1).strip()

        if comp or "interview" in chunk.lower():
            interview_list.append(InterviewExperience(
                evidence_id=f"interview_ev_{idx}",
                company=comp,
                role="Software Engineer",
                difficulty=diff,
                raw_text=chunk.strip()
            ))

    # 4. Placement Materials
    placement_list: List[PlacementMaterial] = []
    placement_raw = state.get("context_placement", "")
    p_chunks = placement_raw.split("### Chunk ") if "### Chunk " in placement_raw else [placement_raw]
    for idx, chunk in enumerate(p_chunks, 1):
        if not chunk.strip(): continue
        title_m = re.search(r"### Chunk \d+:\s*([^\n]+)", chunk)
        title = title_m.group(1).strip() if title_m else "Placement Resource"
        placement_list.append(PlacementMaterial(
            evidence_id=f"placement_ev_{idx}",
            title=title,
            raw_text=chunk.strip()
        ))

    return {
        "student": student,
        "alumni": alumni_list,
        "interviews": interview_list,
        "placement": placement_list,
    }

def compute_deterministic_recommendations(student: StudentProfile, alumni_list: List[AlumniProfile]) -> List[Dict[str, Any]]:
    matches = []
    for alumni in alumni_list:
        matching_skills = sorted(list(student.skills & alumni.skills))
        missing_skills = sorted(list(alumni.skills - student.skills))
        
        skill_overlap_ratio = len(matching_skills) / max(len(alumni.skills), 1)
        
        matching_projects = []
        for s_proj in student.projects:
            for a_proj_dict in alumni.projects:
                a_proj = a_proj_dict.get("title", "") + " " + a_proj_dict.get("description", "")
                s_words = set(s_proj.lower().split())
                a_words = set(a_proj.lower().split())
                if len(s_words & a_words) >= 1:
                    matching_projects.append({"student_project": s_proj, "alumni_project": a_proj_dict.get("title", "")})
                    
        proj_overlap_ratio = len(matching_projects) / max(len(alumni.projects), 1) if alumni.projects else 0.5
        match_score = round((skill_overlap_ratio * 0.7 + proj_overlap_ratio * 0.3) * 100, 1)
        
        has_specific_name = alumni.name not in ["Alumni", "Alumni Senior", "Unknown Alumni"]
        has_specific_company = alumni.company not in ["Placed Company", "Unknown Company"]
        
        evidence_richness_score = round((1.0 if has_specific_name else 0.6) * (1.0 if has_specific_company else 0.6) * 100, 1)
        overall_confidence_score = round((match_score * 0.6 + evidence_richness_score * 0.4), 1)
        confidence_level = "High" if overall_confidence_score >= 75 else ("Medium" if overall_confidence_score >= 45 else "Low")
        
        matches.append({
            "evidence_id": alumni.evidence_id,
            "alumni_name": alumni.name,
            "company": alumni.company,
            "role": alumni.role,
            "designation": getattr(alumni, 'designation', alumni.role),
            "experience": getattr(alumni, 'experience', []),
            "projects": getattr(alumni, 'projects', []),
            "technologies": sorted(list(alumni.technologies)) if hasattr(alumni, 'technologies') else [],
            "certifications": getattr(alumni, 'certifications', []),
            "career_path": getattr(alumni, 'career_path', []),
            "matching_skills": matching_skills,
            "missing_skills": missing_skills,
            "matching_projects": matching_projects,
            "match_score": match_score,
            "confidence_score": overall_confidence_score,
            "confidence_level": confidence_level,
            "evidence_richness": evidence_richness_score,
            "raw_text": alumni.raw_text,
        })

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches
