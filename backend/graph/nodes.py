"""
LangGraph Nodes for the Placement Platform.
Each node handles a specific retrieval or generation step.
"""

from graph.state import PlacementState
from knowledge_base.collections import search_kb, search_student_resumes
from llm import llm_call


def retrieve_kb_node(state: PlacementState) -> PlacementState:
    """Retrieve relevant documents from the institutional knowledge base."""
    query = state["question"]
    career_goal = state.get("career_goal", "")
    if career_goal:
        query = f"{query} {career_goal}"

    results = search_kb(query, "institutional_kb", k=5)
    context = "\n\n".join([r["document"] for r in results]) if results else ""

    return {**state, "context_kb": context}


def retrieve_resume_node(state: PlacementState) -> PlacementState:
    """Retrieve the student's own resume context for personalization."""
    user_id = state.get("user_id", "")
    if not user_id:
        return {**state, "context_resume": ""}

    results = search_kb(
        state["question"], "student_resumes", k=3,
        where={"roll_no": user_id}
    )
    context = "\n\n".join([r["document"] for r in results]) if results else ""
    return {**state, "context_resume": context}


def retrieve_interview_node(state: PlacementState) -> PlacementState:
    """Retrieve company/role-specific interview experiences."""
    company = state.get("target_company", "")
    role = state.get("target_role", "")
    query = f"{state['question']} {company} {role}".strip()

    where = {"company": company} if company else None
    results = search_kb(query, "interview_experiences", k=5, where=where)
    context = "\n\n".join([r["document"] for r in results]) if results else ""

    return {**state, "context_interviews": context}


def mentor_node(state: PlacementState) -> PlacementState:
    """Career guidance and mentorship node."""
    history_text = "\n".join(state.get("history", [])[-10:])

    prompt = f"""You are an AI Career Mentor at a university placement cell with deep knowledge of industry hiring.

Student's Resume Profile:
{state.get('context_resume', 'No resume uploaded yet.')}

Institutional Knowledge (Alumni Profiles, Roadmaps, Placement Data):
{state.get('context_kb', '')}

Career Goal: {state.get('career_goal', 'Not specified')}

Conversation History:
{history_text}

Student's Question:
{state['question']}

Guidelines:
- Provide personalized, actionable career guidance based on the student's profile and institutional data
- Reference specific alumni success stories and roadmaps from the knowledge base
- Give structured advice with clear steps, timelines, and priorities
- Suggest specific projects, skills, and resources
- Be encouraging but realistic
- Use markdown formatting with headers, bullet points, and bold text
- If the student hasn't uploaded a resume, still provide valuable guidance from the KB"""

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def interview_prep_node(state: PlacementState) -> PlacementState:
    """Interview preparation node."""
    history_text = "\n".join(state.get("history", [])[-10:])

    prompt = f"""You are an AI Interview Coach with access to real interview experiences from placed students.

Student's Resume:
{state.get('context_resume', 'No resume uploaded yet.')}

Interview Experiences from Seniors:
{state.get('context_interviews', 'No specific experiences found.')}

Related Knowledge Base:
{state.get('context_kb', '')}

Target Company: {state.get('target_company', 'Not specified')}
Target Role: {state.get('target_role', 'Not specified')}

Conversation History:
{history_text}

Student's Question:
{state['question']}

Guidelines:
- Provide company-specific interview preparation based on real senior experiences
- List expected questions with preparation strategies
- Give round-wise preparation guidance
- Include important topics and concepts to revise
- Suggest mock interview questions based on the student's resume
- Reference actual interview experiences from the knowledge base
- Use markdown with clear sections and formatting"""

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def ats_node(state: PlacementState) -> PlacementState:
    """ATS scoring and resume analysis node."""
    prompt = f"""You are an expert ATS (Applicant Tracking System) analyzer and resume reviewer.

Student's Resume Content:
{state.get('context_resume', 'No resume uploaded.')}

ATS Best Practices from Knowledge Base:
{state.get('context_kb', '')}

Student's Question:
{state['question']}

Analyze the resume and provide:
1. **ATS Score: X/100**
2. **Category Breakdown:**
   - Format & Structure (0-20): Is it ATS-parseable?
   - Keywords & Skills (0-20): Are relevant tech keywords present?
   - Experience & Impact (0-20): Are achievements quantified?
   - Education & Certifications (0-20): Are they well-presented?
   - Overall Presentation (0-20): Grammar, consistency, clarity
3. **Keywords Found:** List detected technical keywords
4. **Missing Keywords:** Suggest important keywords to add
5. **Specific Improvements:** Actionable before/after examples
6. **Overall Assessment:** 2-3 sentence summary

Use markdown formatting. Be specific with examples from the actual resume."""

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def resume_match_node(state: PlacementState) -> PlacementState:
    """Resume matching against successful alumni profiles."""
    prompt = f"""You are an AI Resume Matching system comparing a student against successfully placed alumni.

Student's Current Resume:
{state.get('context_resume', 'No resume uploaded.')}

Successfully Placed Alumni Profiles:
{state.get('context_kb', '')}

Student's Question:
{state['question']}

Provide:
1. **Match Analysis:** How does this student compare to placed alumni?
2. **Skill Gap Analysis:** What skills are missing compared to successful candidates?
3. **Matching Profiles:** Which alumni profiles are most similar?
4. **Improvement Plan:** Specific steps to bridge the gap
5. **Strength Assessment:** What the student already has going for them
6. **Timeline:** Realistic timeline to become placement-ready

Use markdown. Reference specific alumni profiles and their achievements."""

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def memory_node(state: PlacementState) -> PlacementState:
    """Update conversation history."""
    updated = state.get("history", []) + [
        f"Student: {state['question']}",
        f"AI: {state['answer']}",
    ]
    return {**state, "history": updated}
