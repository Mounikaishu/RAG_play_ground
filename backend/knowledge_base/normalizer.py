"""
normalizer.py — Entity Normalization Engine for Knowledge Base Metadata.

Normalizes raw extracted strings into canonical formats for clean metadata filtering:
- Company names (e.g. "Google Inc.", "GOOGLE", "Google LLC" -> "Google")
- Roles (e.g. "SDE-1", "Software Engineer 1", "SWE 1" -> "Software Engineer")
- Job Types ("FTE", "Intern")
- Interview Round Names ("Online Assessment", "Technical Round 1", "HR Round", etc.)
- Technologies & Skills
"""

import re
from typing import List

# ──────────────────────────────────────────────────────────
# Canonical Mappings
# ──────────────────────────────────────────────────────────

COMPANY_CANONICAL_MAP = {
    r"\bgoogle\b": "Google",
    r"\bamazon\b": "Amazon",
    r"\bmicrosoft\b": "Microsoft",
    r"\bmeta\b|\bfacebook\b": "Meta",
    r"\bapple\b": "Apple",
    r"\bnetflix\b": "Netflix",
    r"\buber\b": "Uber",
    r"\bsalesforce\b": "Salesforce",
    r"\boracle\b": "Oracle",
    r"\badobe\b": "Adobe",
    r"\bdeloitte\b": "Deloitte",
    r"\bnvidia\b": "NVIDIA",
    r"\bintel\b": "Intel",
    r"\bgoldman\s*sachs\b": "Goldman Sachs",
    r"\bjpmorgan\b|\bjp\s*morgan\b": "JPMorgan Chase",
    r"\bmorgan\s*stanley\b": "Morgan Stanley",
    r"\bflipkart\b": "Flipkart",
    r"\bswiggy\b": "Swiggy",
    r"\bzomato\b": "Zomato",
    r"\batlassian\b": "Atlassian",
    r"\bwalmart\b": "Walmart Labs",
    r"\btcs\b|\btata\s*consultancy\b": "TCS",
    r"\binfosys\b": "Infosys",
    r"\bwipro\b": "Wipro",
    r"\baccenture\b": "Accenture",
}

ROLE_CANONICAL_MAP = {
    r"\bsde\s*[-_\s]*1?\b|\bsoftware\s*development\s*engineer\s*1?\b|\bswe\s*1?\b|\bsoftware\s*engineer\b": "Software Engineer",
    r"\bsde\s*[-_\s]*2\b|\bsoftware\s*engineer\s*2\b": "Senior Software Engineer",
    r"\bdata\s*analyst\b": "Data Analyst",
    r"\bdata\s*scientist\b": "Data Scientist",
    r"\bai\s*engineer\b|\bml\s*engineer\b|\bmachine\s*learning\s*engineer\b": "AI/ML Engineer",
    r"\bfrontend\s*engineer\b|\bfrontend\s*developer\b": "Frontend Engineer",
    r"\bbackend\s*engineer\b|\bbackend\s*developer\b": "Backend Engineer",
    r"\bfull\s*stack\s*engineer\b|\bfull\s*stack\s*developer\b": "Full Stack Engineer",
    r"\bcloud\s*engineer\b|\bdevops\s*engineer\b": "DevOps / Cloud Engineer",
    r"\bproduct\s*manager\b": "Product Manager",
    r"\bqa\s*engineer\b|\btest\s*engineer\b": "QA Engineer",
}

ROUND_CANONICAL_MAP = {
    r"\boa\b|\bonline\s*assessment\b|\bcoding\s*test\b|\bhackerrank\b": "Online Assessment",
    r"\btechnical\s*round\s*1\b|\bcoding\s*round\s*1\b|\bdsa\s*round\b": "Technical Round 1",
    r"\btechnical\s*round\s*2\b|\bcoding\s*round\s*2\b": "Technical Round 2",
    r"\bsystem\s*design\b|\barchitectural\s*round\b": "System Design Round",
    r"\bbar\s*raiser\b": "Bar Raiser",
    r"\bhr\s*round\b|\bbehavioral\b|\bmanagerial\b": "HR / Behavioral Round",
}


def normalize_company(raw_name: str) -> str:
    """Normalize company name to canonical format."""
    if not raw_name or raw_name.strip().lower() in ("unknown", "n/a", "not specified", "none"):
        return "Unknown"

    cleaned = raw_name.strip()
    # Strip legal suffixes
    cleaned = re.sub(r"\b(Inc|LLC|Ltd|Limited|Corp|Corporation|Pvt|Private)\b\.?", "", cleaned, flags=iRE := re.IGNORECASE).strip()

    for pattern, canonical in COMPANY_CANONICAL_MAP.items():
        if re.search(pattern, cleaned, re.IGNORECASE):
            return canonical

    return cleaned.title()


def normalize_role(raw_role: str) -> str:
    """Normalize job title / role to canonical format."""
    if not raw_role or raw_role.strip().lower() in ("unknown", "n/a", "not specified", "general"):
        return "Software Engineer"

    cleaned = raw_role.strip()
    for pattern, canonical in ROLE_CANONICAL_MAP.items():
        if re.search(pattern, cleaned, re.IGNORECASE):
            return canonical

    return cleaned.title()


def normalize_job_type(raw_type: str) -> str:
    """Normalize job type to FTE or Intern."""
    if not raw_type:
        return "FTE"
    low = raw_type.lower()
    if any(k in low for k in ["intern", "co-op", "trainee", "6 months", "summer"]):
        return "Internship"
    return "FTE"


def normalize_rounds(rounds_input) -> List[str]:
    """Normalize a list or comma-separated string of interview rounds."""
    if isinstance(rounds_input, str):
        parts = [p.strip() for p in rounds_input.split(",") if p.strip()]
    elif isinstance(rounds_input, list):
        parts = [str(p).strip() for p in rounds_input if str(p).strip()]
    else:
        parts = []

    if not parts:
        return ["Technical Round 1"]

    normalized = []
    for part in parts:
        matched = False
        for pattern, canonical in ROUND_CANONICAL_MAP.items():
            if re.search(pattern, part, re.IGNORECASE):
                if canonical not in normalized:
                    normalized.append(canonical)
                matched = True
                break
        if not matched and part.strip():
            norm_part = part.strip().title()
            if norm_part not in normalized:
                normalized.append(norm_part)

    return normalized or ["Technical Round 1"]


def normalize_difficulty(raw_diff: str) -> str:
    """Normalize difficulty level to Easy, Medium, or Hard."""
    if not raw_diff:
        return "Medium"
    low = raw_diff.lower()
    if "easy" in low:
        return "Easy"
    if "hard" in low or "difficult" in low:
        return "Hard"
    return "Medium"


def normalize_skills(skills_input) -> List[str]:
    """Clean and deduplicate technical skills list."""
    if isinstance(skills_input, str):
        items = re.split(r"[,;\n|]", skills_input)
    elif isinstance(skills_input, list):
        items = skills_input
    else:
        items = []

    cleaned = []
    seen = set()
    for item in items:
        s = str(item).strip()
        if s and len(s) < 50:
            key = s.lower()
            if key not in seen:
                seen.add(key)
                cleaned.append(s)

    return cleaned
