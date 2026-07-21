"""
mentor_generator.py — Personalised AI Placement Mentor Prompt Engineering & Validation.

Implements Rules 1-14:
- Rule 1: Evidence Based Responses (never invent info, say unavailable if missing)
- Rule 2: Mandatory Alumni Citation ("Name (Company, Role)")
- Rule 3: Mandatory Resume Comparison (Skills ✓ / ✗)
- Rule 4: Project Comparison (Student Project vs Alumni Project gap)
- Rule 5: Interview Insights
- Rule 6: Company Recommendations (ONLY from retrieved alumni)
- Rule 7: Personalized 30-Day Roadmap
- Rule 8: Forbidden Phrases Banned ("Our alumni...", "To become an ML Engineer...", etc.)
- Rule 9: Exact 9-Section Output Structure
- Rule 10: Strict Post-Generation Validation & Retry Loop
- Rule 13: Context Priority (Student > Alumni > Interviews > Placement)
- Rule 14: Never Lose Retrieved Details
"""

import re
from typing import Dict, Any, Tuple
from llm import llm_call
from generation.context_extractor import extract_structured_context

FORBIDDEN_PHRASES = [
    "our alumni",
    "to become an ml engineer",
    "you should learn python",
    "machine learning requires",
]

REQUIRED_SECTIONS = [
    "# 🎯 Career Assessment",
    "# 📄 Resume Summary",
    "# 👨💻 Alumni Comparison",
    "# 📊 Skill Gap Analysis",
    "# 🚀 Project Recommendations",
    "# 💼 Company Recommendations",
    "# 🧠 Interview Preparation",
    "# 📅 Personalized 30-Day Plan",
    "# 📚 Recommended Resources",
]

def generate_mentor_response(state: Dict[str, Any], max_retries: int = 2) -> str:
    """
    Generates a production-quality personalised AI Placement Mentor response.
    Enforces all 14 Rules including pre-extraction, prompt construction, post-validation, and retries.
    """
    # Rule 12 & Rule 11: Structured Context Extraction & Logging
    structured = extract_structured_context(state)
    student = structured["student"]
    alumni = structured["alumni"]
    interviews = structured["interviews"]
    placement = structured["placement"]
    stats = structured["stats"]

    # Build prompt
    prompt = _build_mentor_prompt(state, student, alumni, interviews, placement)

    current_prompt = prompt
    response = ""

    for attempt in range(max_retries + 1):
        print(f"🤖 [GENERATION] Executing LLM Call (Attempt {attempt + 1}/{max_retries + 1})...")
        response = llm_call(current_prompt)

        # Rule 10: Post-Generation Validation
        is_valid, reasons = _validate_response(response, stats, student)

        if is_valid:
            print(f"✅ [GENERATION VALIDATION] Passed on attempt {attempt + 1}!")
            return response
        else:
            print(f"❌ [GENERATION VALIDATION] Failed on attempt {attempt + 1}: {reasons}")
            if attempt < max_retries:
                # Add retry feedback to prompt
                feedback = (
                    f"\n\nCRITICAL FIX REQUIRED (Attempt {attempt + 1} failed):\n"
                    f"Your previous output failed validation for the following reasons:\n" +
                    "\n".join([f"- {r}" for r in reasons]) +
                    "\n\nYou MUST fix these issues in your response! Maintain all 9 required headers and strict alumni citations."
                )
                current_prompt = prompt + feedback

    print("⚠️ [GENERATION VALIDATION] Max retries reached. Returning best available response.")
    return response


def _build_mentor_prompt(
    state: Dict[str, Any],
    student: Dict[str, Any],
    alumni: list,
    interviews: list,
    placement: str
) -> str:
    history_text = "\n".join(state.get("history", [])[-10:])
    question = state["question"]

    # Rule 13: Priority 1 - Student Resume
    resume_section = (
        student["raw_resume"]
        if student["has_resume"]
        else "No resume uploaded by student yet. Explicitly state this under # 📄 Resume Summary."
    )

    # Rule 13: Priority 2 - Alumni Profiles
    if alumni:
        alumni_text_blocks = []
        for i, a in enumerate(alumni, 1):
            alumni_text_blocks.append(
                f"Alumni #{i}:\n"
                f"- Name: {a['name']}\n"
                f"- Company: {a['company']}\n"
                f"- Role: {a['role']}\n"
                f"- Skills: {', '.join(a['skills']) if a['skills'] else 'Not listed'}\n"
                f"- Projects: {', '.join(a['projects']) if a['projects'] else 'Not listed'}\n"
                f"- Profile Details: {a['full_text'][:400]}"
            )
        alumni_section = "\n\n".join(alumni_text_blocks)
    else:
        alumni_section = "This information is not available in the institutional knowledge base."

    # Rule 13: Priority 3 - Interview Experiences
    if interviews:
        interview_text_blocks = []
        for idx, exp in enumerate(interviews, 1):
            interview_text_blocks.append(
                f"Interview Experience #{idx}:\n"
                f"- Senior/Author: {exp['author']}\n"
                f"- Company: {exp['company']}\n"
                f"- Role: {exp['role']}\n"
                f"- Difficulty: {exp['difficulty']}\n"
                f"- Details: {exp['full_text'][:400]}"
            )
        interview_section = "\n\n".join(interview_text_blocks)
    else:
        interview_section = "This information is not available in the institutional knowledge base."

    # Rule 13: Priority 4 - Placement Materials
    placement_section = placement if placement else "This information is not available in the institutional knowledge base."

    prompt = f"""You are a university AI Placement Mentor with complete knowledge of the student's resume, alumni resumes, interview experiences, and placement guides.

=== CONTEXT DATA (PRIORITY 1: RESUME > PRIORITY 2: ALUMNI > PRIORITY 3: INTERVIEWS > PRIORITY 4: PLACEMENT) ===

[STUDENT RESUME PROFILE]
Name: {student['name']}
Department: {student['department']}
Skills List: {', '.join(student['skills']) if student['skills'] else student['known_skills']}
Raw Resume Context:
{resume_section}

[RETRIEVED ALUMNI RESUMES (Placed Seniors)]
{alumni_section}

[RETRIEVED INTERVIEW EXPERIENCES]
{interview_section}

[RETRIEVED PLACEMENT MATERIALS]
{placement_section}

[CONVERSATION HISTORY]
{history_text}

[STUDENT QUESTION]
{question}

=== MANDATORY SYSTEM RULES & GUIDELINES ===

RULE 1: EVIDENCE-BASED ONLY
- Every single recommendation MUST come directly from retrieved documents above.
- Never invent information, companies, projects, or alumni.
- If information for a section is missing from the context, state EXACTLY: "This information is not available in the institutional knowledge base."

RULE 2: MANDATORY ALUMNI CITATION
- NEVER write "Our alumni...", "Some seniors...", or speak generically.
- ALWAYS cite specific alumni by Name, Company, and Role.
- Format example: "Meera Krishnan (Adobe, Machine Learning Engineer)" or "Nikhil Sharma (Amazon, Software Engineer)".

RULE 3 & 4: MANDATORY RESUME & PROJECT COMPARISON
- Compare student's skills against retrieved alumni. Use matching checkmarks (✓) and missing crosses (✗).
- Compare student's projects vs alumni projects and explicitly state the project gap.

RULE 5 & 6: INTERVIEW & COMPANY RECOMMENDATIONS
- Summarize interview rounds, difficulty, and questions from retrieved interview experiences.
- Recommend ONLY companies present in the retrieved alumni profiles.

RULE 7 & 8: NO GENERIC SENTENCES & ROADMAP
- ABSOLUTELY FORBIDDEN PHRASES: "Our alumni...", "To become an ML Engineer...", "You should learn Python...", "Machine Learning requires...".
- Create a personalized 30-Day Plan (Week 1, Week 2, Week 3, Week 4).

RULE 9: MANDATORY OUTPUT STRUCTURE
Your response MUST contain EXACTLY these 9 section markdown headers in order:

# 🎯 Career Assessment
Overall readiness, Resume score, Target role

# 📄 Resume Summary
Education, Experience, Projects, Skills, Achievements

# 👨💻 Alumni Comparison
For every matched alumni: Name, Company, Role, Skill overlap, Project overlap, Missing skills

# 📊 Skill Gap Analysis
Already Have, Missing, Priority

# 🚀 Project Recommendations
Specific projects, Why, Which alumni completed similar projects

# 💼 Company Recommendations
Top matching companies, Reason, Matched alumni

# 🧠 Interview Preparation
Retrieved interview experiences, Companies, Important topics, Difficulty

# 📅 Personalized 30-Day Plan
Week 1, Week 2, Week 3, Week 4

# 📚 Recommended Resources
Only resources relevant to missing skills.

Begin your response directly with "# 🎯 Career Assessment" now:"""

    return prompt


def _validate_response(response: str, stats: Dict[str, Any], student: Dict[str, Any]) -> Tuple[bool, list]:
    reasons = []
    resp_lower = response.lower()

    # 1. Check Forbidden Phrases
    for phrase in FORBIDDEN_PHRASES:
        if phrase in resp_lower:
            reasons.append(f"Contains forbidden generic phrase: '{phrase}'")

    # 2. Check Required Headers (Rule 9)
    for header in REQUIRED_SECTIONS:
        # Check header title without emoji if emoji matching is tricky
        header_title = header.split(" ", 1)[-1].lower()
        if header.lower() not in resp_lower and header_title not in resp_lower:
            reasons.append(f"Missing required section header: '{header}'")

    # 3. Check Alumni Citation (Rule 2)
    if stats["names"]:
        found_name = any(name.lower() in resp_lower for name in stats["names"])
        if not found_name:
            reasons.append(f"Failed to cite any retrieved alumni by name from: {stats['names']}")

    # 4. Check Company Citation (Rule 6)
    if stats["companies"]:
        found_company = any(company.lower() in resp_lower for company in stats["companies"])
        if not found_company:
            reasons.append(f"Failed to mention any retrieved company from: {stats['companies']}")

    # 5. Check Student Skills (Rule 3)
    if student["skills"]:
        found_skill = any(skill.lower() in resp_lower for skill in student["skills"])
        if not found_skill:
            reasons.append(f"Failed to reference student's skills: {student['skills'][:5]}")

    is_valid = len(reasons) == 0
    return is_valid, reasons
