import re
import logging
import time
import threading
from typing import Dict, List, Any

# Configure logging
logger = logging.getLogger("ResumeParser")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

# ---------------------------------------------------------------------------
# Keywords & Taxonomy
# ---------------------------------------------------------------------------

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

# Section headers mapping (variations -> standardized section name)
SECTION_CANDIDATES = {
    "projects": ["academic projects", "personal projects", "key projects", "projects", "project", "hackathons", "hackathon"],
    "achievements": ["awards & achievements", "awards and achievements", "achievements", "achievement", "awards", "honors", "honor"],
    "activities": ["extracurricular activities", "co-curricular activities", "extracurriculars", "activities", "activity", "leadership", "position of responsibility", "positions of responsibility"],
    "certifications": ["certifications", "certification", "certificates", "certificate"],
    "skills": ["technical skills", "skills & technologies", "skills and technologies", "skills", "skill"],
    "coding_profiles": ["coding profiles", "profiles", "competitive programming"],
    "objective": ["career objective", "professional summary", "summary", "objective", "career goal", "goal"],
    "education": ["education", "academic background", "academic profile"],
    "experience": ["experience", "work experience", "professional experience", "internships", "internship"]
}

# Primary headers that shouldn't be ignored even if preceded by lowercase words
PRIMARY_HEADERS = {
    "education", "skills", "projects", "achievements", "activities", 
    "certifications", "coding profiles", "objective", "experience", "work experience",
    "academic projects", "personal projects", "awards & achievements", "awards and achievements"
}

# Standardized section mapping
HEADER_MAPPING = {}
for standard_key, cands in SECTION_CANDIDATES.items():
    for cand in cands:
        HEADER_MAPPING[cand] = standard_key

# Display names for logging report
SECTION_DISPLAY_NAMES = {
    "education": "Education",
    "skills": "Skills",
    "projects": "Projects",
    "achievements": "Achievements",
    "activities": "Activities",
    "certifications": "Certifications",
    "coding_profiles": "Coding Profiles",
    "objective": "Objective",
    "experience": "Experience"
}

# ---------------------------------------------------------------------------
# Header Validity Checker
# ---------------------------------------------------------------------------

def _can_be_header_start(text: str, match_start: int, cand: str) -> bool:
    """
    Checks if a match candidate is preceded by characters that allow it to be a standalone header.
    Rejects matches preceded by list commas/colons or inside a sentence (preceded by lowercase words).
    Exception: permits primary headers to bypass lowercase preceding word restriction.
    """
    pre_idx = match_start - 1
    while pre_idx >= 0 and text[pre_idx].isspace():
        pre_idx -= 1
        
    if pre_idx < 0:
        return True # Start of text
        
    # If preceded by list separators or punctuation, it's not a section header
    if text[pre_idx] in [",", ";", ":", "-", "–", "—", "/"]:
        return False
        
    # Extract preceding word
    word_end = pre_idx + 1
    word_start = pre_idx
    while word_start >= 0 and not text[word_start].isspace() and text[word_start] not in [".", "!", "?", "•", "●", "▪", "*", "⁃", "⁌", "⁍", "◦"]:
        word_start -= 1
    word_start += 1
    
    pre_word = text[word_start:word_end]
    pre_word_clean = pre_word.strip(",;:-\"'/\\")
    
    if pre_word_clean.islower() and cand.lower().strip() not in PRIMARY_HEADERS:
        # If it doesn't end a sentence, it's inline text
        if not any(char in pre_word for char in [".", "!", "?"]):
            return False
            
    return True

# ---------------------------------------------------------------------------
# Preprocessor to Restore Missing Newlines
# ---------------------------------------------------------------------------

def _restore_newlines(text: str) -> str:
    """
    Restores missing newlines when text has been chunked/squashed into a single line.
    Looks for bullet points, headers, and project GitHub links to insert newlines.
    """
    if not text:
        return ""
    
    insert_indices = set()
    
    # 1. Find standard bullet points
    for m in re.finditer(r"[•●▪*⁃⁌⁍◦⌢ò♦ü]", text):
        idx = m.start()
        while idx > 0 and text[idx - 1].isspace():
            idx -= 1
        insert_indices.add(idx)
        
    # 2. Find dash bullets followed by capitalized letter: e.g. " - Developed" or " – Developed"
    for m in re.finditer(r"\s+([-–—])\s+([A-Z])", text):
        idx = m.start()
        insert_indices.add(idx)
        
    # 3. Find capitalized section headers (longest patterns first)
    for section_name, cands in SECTION_CANDIDATES.items():
        sorted_cands = sorted(cands, key=len, reverse=True)
        for cand in sorted_cands:
            cand_regex = r"\s+".join(re.escape(word) for word in cand.split())
            pattern = r"\b" + cand_regex + r"\b"
            for m in re.finditer(pattern, text, re.IGNORECASE):
                val = m.group(0)
                is_cap = val.isupper() or all(w[0].isupper() for w in val.split() if w.isalpha())
                if is_cap:
                    if _can_be_header_start(text, m.start(), cand):
                        idx = m.start()
                        while idx > 0 and text[idx - 1].isspace():
                            idx -= 1
                        insert_indices.add(idx)
                    
    # 4. Find GitHub/repo mentions and split preceding project title
    for m in re.finditer(r"(?:https?://)?(?:www\.)?github\.com/[^\s,;|)]+|/github|GitHub\s*Repo|GitHub", text):
        git_start = m.start()
        min_idx = max(0, git_start - 120)
        sub = text[min_idx:git_start]
        delim_match = list(re.finditer(r"[\.•\-–—]", sub))
        if delim_match:
            last_delim_idx = min_idx + delim_match[-1].end()
            while last_delim_idx < git_start and text[last_delim_idx].isspace():
                last_delim_idx += 1
            if last_delim_idx < git_start and text[last_delim_idx].isupper():
                insert_indices.add(last_delim_idx)
                
    chars = list(text)
    for idx in sorted(insert_indices, reverse=True):
        if idx > 0 and idx < len(chars):
            if chars[idx - 1] != '\n':
                chars.insert(idx, '\n')
                
    return "".join(chars)

# ---------------------------------------------------------------------------
# Core Segmenting Helper
# ---------------------------------------------------------------------------

def _segment_resume(text: str) -> Dict[str, str]:
    """
    Finds section boundaries and returns a map of normalized section name to content.
    """
    if not text:
        return {}
    
    # Thread cache check to avoid multiple logs/processings for same resume text
    if getattr(_local_state, "parsing", False) and getattr(_local_state, "text", None) == text:
        if hasattr(_local_state, "segmented_sections"):
            return _local_state.segmented_sections
            
    text = _restore_newlines(text)
    
    # Locate all section headers
    raw_headers = []
    
    for section_key, cands in SECTION_CANDIDATES.items():
        sorted_cands = sorted(cands, key=len, reverse=True)
        for cand in sorted_cands:
            cand_regex = r"\s+".join(re.escape(word) for word in cand.split())
            pattern = r"(?:##\s*|###\s*|\*\*\s*|\[)?\b" + cand_regex + r"\b(?:\s*\*\*\s*|\])?\s*[:\-]?"
            for m in re.finditer(pattern, text, re.IGNORECASE):
                val = m.group(0)
                score = 10
                has_format = any(char in val for char in ["#", "*", "[", "]"])
                
                start_pos = m.start()
                preceded_by_newline = False
                prev_text = text[:start_pos]
                if start_pos == 0 or (start_pos > 0 and text[start_pos - 1] in ["\n", "\r"]):
                    preceded_by_newline = True
                elif len(prev_text) >= 3 and prev_text[-3:].isspace() and "\n" not in prev_text[-3:]:
                    # Handle large spaces acting like newlines in OCR
                    preceded_by_newline = True
                
                if has_format or preceded_by_newline:
                    # Double check it is not false inline match
                    if preceded_by_newline or _can_be_header_start(text, start_pos, cand):
                        score = 100
                else:
                    if _can_be_header_start(text, start_pos, cand):
                        core = re.sub(r"[\#\*\\[\\]\:\-\s\n\r]+", "", val)
                        if core.isupper():
                            score = 80
                        elif all(w[0].isupper() for w in val.split() if w.strip() and w[0].isalpha()):
                            score = 50
                        
                if score >= 50:
                    raw_headers.append({
                        "key": section_key,
                        "start": m.start(),
                        "end": m.end(),
                        "name": m.group(0).strip(),
                        "score": score
                    })
                            
    # Resolve overlaps (keep highest score, then longest string)
    raw_headers.sort(key=lambda x: (x["score"], x["end"] - x["start"]), reverse=True)
    section_headers = []
    for rh in raw_headers:
        overlap = False
        for sh in section_headers:
            if not (rh["end"] <= sh["start"] or rh["start"] >= sh["end"]):
                overlap = True
                break
        if not overlap:
            section_headers.append(rh)
            
    section_headers.sort(key=lambda x: x["start"])
    
    sections = {}
    for idx, sh in enumerate(section_headers):
        start = sh["end"]
        end = section_headers[idx + 1]["start"] if idx + 1 < len(section_headers) else len(text)
        content = text[start:end].strip()
        
        print("\n==================================================")
        print("SECTION")
        print("==================================================")
        print(f"Header:\n{SECTION_DISPLAY_NAMES.get(sh['key'], sh['key'])}")
        print(f"\nStart:\n{start}")
        print(f"\nEnd:\n{end}")
        print(f"\nLength:\n{len(content)}")
        print(f"\nContent:\n\n{content}")
        
        if sh["key"] in sections:
            sections[sh["key"]] += "\n\n" + content
        else:
            sections[sh["key"]] = content
    
    if getattr(_local_state, "parsing", False):
        _local_state.segmented_sections = sections
                
    return sections

# ---------------------------------------------------------------------------
# State Logging helpers for Report Printing and Parsing Cache
# ---------------------------------------------------------------------------

_local_state = threading.local()

def _start_logging(text: str):
    if not getattr(_local_state, "parsing", False) or getattr(_local_state, "text", None) != text:
        _local_state.parsing = True
        _local_state.start_time = time.perf_counter()
        _local_state.text = text
        _local_state.extracted_counts = {}
        _local_state.results = {}
        
        # Batch execute segmenting and all extraction logic once
        _local_state.segmented_sections = _segment_resume(text)
        _local_state.sections_detected = list(_local_state.segmented_sections.keys())
        
        _local_state.results["objective"] = _do_extract_objective(text)
        _local_state.results["projects"] = _do_extract_projects(text)
        _local_state.results["certifications"] = _do_extract_certifications(text)
        _local_state.results["achievements"] = _do_extract_achievements(text)
        _local_state.results["activities"] = _do_extract_activities(text)
        _local_state.results["coding_profiles"] = _do_extract_coding_profiles(text)
        
        # Log the counts
        _local_state.extracted_counts["objective"] = bool(_local_state.results["objective"])
        _local_state.extracted_counts["projects"] = len(_local_state.results["projects"])
        _local_state.extracted_counts["certifications"] = len(_local_state.results["certifications"])
        _local_state.extracted_counts["achievements"] = len(_local_state.results["achievements"])
        _local_state.extracted_counts["activities"] = len(_local_state.results["activities"])
        _local_state.extracted_counts["coding_profiles"] = sum(1 for v in _local_state.results["coding_profiles"].values() if v)
        
        # Print the parser report
        _end_logging_and_print_report()

def _end_logging_and_print_report():
    if getattr(_local_state, "parsing", False):
        _local_state.parsing = False
        duration_ms = (time.perf_counter() - _local_state.start_time) * 1000
        
        print("\n==================================================")
        print("Resume Parser Report")
        print("==================================================")
        print("\nDetected Sections\n")
        
        order = ["education", "skills", "projects", "achievements", "activities", "certifications", "coding_profiles", "objective", "experience"]
        for s in order:
            if s in _local_state.sections_detected:
                print(SECTION_DISPLAY_NAMES[s])
        
        print("\nSection Sizes\n")
        for s in order:
            if s in _local_state.segmented_sections:
                print(f"{SECTION_DISPLAY_NAMES[s]} : {len(_local_state.segmented_sections[s])} chars")
                
        print("\nExtraction Summary\n")
        
        counts = _local_state.extracted_counts
        prj = counts.get("projects", 0)
        ach = counts.get("achievements", 0)
        act = counts.get("activities", 0)
        cert = counts.get("certifications", 0)
        cp = counts.get("coding_profiles", 0)
        obj_val = counts.get("objective", False)
        
        print(f"Projects : {prj}")
        print(f"Achievements : {ach}")
        print(f"Activities : {act}")
        print(f"Certifications : {cert}")
        print(f"Coding Profiles : {cp}")
        print(f"\nExecution Time : {duration_ms:.2f} ms")
        print("==================================================\n")

# ---------------------------------------------------------------------------
# Project Extraction Helpers
# ---------------------------------------------------------------------------

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

def _is_description_bullet(line: str) -> bool:
    cleaned = re.sub(r"^[-–—*•●▪⁃⁌⁍◦⌢ò♦ü\d.)\s]+", "", line).strip()
    if not cleaned:
        return True
    first_word = cleaned.split()[0].lower()
    verbs = ["developed", "built", "implemented", "created", "designed", "automated", "optimized", "engineered", 
             "wrote", "integrated", "orchestrated", "led", "completed", "solved", "served", "coordinated", 
             "leveraged", "managed", "deployed", "assisted", "used", "reduced", "increased", "improved", 
             "achieved", "analyzed", "conducted", "programmed", "worked", "collaborated"]
    return any(first_word.startswith(v) for v in verbs)

def _starts_with_bullet(line: str) -> bool:
    return line.startswith(("•", "●", "▪", "*", "⁃", "⁌", "⁍", "◦", "-", "–", "—", "ò", "", "♦", "ü"))

def _do_extract_projects(text: str) -> List[Dict[str, Any]]:
    sections = _segment_resume(text)
    proj_text = sections.get("projects", "")
    if not proj_text:
        return []
    
    # Split by newlines
    lines = [line.strip() for line in proj_text.split("\n") if line.strip()]
    project_blocks = []
    current_block = []
    
    for line in lines:
        is_new_project = False
        if not current_block:
            is_new_project = True
        else:
            is_desc = _is_description_bullet(line)
            cleaned = re.sub(r"^[-–—*•●▪⁃⁌⁍◦⌢ò♦ü\d.)\s]+", "", line).strip()
            
            if cleaned and not is_desc:
                # Check if current block started with a bullet
                starts_with_bullet_char = _starts_with_bullet(current_block[0])
                if starts_with_bullet_char:
                    # If current block starts with bullet, new project MUST also start with bullet
                    if _starts_with_bullet(line):
                        is_new_project = True
                else:
                    is_new_project = True
        
        if is_new_project and current_block:
            project_blocks.append(current_block)
            current_block = [line]
        else:
            current_block.append(line)
            
    if current_block:
        project_blocks.append(current_block)
        
    projects = []
    for block_lines in project_blocks:
        name = ""
        first_line = ""
        for line in block_lines:
            # Skip if line is empty or just bullet
            name = re.sub(r"^[-–—*•●▪⁃⁌⁍◦⌢ò♦ü\d.)\s]+", "", line).strip()
            if name:
                first_line = line
                break
        if not name:
            continue

            
        # Extract possible inline project description
        # e.g., "Scoopio HTML, CSS|GitHub –Designed a ice cream website..."
        # Split on dash separator followed by capital letter
        parts = re.split(r"\s+[-–—]\s*(?=[A-Z])", name)
        name_part = parts[0].strip()
        inline_desc = " ".join(parts[1:]).strip()
        
        # Clean title name: remove trailing links or pipeline markers
        name = re.sub(r"\s*(?:/github|GitHub|github\.com|\||pipeline).*$", "", name_part, flags=re.IGNORECASE).strip()
        if len(name) < 2:
            continue
            
        block_text = "\n".join(block_lines)
        
        github_url = ""
        url_match = re.search(r"https?://(?:www\.)?github\.com/[^\s,;|)]+", block_text, re.IGNORECASE)
        if url_match:
            github_url = url_match.group(0)
        else:
            git_match = re.search(r"github\.com/[^\s,;|)]+", block_text, re.IGNORECASE)
            if git_match:
                github_url = "https://" + git_match.group(0)
        
        block_lower = block_text.lower()
        technologies = [t for t in TECH_KEYWORDS if re.search(r"\b" + re.escape(t.lower()) + r"\b", block_lower)]
        
        desc_parts = []
        if inline_desc:
            desc_parts.append(inline_desc)
            
        role = ""
        for line in block_lines[1:]:
            role_match = re.search(r"^(?:Role|Position)\s*[:\-]\s*(.*)", line, re.IGNORECASE)
            if role_match:
                role = role_match.group(1).strip()
                continue
            
            cleared = re.sub(r"^[-–—*•●▪⁃⁌⁍◦⌢ò♦ü\d.)\s]+", "", line).strip()
            if cleared and cleared.lower() not in (github_url.lower(), "github", "/github"):
                desc_parts.append(cleared)
        description = " ".join(desc_parts)
        
        # Discard invalid projects (empty or too short description)
        if len(description) < 10:
            continue
            
        domain = _classify_project_domain(block_lower, technologies)
        impact_m = re.search(
            r"(achiev|result|improv|reduc|increas|deployed|used by|accuracy)[^\n.]{0,120}",
            block_text, re.IGNORECASE)
        impact = impact_m.group(0).strip() if impact_m else ""
        
        projects.append({
            "name": name,
            "title": name,
            "technologies": technologies[:8],
            "description": description,
            "domain": domain,
            "impact": impact,
            "github_link": github_url,
            "github": github_url,
            "role": role
        })
        if len(projects) >= 6:
            break
            
    return projects

def extract_projects(text: str) -> List[Dict[str, Any]]:
    """
    Extract structured project dicts from projects section in resume text.
    Return schema: [{name, technologies, description, github, role}]
    """
    try:
        _start_logging(text)
        res = _local_state.results.get("projects", [])
        logger.info(f"[Resume Parser] Projects Found: {len(res)}")
        print("\n====================================")
        print("PROJECT TRACE")
        print("====================================")
        print(f"After parser:\nProjects = {len(res)}\n")
        return res
    except Exception as e:
        logger.error(f"[Resume Parser] Error extracting projects: {e}")
        return []

# ---------------------------------------------------------------------------
# Achievements, Certifications & Activities
# ---------------------------------------------------------------------------

def _do_extract_achievements(text: str) -> List[str]:
    sections = _segment_resume(text)
    ach_text = sections.get("achievements", "")
    achievements = []
    if ach_text:
        for line in ach_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^[-–—*•●▪⁃⁌⁍◦⌢ò♦ü\d.)\s]+", "", line).strip()
            if 5 < len(cleaned) < 250:
                achievements.append(cleaned)
    return achievements

def extract_achievements(text: str) -> List[str]:
    """Extract list of achievements from achievements section."""
    try:
        _start_logging(text)
        res = _local_state.results.get("achievements", [])
        logger.info(f"[Resume Parser] Achievements Found: {len(res)}")
        return res
    except Exception as e:
        logger.error(f"[Resume Parser] Error extracting achievements: {e}")
        return []

def _do_extract_certifications(text: str) -> List[str]:
    sections = _segment_resume(text)
    cert_text = sections.get("certifications", "")
    certifications = []
    if cert_text:
        for line in cert_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^[-–—*•●▪⁃⁌⁍◦⌢ò♦ü\d.)\s]+", "", line).strip()
            if 5 < len(cleaned) < 250:
                certifications.append(cleaned)
    return certifications

def extract_certifications(text: str) -> List[str]:
    """Extract list of certifications from certifications section."""
    try:
        _start_logging(text)
        res = _local_state.results.get("certifications", [])
        logger.info(f"[Resume Parser] Certifications Found: {len(res)}")
        return res
    except Exception as e:
        logger.error(f"[Resume Parser] Error extracting certifications: {e}")
        return []

def _do_extract_activities(text: str) -> List[str]:
    sections = _segment_resume(text)
    act_text = sections.get("activities", "")
    activities = []
    if act_text:
        for line in act_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^[-–—*•●▪⁃⁌⁍◦⌢ò♦ü\d.)\s]+", "", line).strip()
            if 5 < len(cleaned) < 250:
                activities.append(cleaned)
    return activities

def extract_activities(text: str) -> List[str]:
    """Extract list of activities/leadership roles from activities section."""
    try:
        _start_logging(text)
        res = _local_state.results.get("activities", [])
        logger.info(f"[Resume Parser] Activities Found: {len(res)}")
        return res
    except Exception as e:
        logger.error(f"[Resume Parser] Error extracting activities: {e}")
        return []

# ---------------------------------------------------------------------------
# Coding Profiles
# ---------------------------------------------------------------------------

def _do_extract_coding_profiles(text: str) -> Dict[str, str]:
    profiles = {
        "leetcode": "",
        "codechef": "",
        "hackerrank": "",
        "github": ""
    }
    sections = _segment_resume(text)
    cp_text = sections.get("coding_profiles", "")
    search_text = cp_text if cp_text else text
    
    platforms = ["leetcode", "codechef", "hackerrank", "github"]
    for platform in platforms:
        pattern = re.escape(platform) + r"\s*[:\-–—]?\s*(.*?)(?=\b(?:leetcode|codechef|hackerrank|github|achievements|activities|education|skills|projects|objective|responsibility|position)\b|[•●▪*⁃⁌⁍◦\n]|\Z)"
        m = re.search(pattern, search_text, re.IGNORECASE)
        val = ""
        if m:
            val = m.group(1).strip()
        
        if platform in ["leetcode", "codechef"]:
            rating_match = re.search(re.escape(platform) + r"\s+Rating\s*[:\-–—]?\s*(\d+)", text, re.IGNORECASE)
            if rating_match:
                val = f"Rating {rating_match.group(1)}"
        
        if not val or val.lower() == "profile":
            if platform == "github":
                url_m = re.search(r"https?://(?:www\.)?github\.com/[^\s,;|)]+", text, re.IGNORECASE)
                if url_m:
                    val = url_m.group(0)
            else:
                url_m = re.search(r"https?://(?:www\.)?" + re.escape(platform) + r"\.[a-z]+/[^\s,;|)]+", text, re.IGNORECASE)
                if url_m:
                    val = url_m.group(0)
        
        if not val:
            if re.search(r"\b" + re.escape(platform) + r"\b", search_text, re.IGNORECASE):
                val = "Found"
        
        profiles[platform] = val.strip()
    return profiles

def extract_coding_profiles(text: str) -> Dict[str, str]:
    """
    Extract coding profile links/usernames/ratings.
    Returns: {"leetcode": "...", "hackerrank": "...", "codechef": "...", "github": "..."}
    """
    try:
        _start_logging(text)
        res = _local_state.results.get("coding_profiles", {"leetcode": "", "codechef": "", "hackerrank": "", "github": ""})
        found_count = sum(1 for v in res.values() if v)
        logger.info(f"[Resume Parser] Coding Profiles Found: {found_count}")
        return res
    except Exception as e:
        logger.error(f"[Resume Parser] Error extracting coding profiles: {e}")
        return {"leetcode": "", "codechef": "", "hackerrank": "", "github": ""}

# ---------------------------------------------------------------------------
# Career Objective
# ---------------------------------------------------------------------------

def _do_extract_objective(text: str) -> str:
    sections = _segment_resume(text)
    objective = sections.get("objective", "").strip()
    if not objective:
        obj_m = re.search(
            r"(Career Objective|Objective|Goal|Summary)\s*[:\-]?\s*([^\n]{20,300})",
            text, re.IGNORECASE)
        if obj_m:
            objective = obj_m.group(2).strip()
    return objective

def extract_objective(text: str) -> str:
    """Extract career objective / summary from resume."""
    try:
        _start_logging(text)
        res = _local_state.results.get("objective", "")
        return res
    except Exception as e:
        logger.error(f"[Resume Parser] Error extracting objective: {e}")
        return ""
