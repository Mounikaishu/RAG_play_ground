"""
structured_evidence.py — Structured Evidence Processing, Recommendation Engine & Confidence Model.

Fixes applied (Issues 1-12):
  1. Alumni name extraction: blocklist + person-name validator + LLM fallback only when needed
  2. Student profile: full structured project extraction (title, description, technologies, domain, impact)
  3. Multiple alumni: group chunks by source document → one AlumniProfile per alumnus → Top-5
  4. Match score: 5-factor weighted scoring from config (skills/tech/projects/education/experience)
  5. Interview extraction: rounds, topics, FAQs, prep tips extracted deterministically + LLM fallback
  6. (Intent lives in dynamic_mentor.py)
  7. Evidence aggregation: common skills/tech/companies/career-paths across Top-N alumni
  8. Project comparison: technology + domain + keyword overlap (no hallucination)
  9-12. All fields forwarded; detailed debug reports at every stage.
"""

import re
import json
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional, Tuple, Union

from llm import llm_call
from config import MATCH_SCORE_WEIGHTS, TOP_ALUMNI_COUNT, CONFIDENCE_HIGH_THRESHOLD, CONFIDENCE_MEDIUM_THRESHOLD

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Exact-match blocklist for strings that look like names but are not people
INVALID_ALUMNI_NAMES = {
    # Generic resume section headings
    "alumni journey", "resume", "professional summary", "career journey",
    "profile", "curriculum vitae", "cv", "overview", "about me",
    "introduction", "background", "summary", "bio", "biography",
    "skills", "technical skills", "education", "experience", "work experience",
    "projects", "academic projects", "personal projects", "professional projects",
    "certifications", "achievements", "awards", "honors", "publications",
    "languages", "interests", "hobbies", "references", "contact",
    # Advice / placement content
    "placement tips", "career advice", "interview tips", "preparation tips",
    "career guidance", "mentorship", "study plan", "preparation",
    # Technical terms (never a person name)
    "linux kernel", "distributed systems", "machine learning", "deep learning",
    "neural networks", "data structures", "algorithms", "system design",
    "object oriented", "computer science", "artificial intelligence",
    "software engineering", "web development", "data science", "mlops",
    # Company/employer markers
    "current employer", "employer", "company", "organization", "workplace",
    # Common heading fragments
    "work history", "career history", "job history", "professional experience",
    "key skills", "core competencies", "areas of expertise",
}

GENERIC_HEADINGS = INVALID_ALUMNI_NAMES  # keep alias for backward compat

# Words that indicate a string is NOT a human first/last name
NON_NAME_WORDS = {
    # Job titles / seniority
    "Software", "Engineer", "Machine", "Learning", "Data", "Scientist",
    "Full", "Stack", "Computer", "Science", "Alumni", "Manager",
    "Technical", "Senior", "Junior", "Lead", "Engineering", "Developer",
    "Analyst", "Architect", "Intern", "Designer", "Product", "Research",
    "Associate", "Consultant", "Director", "Officer", "Specialist", "Head",
    "Principal", "Staff", "Distinguished", "Fellow",
    # Company names
    "Adobe", "Google", "Microsoft", "Amazon", "Meta", "Apple", "NVIDIA",
    "Netflix", "Flipkart", "Swiggy", "Zomato", "Oracle", "Salesforce",
    # Generic markers
    "Unknown", "Placed", "Company", "University", "Institute", "College",
    # Technical topics (appear in section titles)
    "Linux", "Kernel", "Distributed", "Systems", "Networks", "Database",
    "Algorithms", "Structures", "Placement", "Tips", "Advice", "Preparation",
    "Current", "Employer", "Organization", "Workplace",
}

TECH_KEYWORDS = [
    "Python", "Java", "C++", "C#", "JavaScript", "TypeScript", "Go", "Rust",
    "React", "Node.js", "Express", "Angular", "Vue", "Next.js",
    "HTML", "CSS", "SQL", "PostgreSQL", "MongoDB", "MySQL", "Redis",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "Linux",
    "Machine Learning", "Deep Learning", "NLP", "PyTorch", "TensorFlow",
    "Scikit-Learn", "OpenCV", "Pandas", "NumPy", "Matplotlib", "Seaborn",
    "Flask", "FastAPI", "Django", "Spring Boot",
    "MLOps", "Spark", "Hadoop", "Kafka", "Airflow", "CUDA",
    "LangChain", "LangGraph", "RAG", "Vector DB", "ChromaDB", "Pinecone",
    "Stable Diffusion", "BLIP", "BERT", "GPT", "LLM", "Transformers",
    "Tableau", "Power BI", "Looker", "BigQuery",
    "Data Structures", "Algorithms", "System Design", "Agile", "REST API", "GraphQL",
]

SKILL_KEYWORDS = [
    "Data Structures", "Algorithms", "Object Oriented Programming", "System Design",
    "Agile", "REST API", "GraphQL", "Machine Learning", "Deep Learning", "NLP",
    "Computer Vision", "Generative AI", "MLOps", "DevOps", "Communication",
    "Leadership", "Problem Solving", "Critical Thinking",
]

# Section headers in resumes that should NEVER be mistaken for project titles
ADVICE_SECTION_MARKERS = {
    "placement tips", "career advice", "interview tips", "preparation",
    "goals", "career goals", "career objective", "objective",
    "tips", "advice", "guidance", "mentorship", "study plan",
    "for ml roles", "for data science", "for software", "to get placed",
    "how to", "steps to", "roadmap",
}

# ---------------------------------------------------------------------------
# Helpers: Name Validation
# ---------------------------------------------------------------------------

def _is_valid_person_name(name: str) -> bool:
    """Return True only if name looks like a real human name (Issues 1 & 6)."""
    if not name:
        return False
    name = name.strip()

    # Immediate exact-match rejection against full blocklist
    if name.lower() in INVALID_ALUMNI_NAMES:
        return False

    if len(name) < 4 or len(name) > 60:
        return False

    # Must have at least two parts (First Last)
    parts = name.split()
    if len(parts) < 2 or len(parts) > 5:
        return False

    # Each part must start with a capital letter and be mostly alpha
    for p in parts:
        if not p:
            continue
        if not p[0].isupper():
            return False
        alpha_r = sum(c.isalpha() for c in p) / max(len(p), 1)
        if alpha_r < 0.6:
            return False

    # Reject if ANY part is a known non-name word
    if any(p in NON_NAME_WORDS for p in parts):
        return False

    # Reject strings with digits (serial numbers, IDs)
    if any(c.isdigit() for c in name):
        return False

    # Reject substrings of known advice/section phrases
    name_lower = name.lower()
    for marker in ADVICE_SECTION_MARKERS:
        if marker in name_lower:
            return False

    # Must be mostly alphabetic (allow spaces, hyphens, apostrophes)
    alpha_ratio = sum(c.isalpha() or c in " -'" for c in name) / max(len(name), 1)
    if alpha_ratio < 0.8:
        return False

    return True


def _extract_name_deterministic(chunk: str, metadata: dict) -> Optional[str]:
    """
    Multi-stage deterministic name extraction (Issue 1).
    Priority: metadata → title line → body scan.
    """
    # Stage 1: Metadata
    for field in ("alumni_name", "name", "student_name", "author"):
        val = metadata.get(field, "")
        if val and _is_valid_person_name(str(val)):
            return str(val).strip()

    # Stage 2: Title patterns  e.g. "Resume — Meera Krishnan" or "Name: Meera Krishnan"
    title_patterns = [
        r"Resume\s*[—\-:]\s*([^\n\*\#\|]{3,50})",
        r"Name\s*[:\-]\s*([^\n\*\#\|]{3,50})",
        r"Student\s*Name\s*[:\-]\s*([^\n\*\#\|]{3,50})",
    ]
    for pat in title_patterns:
        m = re.search(pat, chunk[:800], re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().split("|")[0].strip().split("\n")[0].strip()
            if _is_valid_person_name(candidate):
                return candidate

    # Stage 3: First valid "Firstname Lastname" pattern in first 1 500 chars
    name_pattern = re.findall(r"\b([A-Z][a-z]{1,14}\s+[A-Z][a-z]{1,19}(?:\s+[A-Z][a-z]{1,14})?)\b", chunk[:1500])
    for cand in name_pattern:
        if _is_valid_person_name(cand):
            return cand

    return None


def _llm_extract_name_only(raw_text: str) -> Optional[str]:
    """LLM fallback for name extraction ONLY (Issue 1 — minimal LLM use)."""
    prompt = (
        "Extract ONLY the full name of the person whose resume or profile is shown below.\n"
        "Return ONLY the name as plain text, nothing else.\n"
        "If you cannot find a real person name, return the word: UNKNOWN\n\n"
        f"DOCUMENT:\n{raw_text[:1200]}"
    )
    try:
        result = llm_call(prompt).strip()
        if result and result != "UNKNOWN" and _is_valid_person_name(result):
            return result
    except Exception as e:
        print(f"⚠️ [LLM NAME FALLBACK] {e}")
    return None


# ---------------------------------------------------------------------------
# LLM: Full Alumni Profile Extraction (used when deterministic is incomplete)
# ---------------------------------------------------------------------------

def _llm_extract_alumni_profile(raw_text: str) -> Dict[str, Any]:
    prompt = f"""Extract the following fields from the alumni resume chunk as a STRICT JSON object.
Do NOT fabricate information. Return empty string or empty list if a field is missing.

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
  "technologies": ["string"],
  "skills": ["string"],
  "certifications": ["string"],
  "achievements": ["string"],
  "education": ["string"],
  "career_path": ["string"],
  "summary": "string"
}}

RESUME CHUNK:
{raw_text[:2000]}

Return ONLY valid JSON:"""
    try:
        response = llm_call(prompt)
        clean = re.sub(r"^```json\s*", "", response.strip())
        clean = re.sub(r"```$", "", clean.strip())
        return json.loads(clean)
    except Exception as e:
        print(f"⚠️ [LLM ALUMNI EXTRACTION FAILED] {e}")
        return {}


def _llm_extract_interview(raw_text: str) -> Dict[str, Any]:
    """LLM fallback for interview field extraction (Issue 5)."""
    prompt = f"""Extract interview experience fields as a STRICT JSON object.
Do NOT fabricate. Return empty list if field is missing.

JSON SCHEMA:
{{
  "company": "string",
  "role": "string",
  "difficulty": "string (Easy/Medium/Hard)",
  "rounds": ["string (e.g. OA, Technical Round 1, HR)"],
  "topics": ["string (e.g. DSA, System Design)"],
  "faqs": ["string (actual questions asked)"],
  "prep_tips": ["string"]
}}

INTERVIEW DOCUMENT:
{raw_text[:1500]}

Return ONLY valid JSON:"""
    try:
        response = llm_call(prompt)
        clean = re.sub(r"^```json\s*", "", response.strip())
        clean = re.sub(r"```$", "", clean.strip())
        return json.loads(clean)
    except Exception as e:
        print(f"⚠️ [LLM INTERVIEW EXTRACTION FAILED] {e}")
        return {}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

class StudentProfile:
    def __init__(self, name: str = "Student", dept: str = "Unknown",
                 skills: List[str] = None, raw_text: str = ""):
        self.evidence_id = "student_profile_1"
        self.name = name or "Student"
        self.department = dept or "Unknown"
        self.skills: set = set(skills or [])
        self.technologies: set = set()
        self.projects: List[Dict[str, Any]] = []
        self.experience: List[Dict[str, Any]] = []
        self.education: List[str] = []
        self.certifications: List[str] = []
        self.achievements: List[str] = []
        self.career_objective: str = ""
        self.raw_text = raw_text or ""
        self.has_resume = bool(
            raw_text and raw_text.strip()
            and raw_text.strip() not in ("No resume uploaded yet.", "No resume uploaded.")
        )
        if self.has_resume:
            self._parse_resume()

    # ------------------------------------------------------------------
    def _parse_resume(self):
        """Full structured extraction from resume text (Issue 2)."""
        text = self.raw_text
        text_lower = text.lower()

        # Skills & Technologies from keyword scan
        for t in TECH_KEYWORDS:
            if re.search(r"\b" + re.escape(t.lower()) + r"\b", text_lower):
                self.technologies.add(t)
                self.skills.add(t)
        for s in SKILL_KEYWORDS:
            if re.search(r"\b" + re.escape(s.lower()) + r"\b", text_lower):
                self.skills.add(s)

        # Education
        edu_pattern = re.compile(
            r"(B\.?Tech|M\.?Tech|B\.?E|MCA|BCA|B\.?Sc|M\.?Sc|PhD"
            r"|Bachelor|Master|Degree)[^\n]{0,120}", re.IGNORECASE)
        for m in edu_pattern.finditer(text):
            entry = m.group(0).strip()
            if entry not in self.education:
                self.education.append(entry)

        # Career objective
        obj_m = re.search(
            r"(Career Objective|Objective|Goal|Summary)\s*[:\-]?\s*([^\n]{20,300})",
            text, re.IGNORECASE)
        if obj_m:
            self.career_objective = obj_m.group(2).strip()

        # Projects — student-only extraction (labelled sections only, no advice)
        self.projects = _extract_projects_student(text)

        # Certifications
        cert_section = re.search(
            r"Certif[^\n]*\n(.*?)(?=\n[A-Z][A-Z\s]{3,}:|\Z)",
            text, re.IGNORECASE | re.DOTALL)
        if cert_section:
            for line in cert_section.group(1).split("\n"):
                l = re.sub(r"^[-*•\s]+", "", line).strip()
                if 5 < len(l) < 100:
                    self.certifications.append(l)

        # Achievements
        ach_section = re.search(
            r"(Achievement|Award|Honor|Recognition)[^\n]*\n(.*?)(?=\n[A-Z][A-Z\s]{3,}:|\Z)",
            text, re.IGNORECASE | re.DOTALL)
        if ach_section:
            for line in ach_section.group(2).split("\n"):
                l = re.sub(r"^[-*•\s]+", "", line).strip()
                if 5 < len(l) < 150:
                    self.achievements.append(l)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "name": self.name,
            "department": self.department,
            "skills": sorted(self.skills),
            "technologies": sorted(self.technologies),
            "projects": self.projects[:6],
            "experience": self.experience,
            "education": self.education,
            "certifications": self.certifications,
            "achievements": self.achievements,
            "career_objective": self.career_objective,
            "has_resume": self.has_resume,
        }


class AlumniProfile:
    def __init__(self, evidence_id: str, name: str, company: str, role: str,
                 dept: str = "", skills: List[str] = None,
                 projects: List[Dict[str, Any]] = None,
                 raw_text: str = "", source_key: str = "", kwargs: dict = None):
        if kwargs is None:
            kwargs = {}
        self.evidence_id = evidence_id
        self.name = name or "Alumni Senior"
        self.company = company or "Placed Company"
        self.role = role or "Software Engineer"
        self.department = dept or "CS"
        self.designation = kwargs.get("designation", self.role)
        self.experience: List[Dict] = kwargs.get("experience", [])
        self.skills: set = set(skills or [])
        self.technologies: set = set(kwargs.get("technologies", []))
        self.projects: List[Dict] = projects or []
        self.certifications: List[str] = kwargs.get("certifications", [])
        self.achievements: List[str] = kwargs.get("achievements", [])
        self.education: List[str] = kwargs.get("education", [])
        self.career_path: List[str] = kwargs.get("career_path", [])
        self.summary: str = kwargs.get("summary", "")
        self.confidence: float = kwargs.get("confidence", 0.0)
        self.raw_text = raw_text or ""
        self.source_key = source_key or evidence_id  # for grouping by source doc
        self.source_document = kwargs.get("source_document", "")

        if self.raw_text and not self.technologies:
            self._parse_text_skills_and_tech()

    def _parse_text_skills_and_tech(self):
        text_lower = self.raw_text.lower()
        for t in TECH_KEYWORDS:
            if re.search(r"\b" + re.escape(t.lower()) + r"\b", text_lower):
                self.technologies.add(t)
        for s in SKILL_KEYWORDS:
            if re.search(r"\b" + re.escape(s.lower()) + r"\b", text_lower):
                self.skills.add(s)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "name": self.name,
            "company": self.company,
            "role": self.role,
            "designation": self.designation,
            "department": self.department,
            "experience": self.experience,
            "skills": sorted(self.skills),
            "technologies": sorted(self.technologies),
            "projects": self.projects,
            "certifications": self.certifications,
            "achievements": self.achievements,
            "education": self.education,
            "career_path": self.career_path,
            "summary": self.summary,
            "source_key": self.source_key,
        }


class InterviewExperience:
    def __init__(self, evidence_id: str, company: str, role: str,
                 difficulty: str, author: str = "",
                 rounds: List[str] = None, topics: List[str] = None,
                 faqs: List[str] = None, prep_tips: List[str] = None,
                 raw_text: str = ""):
        self.evidence_id = evidence_id
        self.company = company or "Interviewed Company"
        self.role = role or "Software Engineer"
        self.difficulty = difficulty or "Medium"
        self.author = author or "Senior"
        self.rounds: List[str] = rounds or []
        self.topics: List[str] = topics or []
        self.faqs: List[str] = faqs or []
        self.prep_tips: List[str] = prep_tips or []
        self.raw_text = raw_text or ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "company": self.company,
            "role": self.role,
            "difficulty": self.difficulty,
            "author": self.author,
            "rounds": self.rounds,
            "topics": self.topics,
            "faqs": self.faqs,
            "prep_tips": self.prep_tips,
        }


class PlacementMaterial:
    def __init__(self, evidence_id: str, title: str,
                 doc_type: str = "", raw_text: str = ""):
        self.evidence_id = evidence_id
        self.title = title or "Placement Guide"
        self.doc_type = doc_type or "Material"
        self.raw_text = raw_text or ""


# ---------------------------------------------------------------------------
# Project Extraction Helper (shared by Student + Alumni)
# ---------------------------------------------------------------------------

def _is_project_block(block: str, title: str) -> bool:
    """
    Guard: return True only if this block is a real project, not advice (Issues 3 & 4).
    A real project must contain at least one technology keyword OR an action verb
    indicating actual implementation work.
    """
    title_lower = title.lower()

    # Reject if title matches an advice/section marker
    for marker in ADVICE_SECTION_MARKERS:
        if marker in title_lower:
            return False

    # Reject if title is itself a section heading
    if title_lower in INVALID_ALUMNI_NAMES:
        return False

    # Reject advice-style openers (e.g. "For ML roles prepare...")
    advice_openers = (
        r"^(for|to|how|prepare|study|learn|focus|understand|revise|practice|"
        r"master|improve|develop|strengthen|build your|tips for|advice |guidance)"
    )
    if re.match(advice_openers, title_lower):
        return False

    # Must have at least one detected technology OR an implementation verb
    block_lower = block.lower()
    has_tech = any(
        re.search(r"\b" + re.escape(t.lower()) + r"\b", block_lower)
        for t in TECH_KEYWORDS
    )
    impl_verbs = (
        "built", "developed", "implemented", "created", "designed",
        "deployed", "engineered", "trained", "fine-tuned", "integrated",
        "automated", "optimized", "developed", "architected", "wrote",
    )
    has_action = any(v in block_lower for v in impl_verbs)

    return has_tech or has_action


def _extract_projects_student(text: str) -> List[Dict[str, Any]]:
    """
    Extract structured project dicts ONLY from labelled project sections in resume text.
    Student-specific: ignores placement advice, career goals, interview tips (Issue 3).
    Returns: [{title, description, technologies, domain, impact}]
    """
    projects: List[Dict[str, Any]] = []

    # Strictly look for a Projects section — must be labelled
    sec_match = re.search(
        r"(?:^|\n)\s*(?:##\s*|###\s*|\*\*)?(?:PROJECTS?|Personal Projects?|Academic Projects?"
        r"|Professional Projects?|Hackathon(?:s)?|Key Projects?)"
        r"(?:\*\*)?\s*(?:[:\-])?\s*\n(.*?)(?=\n\s*(?:##|###|\*\*[A-Z]{2,}|EXPERIENCE"
        r"|EDUCATION|SKILLS|CERTIFICATIONS|WORK|INTERNSHIP|PLACEMENT|CAREER|INTERVIEW)|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )

    if not sec_match:
        return []  # Student: never fall back to full-text scan (avoids advice leakage)

    return _parse_project_section(sec_match.group(1))


def _extract_projects_alumni(text: str) -> List[Dict[str, Any]]:
    """
    Extract structured project dicts from alumni resume/profile text (Issue 4).
    Falls back to full-text scan if no Projects section found, but guards against advice.
    Returns: [{title, description, technologies, domain, impact}]
    """
    # Try labelled section first
    sec_match = re.search(
        r"(?:^|\n)\s*(?:##\s*|###\s*|\*\*)?(?:PROJECTS?|Personal Projects?|Academic Projects?"
        r"|Professional Projects?|Hackathon(?:s)?|Key Projects?)"
        r"(?:\*\*)?\s*(?:[:\-])?\s*\n(.*?)(?=\n\s*(?:##|###|\*\*[A-Z]{2,}|EXPERIENCE"
        r"|EDUCATION|SKILLS|CERTIFICATIONS|WORK|INTERNSHIP|PLACEMENT|CAREER|INTERVIEW)|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )

    if sec_match:
        return _parse_project_section(sec_match.group(1))

    # Fallback: look for any 'project' mention block
    fb_match = re.search(
        r"project[s]?[^\n]*\n(.*?)(?=\n\s*(?:[A-Z]{4,}|\*\*[A-Z])|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )
    return _parse_project_section(fb_match.group(1)) if fb_match else []


# Keep old name as alias for backward compat
_extract_projects_structured = _extract_projects_alumni


def _parse_project_section(section_text: str) -> List[Dict[str, Any]]:
    """Parse a project section string into structured dicts with advice filtering."""
    projects: List[Dict[str, Any]] = []

    raw_blocks = re.split(
        r"\n(?=\s*(?:[-*•]?\s*)?(?:\d+[.)]\s+)?[A-Z][^\n]{3,80}(?:\s*\||\s*[-–—]|\s*:|\s*\())",
        section_text
    )

    for block in raw_blocks:
        block = block.strip()
        if not block or len(block) < 10:
            continue

        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        raw_title = re.sub(r"^[-*•\d.)\s]+", "", lines[0]).split("|")[0].split("–")[0].strip()
        if len(raw_title) < 4 or len(raw_title) > 100:
            continue
        # Reject known section headings
        if raw_title.lower() in INVALID_ALUMNI_NAMES:
            continue
        if re.match(r"^(experience|education|skills|certifications|achievements|placement|career|interview)\b", raw_title, re.I):
            continue

        # Guard: must be a real project, not advice (Issues 3 & 4)
        if not _is_project_block(block, raw_title):
            continue

        description = " ".join(lines[1:4])[:300]
        block_lower = block.lower()
        techs = [t for t in TECH_KEYWORDS
                 if re.search(r"\b" + re.escape(t.lower()) + r"\b", block_lower)]
        domain = _classify_project_domain(block_lower, techs)
        impact_m = re.search(
            r"(achiev|result|improv|reduc|increas|deployed|used by|accuracy)[^\n.]{0,120}",
            block, re.IGNORECASE)
        impact = impact_m.group(0).strip() if impact_m else ""

        projects.append({
            "title": raw_title,
            "description": description,
            "technologies": techs[:8],
            "domain": domain,
            "impact": impact,
        })

        if len(projects) >= 6:
            break

    return projects



def _classify_project_domain(text_lower: str, techs: List[str]) -> str:
    """Classify project domain from text + detected technologies."""
    ml_terms = {"machine learning", "deep learning", "neural", "nlp", "computer vision",
                 "llm", "gpt", "bert", "transformer", "stable diffusion", "generative"}
    web_terms = {"react", "node", "express", "django", "flask", "fastapi", "html", "css", "rest"}
    data_terms = {"data analysis", "pandas", "tableau", "power bi", "sql", "spark", "hadoop"}
    cloud_terms = {"aws", "azure", "gcp", "docker", "kubernetes", "devops"}

    tl = set(t.lower() for t in techs)
    if any(t in text_lower for t in ml_terms) or tl & {"pytorch", "tensorflow", "scikit-learn"}:
        return "Machine Learning / AI"
    if any(t in text_lower for t in web_terms) or tl & {"react", "node.js", "django", "fastapi"}:
        return "Web Development"
    if any(t in text_lower for t in data_terms) or tl & {"pandas", "tableau", "spark"}:
        return "Data Analytics"
    if any(t in text_lower for t in cloud_terms) or tl & {"docker", "kubernetes", "aws"}:
        return "Cloud / DevOps"
    return "General Software"


# ---------------------------------------------------------------------------
# Company Extraction (Issue 2) — priority chain
# ---------------------------------------------------------------------------

def _extract_company_from_chunk(chunk: str, metadata: dict) -> Optional[str]:
    """
    Extract company/employer using a 5-priority deterministic chain (Issue 2).
    Priority: metadata → Current Employer → Company → Employer → experience section → title pipe
    """
    JUNK_COMPANIES = {"unknown", "unknown company", "placed company", "n/a", "none", ""}

    # Priority 0: metadata
    for field in ("company", "employer", "current_employer"):
        val = str(metadata.get(field, "")).strip()
        if val and val.lower() not in JUNK_COMPANIES:
            return val

    # Priority 1: "Current Employer: <name>"
    m = re.search(r"Current\s+Employer\s*[:\-]\s*([^\n\|,]{2,50})", chunk, re.IGNORECASE)
    if m:
        val = m.group(1).strip().rstrip(".")
        if val.lower() not in JUNK_COMPANIES:
            return val

    # Priority 2: "Company: <name>" or "**Company**: <name>"
    m = re.search(r"\*{0,2}Company\*{0,2}\s*[:\-]\s*([^\n\|,]{2,50})", chunk, re.IGNORECASE)
    if m:
        val = m.group(1).strip().rstrip(".")
        if val.lower() not in JUNK_COMPANIES and not val.isspace():
            return val

    # Priority 3: "Employer: <name>"
    m = re.search(r"\bEmployer\b\s*[:\-]\s*([^\n\|,]{2,50})", chunk, re.IGNORECASE)
    if m:
        val = m.group(1).strip().rstrip(".")
        if val.lower() not in JUNK_COMPANIES:
            return val

    # Priority 4: Experience section — "Role | Company", "Role @ Company", "Role at Company"
    exp_patterns = [
        r"(?:Software|Senior|Junior|Lead|Principal|Staff|ML|AI|Data)[^\n]{0,30}"
        r"(?:\||@|\bat\b)\s*([A-Z][A-Za-z\s&.]{1,40})",
        r"([A-Z][A-Za-z\s&.]{2,35})(?:\s*\|\s*|\s+-\s+)(?:Software|Senior|ML|Data|AI|Full)[^\n]{0,40}",
    ]
    for pat in exp_patterns:
        m = re.search(pat, chunk)
        if m:
            val = m.group(1).strip().rstrip(".")
            if val and val.lower() not in JUNK_COMPANIES and not _is_valid_person_name(val):
                return val

    # Priority 5: Title pipe format  e.g. "Meera Krishnan | Adobe | ML Engineer"
    pipe_m = re.search(r"\b([A-Z][A-Za-z\s&.]{2,30})\s*\|\s*(?:ML|AI|Data|Software|Senior)[^\n]{0,40}", chunk)
    if pipe_m:
        val = pipe_m.group(1).strip()
        if val.lower() not in JUNK_COMPANIES and not _is_valid_person_name(val):
            return val

    return None


# ---------------------------------------------------------------------------
# Alumni Pre-Generation Validation (Issues 6, 8, 9)
# ---------------------------------------------------------------------------

def _validate_alumni_profile(prof: "AlumniProfile", source: str) -> Tuple[bool, str]:
    """
    Return (is_valid, rejection_reason).
    A valid AlumniProfile must have a valid person name, a company, a role,
    AND at least one of: projects, skills, technologies (Issue 8).
    """
    reasons = []

    if not _is_valid_person_name(prof.name):
        reasons.append(f"Invalid name: '{prof.name}'")

    junk_cos = {"unknown company", "placed company", "unknown", ""}
    if not prof.company or prof.company.lower() in junk_cos:
        reasons.append(f"Missing/invalid company: '{prof.company}'")

    junk_roles = {"software engineer", "unknown", ""}
    # Allow common roles but require at least something
    if not prof.role:
        reasons.append("Missing role")

    has_content = bool(
        prof.projects or
        (prof.skills and len(prof.skills) > 0) or
        (prof.technologies and len(prof.technologies) > 0)
    )
    if not has_content:
        reasons.append("No projects, skills, or technologies found")

    return len(reasons) == 0, "; ".join(reasons)


def _print_alumni_validation_report(results: List[Tuple["AlumniProfile", str, bool, str]]):
    """Print the Alumni Validation Report (Issue 9)."""
    print("\n" + "=" * 50)
    print("Alumni Validation Report")
    print("=" * 50)
    for prof, source, valid, reason in results:
        status = "✅ ACCEPTED" if valid else "❌ REJECTED"
        print(f"\nSource        : {source}")
        print(f"Extracted Name: {prof.name}")
        print(f"Valid Name    : {'Yes' if _is_valid_person_name(prof.name) else 'No'}")
        print(f"Company       : {prof.company}")
        print(f"Role          : {prof.role}")
        print(f"Projects      : {len(prof.projects)}")
        print(f"Skills        : {len(prof.skills)}")
        print(f"Technologies  : {len(prof.technologies)}")
        print(f"Status        : {status}")
        if not valid:
            print(f"Reason        : {reason}")
    rejected = [(p.name, r, reason) for p, r, v, reason in results if not v]
    if rejected:
        print("\n--- Rejected Alumni Profiles ---")
        for name, src, reason in rejected:
            print(f"  {name!r} (src: {src}) → {reason}")
    print("=" * 50 + "\n")



# ---------------------------------------------------------------------------
# Alumni Grouping (Issue 3)
# ---------------------------------------------------------------------------

def _get_source_key(chunk_text: str, metadata: dict) -> str:
    """Derive stable grouping key prioritizing original PDF source fields."""
    for field in ("source_file", "filename", "source", "document_id"):
        val = metadata.get(field, "")
        if val and str(val).strip():
            # Clean and normalize the filename/identity as grouping key
            key = str(val).strip().lower()
            if "/" in key or "\\" in key:
                import os
                key = os.path.basename(key)
            return key
            
    # Fallback to first 80 chars of unique text fingerprint
    return chunk_text[:80].strip().lower()


def _group_alumni_chunks(chunks: List[Union[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """
    Group raw retrieval chunks by source PDF document.
    Reconstructs metadata from serialized headers and prints chunk/group/extraction details.
    """
    import json
    
    # 1. Parse individual chunks, collect metadata, print retrieved chunk info
    parsed_chunks = []
    
    for i, chunk in enumerate(chunks, 1):
        meta = {}
        text = ""
        
        if isinstance(chunk, str):
            # Parse the serialized format
            text = chunk
            if "Metadata JSON: " in chunk:
                try:
                    for line in chunk.split("\n"):
                        if line.startswith("Metadata JSON: "):
                            meta = json.loads(line[len("Metadata JSON: "):].strip())
                            break
                except Exception as e:
                    print(f"Error parsing metadata JSON from chunk: {e}")
            
            # Clean up/extract actual text content
            if "---CONTENT---" in chunk:
                text = chunk.split("---CONTENT---", 1)[1].strip()
            else:
                text = chunk.strip()
        else:
            meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
            text = chunk.get("text", chunk.get("document", str(chunk))) if isinstance(chunk, dict) else str(chunk)
            
        parsed_chunks.append({"text": text, "metadata": meta})
        
        # Print Chunk Details as requested
        print("--------------------------------------------------")
        print("Retrieved Chunk")
        print(f"- source_file: {meta.get('source_file', '')}")
        print(f"- filename: {meta.get('filename', '')}")
        print(f"- document_id: {meta.get('document_id', '')}")
        print(f"- collection: {meta.get('collection', '')}")
        print(f"- section: {meta.get('section', '')}")
        print(f"- chunk index: {meta.get('chunk_index', '')}")
        print("--------------------------------------------------")

    # 2. Group chunks by original PDF document grouping key
    groups: Dict[str, Dict[str, Any]] = {}
    chunk_counts: Dict[str, int] = {}
    
    for item in parsed_chunks:
        text = item["text"]
        meta = item["metadata"]
        
        key = _get_source_key(text, meta)
        
        if key not in groups:
            groups[key] = {"text": text, "metadata": meta}
            chunk_counts[key] = 1
        else:
            groups[key]["text"] += "\n\n" + text
            chunk_counts[key] += 1
            
    # 3. Print Grouped Resume details as requested
    for key, group in groups.items():
        print("--------------------------------------------------")
        print("Grouped Resume")
        print(f"- grouping key: {key}")
        print(f"- chunks merged: {chunk_counts[key]}")
        print(f"- merged text length: {len(group['text'])}")
        print("--------------------------------------------------")
        
    return groups



# ---------------------------------------------------------------------------
# Interview Extraction (Issue 5)
# ---------------------------------------------------------------------------

def _extract_interview_fields(chunk: str, metadata: dict) -> Dict[str, Any]:
    """Deterministic interview field extraction; LLM fallback if critical fields missing."""
    result = {
        "company": None, "role": None, "difficulty": "Medium",
        "author": None, "rounds": [], "topics": [], "faqs": [], "prep_tips": [],
    }

    # Company
    comp_patterns = [
        r"Interview Experience\s*[—\-:]\s*([^\(\n\|]{2,40})",
        r"\*\*Company\*\*\s*[:\-]\s*([^\|\n]{2,40})",
        r"company\s*[:\-]\s*([^\|\n,]{2,40})",
    ]
    for pat in comp_patterns:
        m = re.search(pat, chunk, re.IGNORECASE)
        if m:
            result["company"] = m.group(1).strip()
            break

    # Role
    role_m = re.search(r"\*\*Role\*\*\s*[:\-]\s*([^\|\n]{2,40})|role\s*[:\-]\s*([^\|\n,]{2,40})", chunk, re.IGNORECASE)
    if role_m:
        result["role"] = (role_m.group(1) or role_m.group(2)).strip()

    # Difficulty
    diff_m = re.search(r"\*\*Difficulty\*\*\s*[:\-]\s*([^\|\n]{2,20})|difficulty\s*[:\-]\s*([^\|\n]{2,20})", chunk, re.IGNORECASE)
    if diff_m:
        result["difficulty"] = (diff_m.group(1) or diff_m.group(2)).strip()

    # Rounds
    round_matches = re.findall(
        r"(Online Assessment|OA|Technical\s*Round\s*\d*|Coding\s*Round|HR\s*Round|Bar\s*Raiser|Managerial\s*Round|System\s*Design\s*Round|Behavioural\s*Round)",
        chunk, re.IGNORECASE)
    result["rounds"] = list(dict.fromkeys(r.strip().title() for r in round_matches))

    # Topics
    topic_keywords = [
        "Data Structures", "Algorithms", "Dynamic Programming", "System Design",
        "Object Oriented", "Database", "SQL", "Operating Systems", "Networking",
        "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
        "Behavioural", "Leadership", "Problem Solving",
    ]
    text_lower = chunk.lower()
    result["topics"] = [t for t in topic_keywords if t.lower() in text_lower]

    # FAQs: lines with '?' or starting with Q:
    faq_lines = re.findall(r"(?:Q\s*\d*\s*[:\-]|•\s*).{10,200}\?", chunk)
    result["faqs"] = faq_lines[:5]

    # Prep tips: lines after "Tips:" or "Preparation:" header
    tips_m = re.search(r"(?:Tips?|Preparation|Advice)\s*[:\-]\s*\n?(.*?)(?=\n\n|\Z)", chunk, re.IGNORECASE | re.DOTALL)
    if tips_m:
        tip_lines = [re.sub(r"^[-*•\s]+", "", l).strip() for l in tips_m.group(1).split("\n") if l.strip()]
        result["prep_tips"] = [t for t in tip_lines if len(t) > 10][:5]

    # Author
    author_m = re.search(r"\b([A-Z][a-z]{1,14}\s+[A-Z][a-z]{1,19})\b", chunk)
    if author_m and _is_valid_person_name(author_m.group(1)):
        result["author"] = author_m.group(1)

    # LLM fallback if critical fields missing
    critical_missing = not result["company"] or not result["rounds"]
    if critical_missing and "interview" in chunk.lower():
        print(f"🔍 [INTERVIEW EXTRACTION] Deterministic incomplete, invoking LLM fallback...")
        llm_data = _llm_extract_interview(chunk)
        if llm_data:
            result["company"] = result["company"] or llm_data.get("company")
            result["role"] = result["role"] or llm_data.get("role")
            result["difficulty"] = result["difficulty"] or llm_data.get("difficulty", "Medium")
            result["rounds"] = result["rounds"] or llm_data.get("rounds", [])
            result["topics"] = result["topics"] or llm_data.get("topics", [])
            result["faqs"] = result["faqs"] or llm_data.get("faqs", [])
            result["prep_tips"] = result["prep_tips"] or llm_data.get("prep_tips", [])

    return result


# ---------------------------------------------------------------------------
# Debug Logging (Issue 12)
# ---------------------------------------------------------------------------

def _print_student_extraction_report(student: "StudentProfile"):
    print("\n" + "=" * 52)
    print("Student Extraction Report")
    print(f"Name           : {student.name}")
    print(f"Department     : {student.department}")
    print(f"Education      : {'; '.join(student.education) if student.education else 'Not found'}")
    print(f"Skills         : {len(student.skills)} — {', '.join(sorted(student.skills)[:10])}")
    print(f"Technologies   : {len(student.technologies)} — {', '.join(sorted(student.technologies)[:10])}")
    print(f"Projects       : {len(student.projects)}")
    for p in student.projects:
        print(f"   • {p['title']} [{p['domain']}] — Tech: {', '.join(p['technologies'][:4])}")
    print(f"Experience     : {len(student.experience)} entries")
    print(f"Certifications : {len(student.certifications)}")
    print(f"Achievements   : {len(student.achievements)}")
    print("=" * 52 + "\n")


def _print_alumni_extraction_report(alumni: "AlumniProfile", source: str):
    print("\n" + "=" * 52)
    print("Alumni Extraction Report")
    print(f"Source         : {source}")
    print(f"Name           : {alumni.name}")
    print(f"Company        : {alumni.company}")
    print(f"Role           : {alumni.role}")
    print(f"Designation    : {alumni.designation}")
    print(f"Education      : {'; '.join(alumni.education[:2]) if alumni.education else 'Not found'}")
    print(f"Experience     : {len(alumni.experience)} entries")
    print(f"Technologies   : {len(alumni.technologies)}")
    print(f"Skills         : {len(alumni.skills)}")
    print(f"Projects       : {len(alumni.projects)}")
    for p in alumni.projects:
        print(f"   • {p.get('title','?')} [{p.get('domain','')}]")
    print(f"Certifications : {len(alumni.certifications)}")
    print(f"Achievements   : {len(alumni.achievements)}")
    print(f"Career Path    : {alumni.career_path}")
    print(f"Confidence     : {alumni.confidence:.2f}")
    print("=" * 52 + "\n")


def _print_interview_extraction_report(iv: "InterviewExperience"):
    print("\n" + "=" * 52)
    print("Interview Extraction Report")
    print(f"Company    : {iv.company}")
    print(f"Role       : {iv.role}")
    print(f"Difficulty : {iv.difficulty}")
    print(f"Rounds     : {iv.rounds or 'Not found'}")
    print(f"Topics     : {iv.topics or 'Not found'}")
    print(f"FAQs       : {len(iv.faqs)} questions found")
    print(f"Prep Tips  : {len(iv.prep_tips)}")
    print("=" * 52 + "\n")


def _print_top_alumni_selected(matches: List[Dict[str, Any]]):
    print("\n" + "=" * 52)
    print("Top Alumni Selected")
    for i, m in enumerate(matches[:5], 1):
        print(f"{i}.")
        print(f"   Name         : {m['alumni_name']}")
        print(f"   Company      : {m['company']}")
        print(f"   Role         : {m['role']}")
        print(f"   Match Score  : {m['match_score']}%")
        bd = m.get("score_breakdown", {})
        print(f"   Breakdown    : Skills={bd.get('skill_overlap_pct',0)}%  "
              f"Tech={bd.get('tech_overlap_pct',0)}%  "
              f"Proj={bd.get('project_similarity_pct',0)}%  "
              f"Edu={bd.get('education_pct',0)}%  "
              f"Exp={bd.get('experience_pct',0)}%")
    print("=" * 52 + "\n")


# ---------------------------------------------------------------------------
# Main: Extract Structured Evidence
# ---------------------------------------------------------------------------

def extract_structured_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
    # ── 1. Student Profile ─────────────────────────────────────────────────
    student_skills_str = state.get("student_skills", "")
    known_skills = [s.strip() for s in student_skills_str.split(",")
                    if s.strip() and s.strip() != "None specified"]
    student = StudentProfile(
        name=state.get("student_name", "Student"),
        dept=state.get("student_dept", "Unknown"),
        skills=known_skills,
        raw_text=state.get("context_resume", ""),
    )
    _print_student_extraction_report(student)

    # ── 2. Alumni Profiles — group chunks by source (Issue 3) ─────────────
    alumni_list: List[AlumniProfile] = []

    # context_alumni may be a plain string of merged chunks; we split here
    raw_alumni_text = state.get("context_alumni", "") + "\n\n" + state.get("context_kb", "")

    # Split into individual chunk strings
    if "### Chunk " in raw_alumni_text:
        raw_chunks_list = ["### Chunk " + c for c in raw_alumni_text.split("### Chunk ") if c.strip()]
    else:
        # Non-chunked: treat each double-newline block as a separate chunk
        raw_chunks_list = [b.strip() for b in raw_alumni_text.split("\n\n") if b.strip()]

    # Group by source document
    groups = _group_alumni_chunks(raw_chunks_list)
    print(f"\n[ALUMNI GROUPING] {len(raw_chunks_list)} chunks → {len(groups)} distinct alumni sources")

    for group_idx, (source_key, group) in enumerate(groups.items(), 1):
        chunk = group["text"]
        meta = group["metadata"]

        if not chunk.strip():
            continue

        # Deterministic name extraction (Issue 1)
        name = _extract_name_deterministic(chunk, meta)

        # Company — 5-priority deterministic chain (Issue 2)
        company = _extract_company_from_chunk(chunk, meta)

        role_m = (re.search(r"\*\*Role\*\*\s*[:\-]\s*([^\|\n]{2,40})", chunk, re.IGNORECASE)
                  or re.search(r"role\s*[:\-]\s*([^\|\n,]{2,40})", chunk, re.IGNORECASE))
        role = role_m.group(1).strip() if role_m else meta.get("role", "")

        # Determine if LLM extraction is needed
        needs_llm = (
            not _is_valid_person_name(name)
            or not company
            or (not re.search(r"\bproject", chunk, re.IGNORECASE))
        )

        kwargs: Dict[str, Any] = {}
        projects_parsed: List[Dict] = []
        tech_parsed: List[str] = []

        if needs_llm and len(chunk.strip()) > 100:
            print(f"🔍 [ALUMNI EXTRACTION] Incomplete for source '{source_key}'. Invoking LLM...")
            extracted = _llm_extract_alumni_profile(chunk)
            if extracted:
                if not _is_valid_person_name(name):
                    candidate = extracted.get("name", "")
                    name = candidate if _is_valid_person_name(candidate) else name
                company = company or extracted.get("company", "")
                role = role or extracted.get("role", "")
                kwargs["designation"] = extracted.get("designation", "")
                kwargs["experience"] = extracted.get("experience", [])
                kwargs["certifications"] = extracted.get("certifications", [])
                kwargs["achievements"] = extracted.get("achievements", [])
                kwargs["education"] = extracted.get("education", [])
                kwargs["career_path"] = extracted.get("career_path", [])
                kwargs["summary"] = extracted.get("summary", "")
                projects_parsed = extracted.get("projects", [])
                tech_parsed = extracted.get("technologies", [])

        # LLM name-only fallback (Issue 1)
        if not _is_valid_person_name(name) and len(chunk) > 50:
            print(f"🔍 [NAME FALLBACK] Using LLM name extraction for source '{source_key}'")
            name = _llm_extract_name_only(chunk) or name

        # Structured project extraction from raw text — alumni-specific (with advice guard)
        if not projects_parsed:
            projects_parsed = _extract_projects_alumni(chunk)

        # Metadata-from-source company/role if still empty
        company = company or meta.get("company", "")
        role = role or meta.get("role", "")

        if name or company or role or "resume" in chunk.lower():
            kwargs["technologies"] = tech_parsed  # Issue 5: alumni tech only from alumni chunk
            kwargs["source_document"] = source_key
            prof = AlumniProfile(
                evidence_id=f"alumni_ev_{group_idx}",
                name=name or "Unknown Alumni",
                company=company or "Unknown Company",
                role=role or "Software Engineer",
                projects=projects_parsed,
                raw_text=chunk.strip(),
                source_key=source_key,
                kwargs=kwargs,
            )
            prof.confidence = (
                0.95 if (_is_valid_person_name(prof.name) and prof.company not in ("Unknown Company", "Placed Company"))
                else 0.6
            )
            _print_alumni_extraction_report(prof, source_key)
            alumni_list.append(prof)

    # ── 2b. Alumni Validation Gate (Issues 6, 8, 9) ────────────────────────
    validation_results: List[Tuple] = []
    validated_alumni: List[AlumniProfile] = []
    for prof in alumni_list:
        valid, reason = _validate_alumni_profile(prof, prof.source_key)
        validation_results.append((prof, prof.source_key, valid, reason))
        if valid:
            validated_alumni.append(prof)
            
        # Print Debug Log Block as requested
        status_str = "valid" if valid else f"invalid ({reason})"
        print("--------------------------------------------------")
        print("Extracted Alumni")
        print(f"- name: {prof.name}")
        print(f"- company: {prof.company}")
        print(f"- role: {prof.role}")
        print(f"- validation status: {status_str}")
        print("--------------------------------------------------")
        
        # Second print block as requested in "TASK" section
        print("--------------------------------------------------")
        print(f"Extracted Name: {prof.name}")
        print(f"Company: {prof.company}")
        print(f"Role: {prof.role}")
        print(f"Projects: {prof.projects}")
        print(f"Skills: {prof.skills}")
        print(f"Technologies: {prof.technologies}")
        print(f"Validation Result: {'Passed' if valid else 'Failed'}")
        print("--------------------------------------------------")

    _print_alumni_validation_report(validation_results)
    print(f"[VALIDATION] {len(validated_alumni)}/{len(alumni_list)} alumni passed validation")
    alumni_list = validated_alumni


    # ── 3. Interview Experiences (Issue 5) ─────────────────────────────────
    interview_list: List[InterviewExperience] = []
    interview_raw = state.get("context_interviews", "")
    if "### Chunk " in interview_raw:
        i_chunks = ["### Chunk " + c for c in interview_raw.split("### Chunk ") if c.strip()]
    else:
        i_chunks = [b.strip() for b in interview_raw.split("\n\n") if b.strip()]

    for idx, chunk in enumerate(i_chunks, 1):
        if not chunk.strip():
            continue
        if not ("interview" in chunk.lower() or "round" in chunk.lower() or "company" in chunk.lower()):
            continue
        fields = _extract_interview_fields(chunk, {})
        iv = InterviewExperience(
            evidence_id=f"interview_ev_{idx}",
            company=fields["company"] or "Unknown Company",
            role=fields["role"] or "Software Engineer",
            difficulty=fields["difficulty"],
            author=fields["author"] or "Senior",
            rounds=fields["rounds"],
            topics=fields["topics"],
            faqs=fields["faqs"],
            prep_tips=fields["prep_tips"],
            raw_text=chunk.strip(),
        )
        _print_interview_extraction_report(iv)
        interview_list.append(iv)

    # ── 4. Placement Materials ──────────────────────────────────────────────
    placement_list: List[PlacementMaterial] = []
    placement_raw = state.get("context_placement", "")
    p_chunks = placement_raw.split("### Chunk ") if "### Chunk " in placement_raw else [placement_raw]
    for idx, chunk in enumerate(p_chunks, 1):
        if not chunk.strip():
            continue
        title_m = re.search(r"### Chunk \d+:\s*([^\n]+)", chunk)
        title = title_m.group(1).strip() if title_m else "Placement Resource"
        placement_list.append(PlacementMaterial(
            evidence_id=f"placement_ev_{idx}",
            title=title,
            raw_text=chunk.strip(),
        ))

    return {
        "student": student,
        "alumni": alumni_list,
        "interviews": interview_list,
        "placement": placement_list,
    }


# ---------------------------------------------------------------------------
# Match Scoring Engine (Issue 4)
# ---------------------------------------------------------------------------

def compute_deterministic_recommendations(
    student: StudentProfile,
    alumni_list: List[AlumniProfile],
) -> List[Dict[str, Any]]:
    """
    5-factor weighted scoring from config.MATCH_SCORE_WEIGHTS.
    Returns matches sorted by match_score desc; includes score_breakdown and why_selected.
    """
    weights = MATCH_SCORE_WEIGHTS
    matches = []

    for alumni in alumni_list:
        # ── Factor 1: Skill Overlap ──────────────────────────────────────
        all_student_skills = student.skills | student.technologies
        skill_overlap = sorted(all_student_skills & alumni.skills)
        missing_skills = sorted(alumni.skills - all_student_skills)
        skill_overlap_pct = round(
            100 * len(skill_overlap) / max(len(alumni.skills), 1)
        )

        # ── Factor 2: Technology Overlap ────────────────────────────────
        tech_overlap = sorted(student.technologies & alumni.technologies)
        missing_tech = sorted(alumni.technologies - student.technologies)
        tech_overlap_pct = round(
            100 * len(tech_overlap) / max(len(alumni.technologies), 1)
        )

        # ── Factor 3: Project Similarity ────────────────────────────────
        proj_score = _compute_project_similarity(student.projects, alumni.projects)
        proj_pct = round(proj_score * 100)

        # ── Factor 4: Education ─────────────────────────────────────────
        edu_pct = 100 if (student.education and alumni.education) else (50 if (student.education or alumni.education) else 0)

        # ── Factor 5: Experience / Internship ───────────────────────────
        exp_pct = 100 if alumni.experience else 50

        # ── Weighted Final Score ─────────────────────────────────────────
        raw_score = (
            weights["skills"]       * skill_overlap_pct +
            weights["technologies"] * tech_overlap_pct +
            weights["projects"]     * proj_pct +
            weights["education"]    * edu_pct +
            weights["experience"]   * exp_pct
        )
        match_score = round(min(raw_score, 100.0), 1)

        # Confidence
        has_name = _is_valid_person_name(alumni.name)
        has_company = alumni.company not in ("Placed Company", "Unknown Company")
        ev_richness = round((1.0 if has_name else 0.6) * (1.0 if has_company else 0.6) * 100, 1)
        overall_conf = round(match_score * 0.6 + ev_richness * 0.4, 1)
        confidence_level = (
            "High" if overall_conf >= CONFIDENCE_HIGH_THRESHOLD else
            ("Medium" if overall_conf >= CONFIDENCE_MEDIUM_THRESHOLD else "Low")
        )

        # ── Why Selected explanation ─────────────────────────────────────
        why_parts = []
        if skill_overlap:
            why_parts.append(f"Shared skills: {', '.join(skill_overlap[:5])}")
        if tech_overlap:
            why_parts.append(f"Shared technologies: {', '.join(tech_overlap[:5])}")
        if proj_pct > 0:
            why_parts.append(f"Similar project domain ({proj_pct}% overlap)")
        if not why_parts:
            why_parts.append("Broad domain alignment based on retrieved evidence")
        why_selected = "; ".join(why_parts)

        matches.append({
            "evidence_id": alumni.evidence_id,
            "alumni_name": alumni.name,
            "company": alumni.company,
            "role": alumni.role,
            "designation": getattr(alumni, "designation", alumni.role),
            "experience": getattr(alumni, "experience", []),
            "projects": getattr(alumni, "projects", []),
            "technologies": sorted(list(alumni.technologies)),
            "skills": sorted(list(alumni.skills)),
            "certifications": getattr(alumni, "certifications", []),
            "achievements": getattr(alumni, "achievements", []),
            "education": getattr(alumni, "education", []),
            "career_path": getattr(alumni, "career_path", []),
            "summary": getattr(alumni, "summary", ""),
            "matching_skills": skill_overlap,
            "missing_skills": missing_skills,
            "tech_overlap": tech_overlap,
            "missing_tech": missing_tech,
            "matching_projects": _build_project_comparisons(student.projects, alumni.projects),
            "match_score": match_score,
            "score_breakdown": {
                "skill_overlap_pct": skill_overlap_pct,
                "tech_overlap_pct": tech_overlap_pct,
                "project_similarity_pct": proj_pct,
                "education_pct": edu_pct,
                "experience_pct": exp_pct,
            },
            "confidence_score": overall_conf,
            "confidence_level": confidence_level,
            "evidence_richness": ev_richness,
            "why_selected": why_selected,
            "raw_text": alumni.raw_text,
        })

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    _print_top_alumni_selected(matches)
    return matches


# ---------------------------------------------------------------------------
# Project Comparison Helpers (Issue 8)
# ---------------------------------------------------------------------------

def _compute_project_similarity(
    student_projects: List[Dict],
    alumni_projects: List[Dict],
) -> float:
    """Technology + domain + keyword overlap score (0.0–1.0)."""
    if not student_projects or not alumni_projects:
        return 0.3  # partial credit when either side is empty

    total = 0.0
    comparisons = 0
    for sp in student_projects:
        s_techs = set(t.lower() for t in sp.get("technologies", []))
        s_domain = sp.get("domain", "").lower()
        s_words = set(re.sub(r"[^\w\s]", "", sp.get("title", "") + " " + sp.get("description", "")).lower().split())

        best = 0.0
        for ap in alumni_projects:
            a_techs = set(t.lower() for t in ap.get("technologies", []))
            a_domain = ap.get("domain", "").lower()
            a_words = set(re.sub(r"[^\w\s]", "", ap.get("title", "") + " " + ap.get("description", "")).lower().split())

            tech_sim = len(s_techs & a_techs) / max(len(s_techs | a_techs), 1)
            domain_sim = 1.0 if (s_domain and s_domain == a_domain) else 0.0
            kw_sim = len(s_words & a_words) / max(len(s_words | a_words), 1)
            score = 0.5 * tech_sim + 0.3 * domain_sim + 0.2 * kw_sim
            best = max(best, score)

        total += best
        comparisons += 1

    return total / comparisons if comparisons else 0.0


def _build_project_comparisons(
    student_projects: List[Dict],
    alumni_projects: List[Dict],
) -> List[Dict[str, Any]]:
    """Build explicit student↔alumni project pair comparisons (Issue 8)."""
    result = []
    for sp in student_projects:
        s_techs = set(t.lower() for t in sp.get("technologies", []))
        best_score = -1.0
        best_ap = None
        for ap in alumni_projects:
            a_techs = set(t.lower() for t in ap.get("technologies", []))
            combined = len(s_techs & a_techs) / max(len(s_techs | a_techs), 1)
            if combined > best_score:
                best_score = combined
                best_ap = ap
        if best_ap:
            a_techs = set(t.lower() for t in best_ap.get("technologies", []))
            result.append({
                "student_project": sp.get("title", ""),
                "student_techs": sp.get("technologies", []),
                "student_domain": sp.get("domain", ""),
                "alumni_project": best_ap.get("title", ""),
                "alumni_techs": best_ap.get("technologies", []),
                "alumni_domain": best_ap.get("domain", ""),
                "shared_tech": sorted(s_techs & a_techs),
                "missing_tech": sorted(a_techs - s_techs),
                "similarity_pct": round(best_score * 100),
            })
    return result


# ---------------------------------------------------------------------------
# Evidence Aggregation (Issue 7)
# ---------------------------------------------------------------------------

def aggregate_alumni_evidence(
    alumni_list: List[AlumniProfile],
    top_n: int = None,
) -> Dict[str, Any]:
    """
    Aggregate patterns across Top-N alumni profiles (Issue 7).
    Returns common skills, technologies, project themes, companies, career paths.
    """
    if top_n:
        alumni_list = alumni_list[:top_n]
    if not alumni_list:
        return {}

    skill_counter: Counter = Counter()
    tech_counter: Counter = Counter()
    company_counter: Counter = Counter()
    career_counter: Counter = Counter()
    domain_counter: Counter = Counter()
    interview_topic_counter: Counter = Counter()

    for a in alumni_list:
        for s in a.skills:
            skill_counter[s] += 1
        for t in a.technologies:
            tech_counter[t] += 1
        if a.company and a.company not in ("Unknown Company", "Placed Company"):
            company_counter[a.company] += 1
        for cp in a.career_path:
            career_counter[cp] += 1
        for p in a.projects:
            d = p.get("domain", "")
            if d:
                domain_counter[d] += 1

    threshold = max(1, len(alumni_list) // 2)  # appears in at least half

    return {
        "common_skills": [s for s, c in skill_counter.most_common(15) if c >= threshold],
        "common_technologies": [t for t, c in tech_counter.most_common(15) if c >= threshold],
        "all_skills_ranked": skill_counter.most_common(20),
        "all_tech_ranked": tech_counter.most_common(20),
        "frequent_companies": [co for co, c in company_counter.most_common(5)],
        "shared_career_paths": [cp for cp, c in career_counter.most_common(5) if c > 1],
        "common_project_domains": [d for d, c in domain_counter.most_common(5)],
        "alumni_count": len(alumni_list),
    }
