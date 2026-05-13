"""
Alumni Metadata Extractor — Extracts structured metadata from alumni resume text.

Uses Gemini LLM to extract: student_name, company, role, department, batch, skills.
Falls back to regex-based extraction if LLM fails.
"""

import json
import re
from llm import llm_call


def extract_alumni_metadata(text: str) -> dict:
    """
    Extract structured metadata from an alumni resume/profile text.

    Returns dict with:
        - student_name: str
        - company: str
        - role: str
        - department: str
        - batch: str (graduation year)
        - skills: list[str]
    """
    prompt = f"""Analyze the following alumni resume/profile text and extract structured metadata.
You MUST respond with ONLY a valid JSON object, no other text.

Resume/Profile Text:
{text[:4000]}

Return EXACTLY this JSON format (no markdown, no code fences, just raw JSON):
{{
  "student_name": "<full name of the person>",
  "company": "<company where they were placed or currently work>",
  "role": "<job title/role>",
  "department": "<academic department, e.g. Computer Science, IT, ECE>",
  "batch": "<graduation/passing out year, e.g. 2023>",
  "skills": ["skill1", "skill2", "skill3"]
}}

Important:
- Extract ALL technical skills mentioned (languages, frameworks, tools)
- If company is not clear, use "Not Specified"
- If batch/year is mentioned as "Batch of 2023" or "2019-2023", extract the graduation year
- Keep skills as individual items"""

    raw = llm_call(prompt)

    try:
        cleaned = re.sub(r"```json\s*", "", raw)
        cleaned = re.sub(r"```\s*", "", cleaned)
        cleaned = cleaned.strip()
        data = json.loads(cleaned)

        return {
            "student_name": data.get("student_name", "Unknown"),
            "company": data.get("company", "Not Specified"),
            "role": data.get("role", "Not Specified"),
            "department": data.get("department", "Not Specified"),
            "batch": str(data.get("batch", "N/A")),
            "skills": data.get("skills", []),
        }
    except Exception as e:
        print(f"⚠️ LLM metadata extraction failed: {e}. Falling back to regex.")
        return _regex_fallback(text)


def _regex_fallback(text: str) -> dict:
    """Regex-based fallback for metadata extraction."""
    lines = text.strip().split("\n")

    # Try to extract name from first non-empty line
    name = "Unknown"
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and len(line) < 60:
            name = line
            break

    # Try to find company
    company = "Not Specified"
    company_patterns = [
        r"(?:placed at|working at|joined|company[:\s]+)\s*(\w[\w\s]+)",
        r"\|\s*(\w+)\s*\|",  # Matches "| Google |" style
    ]
    for pattern in company_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            break

    # Try to find role
    role = "Not Specified"
    role_patterns = [
        r"(?:role|position|title)[:\s]+(.+)",
        r"(?:as an?|as)\s+(.+?)(?:\s+with|\s+at|\n)",
    ]
    for pattern in role_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            role = match.group(1).strip()
            break

    # Try to find batch/year
    batch = "N/A"
    year_match = re.search(r"(?:batch|graduated|class)\s*(?:of\s*)?(\d{4})", text, re.IGNORECASE)
    if year_match:
        batch = year_match.group(1)

    # Try to find department
    department = "Not Specified"
    dept_patterns = [
        r"(?:department|dept|branch)[:\s]+(.+)",
        r"B\.?Tech\s+(?:in\s+)?(.+?)(?:\s*[-—]|\n)",
    ]
    for pattern in dept_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            department = match.group(1).strip()
            break

    # Extract skills from SKILLS section
    skills = []
    skills_match = re.search(r"SKILLS?\s*\n(.+?)(?:\n\n|\nEXPERIENCE|\nPROJECTS)", text, re.IGNORECASE | re.DOTALL)
    if skills_match:
        skills_text = skills_match.group(1)
        skills = [s.strip() for s in re.split(r"[,\n]", skills_text) if s.strip() and len(s.strip()) < 50]

    return {
        "student_name": name,
        "company": company,
        "role": role,
        "department": department,
        "batch": batch,
        "skills": skills[:20],  # Cap at 20 skills
    }


def extract_interview_metadata_from_filename(filename: str) -> dict:
    """
    Parse interview metadata from filename convention.
    Expected format: Company_Role_Round.txt (e.g., Amazon_SDE1_AllRounds.txt)
    """
    name = filename.rsplit(".", 1)[0]  # Remove extension
    parts = name.split("_")

    company = parts[0] if len(parts) > 0 else "Unknown"
    role = parts[1] if len(parts) > 1 else "General"
    round_type = parts[2] if len(parts) > 2 else "all_rounds"

    return {
        "company": company,
        "role": role,
        "round": round_type,
    }


def extract_interview_metadata_from_content(text: str) -> dict:
    """
    Extract interview metadata from the content of the file.
    Looks for structured headers like 'Company:', 'Role:', 'Difficulty:'.
    """
    metadata = {
        "company": "Unknown",
        "role": "General",
        "round": "all_rounds",
        "difficulty": "Medium",
    }

    patterns = {
        "company": r"Company[:\s]+(.+)",
        "role": r"Role[:\s]+(.+)",
        "difficulty": r"Difficulty[:\s]+(.+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()

    # Detect rounds from content
    rounds_found = []
    round_keywords = {
        "online_assessment": ["online assessment", "hackerrank", "coding test", "OA"],
        "technical": ["technical round", "coding round", "dsa round"],
        "system_design": ["system design", "design round"],
        "behavioral": ["behavioral", "hr round", "managerial"],
        "bar_raiser": ["bar raiser"],
    }
    text_lower = text.lower()
    for round_name, keywords in round_keywords.items():
        if any(kw in text_lower for kw in keywords):
            rounds_found.append(round_name)

    if rounds_found:
        metadata["round"] = ", ".join(rounds_found) if len(rounds_found) > 1 else rounds_found[0]
    if len(rounds_found) > 2:
        metadata["round"] = "all_rounds"

    return metadata
