"""
dynamic_mentor.py — Retrieval-Driven Dynamic AI Placement Mentor.

Fixes applied (Issues 6, 9, 10, 11, 12):
  6.  Intent classification: ML/AI/DL/NLP terms map to domain_guidance/career_guidance/skill_gap
  9.  Prompt builder: ALL extracted fields forwarded (designation, education, certifications,
      achievements, career_path, interview rounds/topics/FAQs, aggregated insights)
  10. Why-selected explanation per alumnus in prompt
  11. Evidence citations in every recommendation block
  12. Prompt Builder Summary log before LLM invocation
"""

from typing import Dict, List, Any, Tuple
from llm import llm_call
from config import TOP_ALUMNI_COUNT
from generation.structured_evidence import (
    extract_structured_evidence,
    compute_deterministic_recommendations,
    aggregate_alumni_evidence,
    StudentProfile,
    AlumniProfile,
    InterviewExperience,
    PlacementMaterial,
)


# ---------------------------------------------------------------------------
# Intent Detection (Issue 6)
# ---------------------------------------------------------------------------

# Single-word ML tokens (matchable via word-set intersection)
_ML_SINGLE_TERMS = {
    "ml", "ai", "nlp", "llm", "gan", "bert", "gpt",
    "transformers", "cv", "dl",
}

# Multi-word ML phrases (requiresubstring search on the full lowered query)
_ML_PHRASE_TERMS = [
    "machine learning", "deep learning", "artificial intelligence",
    "neural network", "natural language processing", "computer vision",
    "large language model", "generative ai", "gen ai",
    "stable diffusion", "reinforcement learning", "transfer learning",
]

_SKILL_GAP_TERMS = {
    "skill", "gap", "missing", "learn", "improve", "upskill",
    "lacking", "need to know", "what to learn",
}

_CAREER_TERMS = {
    "career", "job", "placement", "role", "company", "company",
    "work at", "get into", "join", "hired", "opportunity", "path",
}

_ALUMNI_TERMS = {
    "compare", "alumni", "senior", "resume vs", "similar", "like me",
    "which alumni", "how did", "who got placed",
}

_INTERVIEW_TERMS = {
    "interview", "round", "question", "prep", "preparation",
    "oa", "online assessment", "technical round", "hr round", "coding test",
}

_COMPANY_TERMS = {
    "company", "companies", "apply", "target", "apply to",
    "google", "amazon", "adobe", "microsoft", "meta", "flipkart",
    "which companies",
}

_ROADMAP_TERMS = {
    "roadmap", "plan", "30-day", "schedule", "timeline",
    "week", "month", "how long", "preparation plan",
}


def _detect_query_intent(query: str) -> str:
    import re as _re
    q_lower = query.lower()
    # Strip punctuation from each token for robust set intersection
    words = set(_re.sub(r"[^\w]", "", w) for w in q_lower.split())

    # ML/AI queries — check both single-word tokens AND substrings for multi-word terms
    ml_hit = (words & _ML_SINGLE_TERMS) or any(t in q_lower for t in _ML_PHRASE_TERMS)
    if ml_hit:
        if words & _SKILL_GAP_TERMS or any(t in q_lower for t in ["skill", "gap", "missing", "learn", "improve", "need", "what should"]):
            return "skill_gap"
        return "domain_guidance"

    if words & _SKILL_GAP_TERMS:
        return "skill_gap"
    if words & _ALUMNI_TERMS or any(t in q_lower for t in ["alumni", "compare", "similar to me"]):
        return "alumni_comparison"
    if words & _INTERVIEW_TERMS or any(t in q_lower for t in ["interview", "preparation", "online assessment"]):
        return "interview_prep"
    if words & _COMPANY_TERMS or any(t in q_lower for t in ["companies", "apply to", "which company"]):
        return "company_guidance"
    if words & _ROADMAP_TERMS or any(t in q_lower for t in ["roadmap", "timeline", "preparation plan"]):
        return "roadmap"
    if words & _CAREER_TERMS or any(t in q_lower for t in ["career", "placement", "job", "get into"]):
        return "career_guidance"

    return "general_mentorship"


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def generate_dynamic_mentor_response(state: Dict[str, Any], max_retries: int = 2) -> str:
    question = state["question"]

    # 1. Extract structured evidence
    evidence = extract_structured_evidence(state)
    student: StudentProfile = evidence["student"]
    alumni_list: List[AlumniProfile] = evidence["alumni"]
    interview_list: List[InterviewExperience] = evidence["interviews"]
    placement_list: List[PlacementMaterial] = evidence["placement"]

    # 2. Score & rank alumni
    matches = compute_deterministic_recommendations(student, alumni_list)
    top_matches = matches[:TOP_ALUMNI_COUNT]

    # 3. Aggregate evidence across top alumni (Issue 7)
    agg = aggregate_alumni_evidence(alumni_list, top_n=TOP_ALUMNI_COUNT)

    # 4. Detect intent
    intent = _detect_query_intent(question)

    # 5. Log generation context (Issue 12)
    _log_generation_context(state, evidence, top_matches, agg, intent)

    # 6. Build prompt
    prompt = _build_dynamic_prompt(question, intent, student, top_matches, interview_list, placement_list, agg, state)

    # 7. LLM generation with retry
    current_prompt = prompt
    response = ""
    for attempt in range(max_retries + 1):
        print(f"🤖 [DYNAMIC GENERATION] LLM Call (Attempt {attempt + 1}/{max_retries + 1} | Intent: {intent})")
        response = llm_call(current_prompt)
        is_valid, reasons = _validate_response(response, evidence, top_matches, intent)
        if is_valid:
            print(f"✅ [VALIDATION] Passed on attempt {attempt + 1}")
            return response
        else:
            print(f"❌ [VALIDATION] Failed attempt {attempt + 1}: {reasons}")
            if attempt < max_retries:
                feedback = (
                    f"\n\nCRITICAL FIX REQUIRED (Attempt {attempt + 1} failed):\n"
                    + "\n".join(f"- {r}" for r in reasons)
                    + "\n\nPlease regenerate using only the retrieved evidence above."
                )
                current_prompt = prompt + feedback

    print("⚠️ [VALIDATION] Max retries reached. Returning best response.")
    return response


# ---------------------------------------------------------------------------
# Logging (Issue 12)
# ---------------------------------------------------------------------------

def _log_generation_context(state, evidence, matches, agg, intent):
    student: StudentProfile = evidence["student"]
    print("\n" + "═" * 60)
    print("📊 [PROMPT BUILDER SUMMARY] Generation Context")
    print("═" * 60)
    print(f"  • Intent               : {intent}")
    print(f"  • Student Resume       : {'Yes' if student.has_resume else 'No'}")
    print(f"  • Student Projects     : {len(student.projects)}")
    print(f"  • Student Skills       : {len(student.skills)}")
    print(f"  • Alumni Evidence      : {len(evidence['alumni'])} profiles extracted")
    print(f"  • Top Matches          : {len(matches)}")
    for m in matches:
        bd = m.get("score_breakdown", {})
        print(f"    → {m['alumni_name']} @ {m['company']} | Score={m['match_score']}% "
              f"[Sk={bd.get('skill_overlap_pct',0)}% "
              f"Te={bd.get('tech_overlap_pct',0)}% "
              f"Pr={bd.get('project_similarity_pct',0)}%]")
    print(f"  • Interview Evidence   : {len(evidence['interviews'])} items")
    print(f"  • Placement Materials  : {len(evidence['placement'])} items")
    print(f"  • Common Skills (agg)  : {agg.get('common_skills', [])[:8]}")
    print(f"  • Common Tech (agg)    : {agg.get('common_technologies', [])[:8]}")
    print("═" * 60 + "\n")


# ---------------------------------------------------------------------------
# Prompt Builder (Issues 9, 10, 11)
# ---------------------------------------------------------------------------

def _build_dynamic_prompt(
    question: str,
    intent: str,
    student: StudentProfile,
    matches: List[Dict[str, Any]],
    interviews: List[InterviewExperience],
    placement: List[PlacementMaterial],
    agg: Dict[str, Any],
    state: Dict[str, Any],
) -> str:
    history_text = "\n".join(state.get("history", [])[-6:])

    # ── Student block (Issue 9) ──────────────────────────────────────────
    if student.has_resume:
        proj_lines = ""
        if student.projects:
            for p in student.projects:
                techs = ", ".join(p.get("technologies", []))
                proj_lines += f"\n   • {p['title']} [{p['domain']}]"
                if p.get("description"):
                    proj_lines += f"\n     Desc: {p['description'][:120]}"
                if techs:
                    proj_lines += f"\n     Tech: {techs}"
                if p.get("impact"):
                    proj_lines += f"\n     Impact: {p['impact'][:80]}"
        else:
            proj_lines = "\n   (No structured project blocks detected — check resume excerpt below)"

        student_str = (
            f"Evidence ID : {student.evidence_id}\n"
            f"Name        : {student.name}\n"
            f"Department  : {student.department}\n"
            f"Education   : {'; '.join(student.education[:3]) or 'Not found'}\n"
            f"Career Goal : {student.career_objective or 'Not specified'}\n"
            f"Skills      : {', '.join(sorted(student.skills)) or 'None specified'}\n"
            f"Technologies: {', '.join(sorted(student.technologies)) or 'None specified'}\n"
            f"Projects    :{proj_lines}\n"
            f"Certifications: {', '.join(student.certifications) or 'None'}\n"
            f"Achievements: {', '.join(student.achievements[:3]) or 'None'}\n"
            f"Resume Excerpt:\n{student.raw_text[:700]}"
        )
    else:
        student_str = (
            f"Evidence ID : {student.evidence_id} | Name: {student.name} | "
            f"Department: {student.department} | "
            f"Skills: {', '.join(sorted(student.skills)) or 'None specified'}\n"
            "Note: Student has NOT uploaded a resume yet."
        )

    # ── Alumni blocks (Issues 9, 10, 11) ────────────────────────────────
    if matches:
        match_blocks = []
        for m in matches:
            # Score breakdown explanation
            bd = m.get("score_breakdown", {})
            breakdown_str = (
                f"Skill overlap: {bd.get('skill_overlap_pct', 0)}%  |  "
                f"Technology overlap: {bd.get('tech_overlap_pct', 0)}%  |  "
                f"Project similarity: {bd.get('project_similarity_pct', 0)}%  |  "
                f"Education: {bd.get('education_pct', 0)}%  |  "
                f"Experience: {bd.get('experience_pct', 0)}%"
            )

            # Projects
            proj_str = ""
            if m.get("projects"):
                for p in m["projects"][:4]:
                    t = p.get("title", "Project")
                    desc = p.get("description", "")[:100]
                    techs = ", ".join(p.get("technologies", [])[:6])
                    proj_str += f"\n     • {t}: {desc}"
                    if techs:
                        proj_str += f" [Tech: {techs}]"
            else:
                proj_str = "\n     No structured project data"

            # Experience
            exp_str = ""
            if m.get("experience"):
                for e in m["experience"][:2]:
                    exp_str += f"\n     • {e.get('role', '')} @ {e.get('company', '')} ({e.get('duration', '')})"
            else:
                exp_str = "\n     Not explicitly listed"

            # Project comparison
            proj_cmp_str = ""
            for cmp in m.get("matching_projects", [])[:3]:
                proj_cmp_str += (
                    f"\n     Student: {cmp.get('student_project', '?')} "
                    f"↓ Alumni: {cmp.get('alumni_project', '?')}"
                    f"\n       Shared Tech : {', '.join(cmp.get('shared_tech', [])) or 'None'}"
                    f"\n       Missing Tech: {', '.join(cmp.get('missing_tech', [])) or 'None'}"
                    f"\n       Similarity  : {cmp.get('similarity_pct', 0)}%"
                )

            # Why selected (Issue 10)
            why_str = m.get("why_selected", "Domain alignment with student profile")

            match_blocks.append(
                f"[Evidence ID: {m['evidence_id']}]\n"
                f"  Alumni Name   : {m['alumni_name']}\n"
                f"  Company       : {m['company']}\n"
                f"  Role          : {m['role']}\n"
                f"  Designation   : {m.get('designation', m['role'])}\n"
                f"  Education     : {'; '.join(m.get('education', [])[:2]) or 'Not listed'}\n"
                f"  Career Path   : {' → '.join(m.get('career_path', [])) or 'Not listed'}\n"
                f"  Match Score   : {m['match_score']}% (Confidence: {m['confidence_level']})\n"
                f"  Score Breakdown:\n    {breakdown_str}\n"
                f"  Why Selected  : {why_str}\n"
                f"  Shared Skills : {', '.join(m.get('matching_skills', [])) or 'None matched'}\n"
                f"  Missing Skills: {', '.join(m.get('missing_skills', [])[:8]) or 'None'}\n"
                f"  Technologies  : {', '.join(m.get('technologies', [])[:10])}\n"
                f"  Tech Overlap  : {', '.join(m.get('tech_overlap', [])) or 'None'}\n"
                f"  Missing Tech  : {', '.join(m.get('missing_tech', [])[:8]) or 'None'}\n"
                f"  Certifications: {', '.join(m.get('certifications', [])) or 'None'}\n"
                f"  Achievements  : {'; '.join(m.get('achievements', [])[:2]) or 'None'}\n"
                f"  Experience    :{exp_str}\n"
                f"  Projects      :{proj_str}\n"
                f"  Project Comparison (Student ↔ Alumni):{proj_cmp_str or chr(10) + '     No student projects to compare'}\n"
                f"  Resume Excerpt: {m['raw_text'][:350]}"
            )
        alumni_str = "\n\n".join(match_blocks)
    else:
        alumni_str = "This information is not available in the institutional knowledge base."

    # ── Aggregated Insights Block (Issue 7, 11) ──────────────────────────
    if agg:
        agg_str = (
            f"Alumni Count Analysed : {agg.get('alumni_count', 0)}\n"
            f"Common Skills         : {', '.join(agg.get('common_skills', [])) or 'Insufficient data'}\n"
            f"Common Technologies   : {', '.join(agg.get('common_technologies', [])) or 'Insufficient data'}\n"
            f"Frequent Companies    : {', '.join(agg.get('frequent_companies', [])) or 'N/A'}\n"
            f"Shared Career Paths   : {', '.join(agg.get('shared_career_paths', [])) or 'N/A'}\n"
            f"Common Project Domains: {', '.join(agg.get('common_project_domains', [])) or 'N/A'}"
        )
    else:
        agg_str = "This information is not available in the institutional knowledge base."

    # ── Interview Block (Issues 5, 9) ────────────────────────────────────
    if interviews:
        int_blocks = []
        for iv in interviews[:4]:
            int_blocks.append(
                f"[Evidence ID: {iv.evidence_id}]\n"
                f"  Company   : {iv.company}\n"
                f"  Role      : {iv.role}\n"
                f"  Difficulty: {iv.difficulty}\n"
                f"  Rounds    : {', '.join(iv.rounds) or 'Not listed'}\n"
                f"  Topics    : {', '.join(iv.topics) or 'Not listed'}\n"
                f"  FAQs      : {'; '.join(iv.faqs[:3]) or 'Not listed'}\n"
                f"  Prep Tips : {'; '.join(iv.prep_tips[:3]) or 'Not listed'}\n"
                f"  Details   : {iv.raw_text[:350]}"
            )
        interview_str = "\n\n".join(int_blocks)
    else:
        interview_str = "This information is not available in the institutional knowledge base."

    # ── Placement Block ───────────────────────────────────────────────────
    if placement:
        placement_str = "\n".join(
            f"[{p.evidence_id}] {p.title}: {p.raw_text[:300]}" for p in placement[:3]
        )
    else:
        placement_str = "This information is not available in the institutional knowledge base."

    prompt = f"""You are an experienced Senior University Placement Mentor conducting a personalised placement strategy session.
You have structured evidence retrieved from the institutional knowledge base. Use ONLY this evidence.

=== RETRIEVED STRUCTURED EVIDENCE ===

[STUDENT PROFILE]
{student_str}

[PRE-COMPUTED ALUMNI MATCHES — Top {len(matches)} Ranked by Python Scoring Engine]
{alumni_str}

[AGGREGATED INSIGHTS ACROSS TOP ALUMNI]
{agg_str}

[INTERVIEW EXPERIENCES]
{interview_str}

[PLACEMENT MATERIALS]
{placement_str}

[CONVERSATION HISTORY]
{history_text}

[STUDENT QUESTION]
{question}

=== SENIOR MENTOR INSTRUCTIONS ===

QUERY INTENT DETECTED: {intent}

RULE 1 — HALLUCINATION PREVENTION (STRICT):
- NEVER invent alumni names, companies, projects, interview rounds, or recommendations.
- If a field says "Not listed" or "None", do NOT guess or fabricate.
- If evidence is unavailable for a section, state: "This information is not available in the institutional knowledge base."

RULE 2 — OUTPUT STYLE:
- Use rich Markdown with headers, tables, and bullet points.
- Skill comparisons: always use a Markdown TABLE with ✅ (student has) and ❌ (student missing).
- Keep each section focused and concise.

RULE 3 — MANDATORY STRUCTURE (based on intent: {intent}):
Include only sections that have evidence. Suggested order:

### 📋 Student Summary
Summarise the student's actual resume. Mention projects, skills, technologies.
Do NOT say "no projects" if the student has projects listed above.

### 🎓 Relevant Alumni
For EACH matched alumni profile (show all {len(matches)} if available):
  - Name | Company | Role
  - Match Score: XX%  (explain: "Skill overlap: X%, Tech overlap: Y%, Project similarity: Z%")
  - **Why Selected**: [use the Why Selected field verbatim or paraphrase it]
  - Shared Skills: [list]
  - Missing Skills: [list — these are your gaps]
  - Projects: [list from evidence]

### 📊 Skill & Technology Comparison Table
Present a Markdown TABLE:
| Skill/Technology | You (Student) | Alumni (aggregate) |
|------------------|---------------|--------------------|
Show ✅ for present and ❌ for missing. Include ALL skills and technologies from evidence.

### 🔁 Project Comparison
For each student project, show:
  Student Project → Closest Alumni Project
  Shared Technologies | Missing Technologies | Similarity %
Do NOT invent projects.

### 🌐 Common Patterns Across Alumni
Based on aggregated evidence:
  - Common skills that successful alumni share
  - Common technologies
  - Frequent companies

### 🎯 Evidence-Backed Recommendations
For each recommendation:
  - State the recommendation
  - **Why**: cite which alumni profiles support this (Issue 11)
  - **Confidence**: High / Medium / Low based on how many alumni share this pattern

### 🗺️ Roadmap
  - Immediate Priorities (next 2 weeks)
  - Short-Term Goals (1–3 months)
  - Long-Term Goals (3–12 months)
Each goal must reference specific skills/technologies/companies from the evidence.

### 🧠 Interview Preparation (only if interview evidence exists)
  - Company | Role | Difficulty
  - Rounds breakdown
  - Topics to focus on
  - FAQs from retrieved evidence

Produce your response in clean Markdown now:"""

    return prompt


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_response(
    response: str,
    evidence: Dict[str, Any],
    matches: List[Dict[str, Any]],
    intent: str,
) -> Tuple[bool, List[str]]:
    reasons = []
    resp_lower = response.lower()

    # Banned generic phrases
    banned = ["our alumni", "you should learn python", "machine learning requires",
               "to become an ml engineer"]
    for phrase in banned:
        if phrase in resp_lower:
            reasons.append(f"Contains forbidden generic phrase: '{phrase}'")

    # At least one retrieved alumni name must be mentioned
    valid_matches = [m for m in matches if m["alumni_name"] not in ("Alumni Senior", "Unknown Alumni", "")]
    if valid_matches and intent in ("skill_gap", "alumni_comparison", "career_guidance", "domain_guidance", "general_mentorship"):
        found = any(m["alumni_name"].lower() in resp_lower for m in valid_matches)
        if not found:
            reasons.append(f"Failed to reference any retrieved alumni (e.g. '{valid_matches[0]['alumni_name']}')")

    # Interview-prep intent must mention a retrieved company
    interviews: List[InterviewExperience] = evidence.get("interviews", [])
    if interviews and intent == "interview_prep":
        real = [iv for iv in interviews if iv.company and iv.company not in ("Unknown Company", "Interviewed Company")]
        if real and not any(iv.company.lower() in resp_lower for iv in real):
            reasons.append("Failed to mention any retrieved interview company.")

    return len(reasons) == 0, reasons
