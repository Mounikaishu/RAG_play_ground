"""
Metadata Extractor — Uses Gemini LLM to extract structured metadata from resume text.

Extracts: name, department, skills, cgpa, projects, experience_summary
This enables rich metadata-based filtering and display in the Recruit tab.
"""

import json
import re
from llm import llm_call


def extract_resume_metadata(resume_text: str) -> dict:
    """
    Calls Gemini to extract structured metadata from raw resume text.

    Returns a dict with:
        - name: str
        - department: str
        - skills: list[str]
        - cgpa: str
        - projects: list[str]
        - experience_summary: str
    """
    prompt = f"""
Analyze the following resume text and extract structured metadata.
You MUST respond with ONLY a valid JSON object, no other text.

Resume Text:
{resume_text[:4000]}

Return EXACTLY this JSON format (no markdown, no code fences, just raw JSON):
{{
  "name": "<full name of the candidate>",
  "department": "<department or major, e.g. Computer Science, Electronics>",
  "skills": ["skill1", "skill2", "skill3"],
  "cgpa": "<CGPA or GPA if mentioned, otherwise 'N/A'>",
  "projects": ["project name 1", "project name 2"],
  "experience_summary": "<1-2 sentence summary of their experience and strengths>"
}}

Important:
- Extract ALL skills mentioned (programming languages, frameworks, tools, soft skills)
- Extract ALL project names mentioned
- If department is not clear, infer from context or use "Not Specified"
- Keep skills as individual items, not combined phrases
"""

    raw = llm_call(prompt)

    try:
        # Remove markdown code fences if present
        cleaned = re.sub(r"```json\s*", "", raw)
        cleaned = re.sub(r"```\s*", "", cleaned)
        cleaned = cleaned.strip()
        data = json.loads(cleaned)

        # Ensure all required fields exist with defaults
        return {
            "name": data.get("name", "Unknown"),
            "department": data.get("department", "Not Specified"),
            "skills": data.get("skills", []),
            "cgpa": str(data.get("cgpa", "N/A")),
            "projects": data.get("projects", []),
            "experience_summary": data.get("experience_summary", ""),
        }
    except Exception as e:
        print(f"⚠️ Metadata extraction failed: {e}")
        # Fallback: try to extract name from first line
        first_line = resume_text.strip().split("\n")[0].strip()
        return {
            "name": first_line[:50] if first_line else "Unknown",
            "department": "Not Specified",
            "skills": [],
            "cgpa": "N/A",
            "projects": [],
            "experience_summary": "Metadata could not be auto-extracted.",
        }
