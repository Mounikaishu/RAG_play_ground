"""
dynamic_mentor.py — Retrieval-Driven Dynamic AI Placement Mentor with Multi-Level Confidence & Attribution.

Architecture & Principles:
1. Intent-Driven Dynamic Generation — No hardcoded templates or fixed 9 sections.
2. Explains pre-computed deterministic matching scores (skill overlap, match score, confidence score).
3. Dynamic Evidence Attribution — Links recommendations to unique Evidence Object IDs (`alumni_ev_1`).
4. Evidence-First — If evidence is missing, outputs "This information is not available in the institutional knowledge base."
5. Dynamic Prompt Builder — Includes ONLY context relevant to the user query.
6. Context-based Validation — Validates outputs against actual retrieved objects (not hardcoded strings).
7. Structured Evidence Logging — Logs statistics & multi-level confidence without exposing sensitive text.
"""

from typing import Dict, List, Any, Tuple
from llm import llm_call
from generation.structured_evidence import (
    extract_structured_evidence,
    compute_deterministic_recommendations,
    StudentProfile,
    AlumniProfile,
    InterviewExperience,
    PlacementMaterial
)


def generate_dynamic_mentor_response(state: Dict[str, Any], max_retries: int = 2) -> str:
    """
    Main entry point for dynamic, retrieval-driven mentor generation.
    Orchestrates:
    1. Structured Evidence Extraction (metadata-first)
    2. Deterministic Matching Engine (Python-computed match scores, overlap arrays, multi-level confidence)
    3. Intent Analysis (query-driven focus)
    4. Dynamic Prompt Construction (with Evidence Attribution IDs)
    5. Context-driven Post-Validation
    6. Non-sensitive Multi-Level Evidence Logging
    """
    question = state["question"]

    # 1. Extract Structured Evidence Objects
    evidence = extract_structured_evidence(state)
    student: StudentProfile = evidence["student"]
    alumni_list: List[AlumniProfile] = evidence["alumni"]
    interview_list: List[InterviewExperience] = evidence["interviews"]
    placement_list: List[PlacementMaterial] = evidence["placement"]

    # 2. Deterministic Recommendation Engine (Python calculates match & confidence scores)
    matches = compute_deterministic_recommendations(student, alumni_list)

    # 3. Detect Intent & Query Focus
    intent = _detect_query_intent(question)

    # 4. Multi-Level Evidence Logging (Non-sensitive)
    _log_generation_evidence(state, evidence, matches, intent)

    # 5. Build Dynamic Prompt
    prompt = _build_dynamic_prompt(question, intent, student, matches, interview_list, placement_list, state)

    current_prompt = prompt
    response = ""

    for attempt in range(max_retries + 1):
        print(f"🤖 [DYNAMIC GENERATION] LLM Invocation (Attempt {attempt + 1}/{max_retries + 1} | Intent: {intent})...")
        response = llm_call(current_prompt)

        # 6. Validate against retrieved context
        is_valid, reasons = _validate_response_against_context(response, evidence, matches, intent)

        if is_valid:
            print(f"✅ [DYNAMIC GENERATION VALIDATION] Passed on attempt {attempt + 1}!")
            return response
        else:
            print(f"❌ [DYNAMIC GENERATION VALIDATION] Failed on attempt {attempt + 1}: {reasons}")
            if attempt < max_retries:
                feedback = (
                    f"\n\nCRITICAL FIX REQUIRED (Attempt {attempt + 1} failed):\n" +
                    "\n".join([f"- {r}" for r in reasons]) +
                    "\n\nPlease regenerate answering the user's specific question using only the retrieved evidence."
                )
                current_prompt = prompt + feedback

    print("⚠️ [DYNAMIC GENERATION VALIDATION] Max retries reached. Returning best response.")
    return response


def _detect_query_intent(query: str) -> str:
    """Detects query intent to focus prompt instructions dynamically."""
    q_lower = query.lower()
    if any(k in q_lower for k in ["skill", "gap", "missing", "learn", "improve"]):
        return "skill_gap"
    elif any(k in q_lower for k in ["compare", "alumni", "senior", "resume vs"]):
        return "alumni_comparison"
    elif any(k in q_lower for k in ["interview", "round", "question", "prep", "experience"]):
        return "interview_prep"
    elif any(k in q_lower for k in ["company", "companies", "apply", "target"]):
        return "company_guidance"
    elif any(k in q_lower for k in ["roadmap", "plan", "30-day", "schedule"]):
        return "roadmap"
    else:
        return "general_mentorship"


def _log_generation_evidence(
    state: Dict[str, Any],
    evidence: Dict[str, Any],
    matches: List[Dict[str, Any]],
    intent: str
):
    """Rule: Log counts, extracted entities, confidence scores, selected evidence without sensitive content."""
    student: StudentProfile = evidence["student"]
    alumni_list = evidence["alumni"]
    interview_list = evidence["interviews"]
    placement_list = evidence["placement"]

    scores = [f"{m['alumni_name']} ({m['match_score']}% | Conf: {m['confidence_level']})" for m in matches[:3]]

    print("\n" + "═" * 60)
    print("📊 [DYNAMIC GENERATION LOGGING] Multi-Level Evidence & Confidence Summary")
    print("═" * 60)
    print(f"  • Query Intent       : {intent}")
    print(f"  • Resume Chunks      : {1 if student.has_resume else 0}")
    print(f"  • Alumni Evidence    : {len(alumni_list)} items")
    print(f"  • Interview Evidence : {len(interview_list)} items")
    print(f"  • Placement Materials: {len(placement_list)} items")
    print(f"  • Pre-Computed Scores: {scores if scores else 'None'}")
    print(f"  • Intent Focus       : {intent}")
    print("═" * 60 + "\n")


def _build_dynamic_prompt(
    question: str,
    intent: str,
    student: StudentProfile,
    matches: List[Dict[str, Any]],
    interviews: List[InterviewExperience],
    placement: List[PlacementMaterial],
    state: Dict[str, Any]
) -> str:
    history_text = "\n".join(state.get("history", [])[-6:])

    # Student summary string
    if student.has_resume:
        projects_str = "\n".join([f"- {p}" for p in student.projects]) if student.projects else "None listed in structured evidence (check resume excerpt below)"
        student_str = (
            f"Evidence ID: {student.evidence_id}\n"
            f"Name: {student.name}\n"
            f"Department: {student.department}\n"
            f"Skills: {', '.join(sorted(list(student.skills))) if student.skills else 'None specified'}\n"
            f"Projects:\n{projects_str}\n"
            f"Resume Text Excerpt:\n{student.raw_text[:800]}"
        )
    else:
        student_str = f"Evidence ID: {student.evidence_id} | Name: {student.name} | Department: {student.department} | Skills: {', '.join(sorted(list(student.skills))) if student.skills else 'None specified'}\nNote: Student has NOT uploaded a resume yet."

    # Deterministic Matches Block (Python computed)
    if matches:
        match_blocks = []
        for m in matches[:4]:
            alumni_details = []
            if m['alumni_name'] and m['alumni_name'] not in ["Alumni Senior", "Unknown Alumni"]:
                alumni_details.append(f"Alumni: {m['alumni_name']}")
            if m['company'] and m['company'] not in ["Placed Company", "Unknown Company"]:
                alumni_details.append(f"Company: {m['company']}")
            if m['role'] and m['role'] not in ["Software Engineer", "Unknown Role"]:
                alumni_details.append(f"Role: {m['role']}")
                
            details_str = " | ".join(alumni_details)
            if not details_str:
                details_str = "Alumni Profile"
            
            # Format projects nicely
            proj_str = ""
            if m.get('projects'):
                for p in m['projects'][:3]:
                    title = p.get("title", "Project")
                    desc = p.get("description", "")
                    techs = ", ".join(p.get("technologies", []))
                    proj_str += f"\n    - {title}: {desc}"
                    if techs: proj_str += f" (Tech: {techs})"
            else:
                proj_str = " No structured project data"

            # Format experience nicely
            exp_str = ""
            if m.get('experience'):
                for e in m['experience'][:3]:
                    comp = e.get("company", "")
                    rol = e.get("role", "")
                    dur = e.get("duration", "")
                    if comp or rol:
                        exp_str += f"\n    - {rol} at {comp} ({dur})"
            else:
                exp_str = " No explicit experience blocks"

            match_blocks.append(
                f"[Evidence ID: {m['evidence_id']}]\n"
                f"- {details_str}\n"
                f"  • Match Score: {m['match_score']}% (Conf: {m['confidence_level']})\n"
                f"  • Skills: {', '.join(m['matching_skills'] + m['missing_skills'])}\n"
                f"  • Technologies: {', '.join(m.get('technologies', []))}\n"
                f"  • Experience:{exp_str}\n"
                f"  • Projects:{proj_str}\n"
                f"  • Certifications: {', '.join(m.get('certifications', []))}\n"
                f"  • Full Excerpt: {m['raw_text'][:300]}"
            )
        alumni_str = "\n\n".join(match_blocks)
    else:
        alumni_str = "This information is not available in the institutional knowledge base."

    # Interview Experiences Block
    if interviews:
        int_blocks = []
        for exp in interviews[:4]:
            int_blocks.append(
                f"[Evidence ID: {exp.evidence_id}]\n"
                f"- Company: {exp.company} | Role: {exp.role} | Difficulty: {exp.difficulty}\n"
                f"  Details: {exp.raw_text[:400]}"
            )
        interview_str = "\n\n".join(int_blocks)
    else:
        interview_str = "This information is not available in the institutional knowledge base."

    # Placement Guides Block
    if placement:
        placement_str = "\n".join([f"[Evidence ID: {p.evidence_id}] - {p.title}: {p.raw_text[:300]}" for p in placement[:3]])
    else:
        placement_str = "This information is not available in the institutional knowledge base."

    prompt = f"""You are an experienced Senior University Placement Mentor conducting a personalized placement strategy session with a student.
You have access to structured evidence retrieved from the institutional knowledge base.

=== RETRIEVED STRUCTURED EVIDENCE ===

[STUDENT PROFILE EVIDENCE]
{student_str}

[PRE-COMPUTED ALUMNI MATCHES (DETERMINISTIC PYTHON ENGINE)]
{alumni_str}

[INTERVIEW EXPERIENCES EVIDENCE]
{interview_str}

[PLACEMENT MATERIALS EVIDENCE]
{placement_str}

[CONVERSATION HISTORY]
{history_text}

[USER QUESTION]
{question}

=== SENIOR MENTOR RESPONSE & STYLE INSTRUCTIONS ===

1. HALLUCINATION PREVENTION (STRICT):
   - NEVER invent alumni names, company names, projects, or interview rounds. 
   - NEVER invent project suggestions like "Stable Diffusion" or "RAG" unless explicitly present in the retrieved alumni evidence.
   - If evidence is unavailable for a specific section, explicitly state: "This information is not available in the institutional knowledge base."
   - Do NOT say "Not specified" or "Not listed" for missing alumni details. Simply omit the field entirely (e.g., if company is missing, just show Name and Role).

2. OUTPUT STYLE:
   - Use rich markdown.
   - Use structured Markdown TABLES for skill comparisons (e.g., `| Category | Student | Alumni |`).
   - Use concise bullets instead of long paragraphs.
   - Ensure the comparison is highly readable and visually structured.

3. ADAPTIVE SECTION ORGANIZATION (INCLUDE ONLY IF EVIDENCE EXISTS):
   Organize your response naturally based on the user's query intent ('{intent}') and the retrieved evidence:

   • STUDENT PROFILE SUMMARY:
     - Summarize only information actually present in the uploaded resume (Education, Skills, Projects, Experience, Certifications).
     - Do NOT state that projects are missing unless the structured evidence extractor explicitly says 'None listed in structured evidence' AND you find zero projects in the raw resume text excerpt.

   • ALUMNI COMPARISON & SELECTION REASONING:
     - Display Name, Company, and Role ONLY if available in evidence. Hide unavailable fields.
     - Detail Shared Skills (✓) and Missing Skills (✗).
     - Explain WHY the alumnus was selected based on shared skills and gaps.

   • MATCH SCORE EXPLANATION:
     - Do NOT simply print "43%".
     - Explain the score: "Your profile currently matches approximately {matches[0]['match_score'] if matches else 'N/A'}% of this alumni profile based on skill overlap and project similarity. Confidence is {matches[0]['confidence_level'] if matches else 'N/A'} because..."

   • DETAILED PROJECT COMPARISON (CRITICAL):
     - Compare student's projects vs retrieved alumni projects directly (e.g., "Your Project: [Name] ↓ Alumni Project: [Name]").
     - Detail Strengths and Gaps in tech stack (e.g., "Both involve Machine Learning. Gap: Alumni project uses PyTorch and deployment").
     - If alumni projects are unavailable in the evidence, state: "The retrieved alumni profile does not contain sufficient project information for comparison." DO NOT invent projects to compare.

   • SKILL COMPARISON TABLE:
     - Present a markdown table comparing Student skills vs Alumni skills side-by-side, marking ✅ and ❌. List the specific Gaps below the table.

   • INTERVIEW EXPERIENCE INSIGHTS:
     - If interview evidence exists, summarize Company, Difficulty, Interview Rounds, Frequently Asked Topics, and Important Technical Areas.
     - Only include companies retrieved from evidence. If none exist, omit this section.

   • PLACEMENT MATERIAL GUIDANCE:
     - Summarize relevant preparation guidance from retrieved placement materials. Do not copy the whole document.

   • EVIDENCE-GROUNDED ROADMAP:
     - The roadmap MUST directly reference the retrieved evidence.
     - AVOID generic advice like "Attend seminars" or "Learn AI".
     - USE evidence-backed goals: "Immediate Priorities: Learn PyTorch because every retrieved Machine Learning Engineer profile uses it."
     - Tie Short-Term and Long-Term Goals directly to the retrieved alumni, skills, or interview insights.

Write your dynamic, rich, senior mentor response now in clean Markdown formatting:"""

    return prompt



def _validate_response_against_context(
    response: str,
    evidence: Dict[str, Any],
    matches: List[Dict[str, Any]],
    intent: str
) -> Tuple[bool, List[str]]:
    """
    Validates output against actual retrieved context objects (not hardcoded strings).
    """
    reasons = []
    resp_lower = response.lower()

    # 1. Banned generic phrases check
    forbidden = ["our alumni", "to become an ml engineer", "you should learn python", "machine learning requires"]
    for f in forbidden:
        if f in resp_lower:
            reasons.append(f"Contains forbidden generic phrase: '{f}'")

    # 2. Check if alumni were retrieved, response references at least one retrieved alumni
    if matches and matches[0]["alumni_name"] not in ["Alumni", "Alumni Senior"]:
        found_alumni = any(m["alumni_name"].lower() in resp_lower for m in matches if m["alumni_name"])
        if not found_alumni and intent in ["alumni_comparison", "skill_gap", "company_guidance"]:
            reasons.append(f"Failed to reference retrieved alumni e.g. '{matches[0]['alumni_name']}'")

    # 3. Check if interviews were retrieved and intent is interview prep
    interviews: List[InterviewExperience] = evidence["interviews"]
    if interviews and intent == "interview_prep":
        found_company = any(i.company.lower() in resp_lower for i in interviews if i.company and i.company != "Unknown Company")
        if not found_company:
            reasons.append("Failed to mention company from retrieved interview experiences.")

    is_valid = len(reasons) == 0
    return is_valid, reasons
