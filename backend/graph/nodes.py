from graph.state import PlacementState
# Legacy direct-collection helpers (kept for search_kb / search_student_resumes used below)
from knowledge_base.collections import (
    search_kb, search_student_resumes,
    search_alumni_resumes, search_placement_materials,
)
from llm import llm_call

# Phase 2: Unified Retrieval Engine & Context Builder
from knowledge_base.retrieval import (
    retrieve,
    retrieve_resumes,
    retrieve_interview_experiences,
    retrieve_placement_materials as kb_retrieve_placement,
)
from knowledge_base.context_builder import build_context

# Import 6-stage RAG pipeline functions from the shared RAG_pipeline (rag_core)
from rag_core.stages.rewrite import rewrite_query
from rag_core.stages.rerank import rerank_chunks
from rag_core.stages.refine import refine_chunks


# ──────────────────────────────────────────────────────────
# Retrieval Nodes — Unified
# ──────────────────────────────────────────────────────────

def retrieve_all_node(state: PlacementState) -> PlacementState:
    """
    Unified multi-collection retrieval using the Phase 2 Retrieval Engine.
    Delegates to knowledge_base/retrieval.py for all ChromaDB operations.
    Still applies query rewriting, reranking, and refinement downstream.
    """
    query = state["question"]
    user_id = state.get("user_id", "")
    career_goal = state.get("career_goal", "")
    target_company = state.get("target_company", "")
    target_role = state.get("target_role", "")

    # ── Stage 1: Query Rewriting ──────────────────────────────────────────────
    context_hint = f"career goal is {career_goal}, target company is {target_company}, target role is {target_role}"
    rewritten_query = rewrite_query(query, context_hint=context_hint)
    print(f"\n[RAG DEBUG] Original Query: {query}")
    print(f"[RAG DEBUG] Rewritten Query: {rewritten_query}")

    def _result_to_rag_chunk(r) -> dict:
        """Convert RetrievalResult or legacy dict to RAG-compatible chunk dict."""
        if hasattr(r, "content"):
            return {"text": r.content, "distance": r.distance, "metadata": r.metadata}
        elif isinstance(r, dict):
            text = r.get("document") or r.get("text") or r.get("page_content") or str(r)
            return {"text": text, "distance": r.get("distance", 0.5), "metadata": r.get("metadata", {})}
        return {"text": str(r), "distance": 0.5, "metadata": {}}

    # ── Stage 2: Retrieve from all collections via Retrieval Engine ───────────
    # 2.1 Institutional Knowledge Base (direct search_kb — not in retrieval engine scope)
    kb_results = search_kb(rewritten_query, "institutional_kb", k=8)
    kb_chunks = [_result_to_rag_chunk(r) for r in kb_results]

    # 2.2 Student's Own Resume (student-specific, uses roll_no filter)
    resume_chunks = []
    if user_id:
        try:
            from services.rag_adapter import ResumeRagAdapter
            adapter = ResumeRagAdapter()
            resume_results = adapter.get_resume_context(user_id, query=rewritten_query)
            resume_chunks = [_result_to_rag_chunk(r) for r in resume_results]
        except Exception as e:
            print(f"⚠️ Failed to get resume context via adapter: {e}")

    # 2.3 Alumni Resumes — via Retrieval Engine
    alumni_response = retrieve_resumes(
        query=rewritten_query, top_k=8,
        company=target_company if target_company else None,
    )
    alumni_chunks = [_result_to_rag_chunk(r) for r in alumni_response.results]

    # 2.4 Interview Experiences — via Retrieval Engine
    interview_response = retrieve_interview_experiences(
        query=rewritten_query, top_k=8,
        company=target_company if target_company else None,
    )
    interview_chunks = [_result_to_rag_chunk(r) for r in interview_response.results]

    # 2.5 Placement Materials — via Retrieval Engine
    materials_response = kb_retrieve_placement(query=rewritten_query, top_k=8)
    materials_chunks = [_result_to_rag_chunk(r) for r in materials_response.results]

    print(f"[RAG DEBUG] Retrieved Chunks: KB={len(kb_chunks)}, Resume={len(resume_chunks)}, Alumni={len(alumni_chunks)}, Interviews={len(interview_chunks)}, Placement={len(materials_chunks)}")

    # ── Stage 3: Reranking ────────────────────────────────────────────────────
    reranked_kb = rerank_chunks(rewritten_query, kb_chunks)
    reranked_resume = rerank_chunks(rewritten_query, resume_chunks)
    reranked_alumni = rerank_chunks(rewritten_query, alumni_chunks)
    reranked_interviews = rerank_chunks(rewritten_query, interview_chunks)
    reranked_placement = rerank_chunks(rewritten_query, materials_chunks)

    print(f"[RAG DEBUG] Reranked: KB={len(reranked_kb)}, Resume={len(reranked_resume)}, Alumni={len(reranked_alumni)}, Interviews={len(reranked_interviews)}, Placement={len(reranked_placement)}")

    # ── Stage 4: Refinement ───────────────────────────────────────────────────
    refined_kb = refine_chunks(reranked_kb, top_k=4)
    refined_resume = refine_chunks(reranked_resume, top_k=4)
    refined_alumni = refine_chunks(reranked_alumni, top_k=4)
    refined_interviews = refine_chunks(reranked_interviews, top_k=4)
    refined_placement = refine_chunks(reranked_placement, top_k=4)

    print(f"[RAG DEBUG] Refined Context: KB={len(refined_kb)}, Resume={len(refined_resume)}, Alumni={len(refined_alumni)}, Interviews={len(refined_interviews)}, Placement={len(refined_placement)}")

    context_kb = "\n\n".join(refined_kb) if refined_kb else ""
    context_resume = "\n\n".join(refined_resume) if refined_resume else "No resume uploaded yet."
    context_alumni = "\n\n".join(refined_alumni) if refined_alumni else ""
    context_interviews = "\n\n".join(refined_interviews) if refined_interviews else ""
    context_placement = "\n\n".join(refined_placement) if refined_placement else ""

    source_docs = []
    for chunk_list in [reranked_kb, reranked_resume, reranked_alumni, reranked_interviews, reranked_placement]:
        for c in chunk_list[:3]:
            meta = c.get("metadata", {})
            src = meta.get("source_file") or meta.get("roll_no") or meta.get("student_name")
            if src and src not in source_docs:
                source_docs.append(src)

    print(f"[RAG DEBUG] Source documents used: {source_docs}")

    return {
        **state,
        "context_kb": context_kb,
        "context_resume": context_resume,
        "context_alumni": context_alumni,
        "context_interviews": context_interviews,
        "context_placement": context_placement,
        "rewritten_query": rewritten_query,
        "source_documents": source_docs,
    }


# ──────────────────────────────────────────────────────────
# Retrieval Nodes — Existing
# ──────────────────────────────────────────────────────────

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
        return {**state, "context_resume": "No resume uploaded yet."}

    results = search_kb(
        state["question"], "student_resumes", k=3,
        where={"roll_no": user_id}
    )
    context = "\n\n".join([r["document"] for r in results]) if results else "No resume uploaded yet."
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


# ──────────────────────────────────────────────────────────
# Retrieval Nodes — New (File-Based Collections)
# ──────────────────────────────────────────────────────────

def retrieve_alumni_guidance_node(state: PlacementState) -> PlacementState:
    """
    Retrieve alumni resume guidance via Phase 2 Retrieval Engine.
    Delegates to retrieve_resumes() with optional company filter.
    """
    query = state["question"]
    career_goal = state.get("career_goal", "")
    target_company = state.get("target_company", "")

    search_query = " ".join(filter(None, [query, career_goal, target_company]))

    response = retrieve_resumes(
        query=search_query,
        top_k=5,
        company=target_company if target_company else None,
    )
    context = build_context(response) if response.results else ""
    return {**state, "context_alumni": context}


def retrieve_interview_experience_node(state: PlacementState) -> PlacementState:
    """
    Retrieve interview experiences via Phase 2 Retrieval Engine.
    Delegates to retrieve_interview_experiences() with optional company + role filters.
    """
    company = state.get("target_company", "")
    role = state.get("target_role", "")
    query = f"{state['question']} {company} {role} interview experience".strip()

    response = retrieve_interview_experiences(
        query=query,
        top_k=8,
        company=company if company else None,
        role=role if role else None,
    )
    context = build_context(response) if response.results else ""
    return {**state, "context_interviews": context}


def retrieve_resume_matching_node(state: PlacementState) -> PlacementState:
    """
    Cross-reference student resume vs alumni profiles via Phase 2 Retrieval Engine.
    """
    query = state["question"]

    alumni_response = retrieve_resumes(query=query, top_k=5)
    alumni_context = build_context(alumni_response) if alumni_response.results else ""

    materials_response = kb_retrieve_placement(query=query, top_k=3)
    material_context = build_context(materials_response) if materials_response.results else ""

    return {
        **state,
        "context_alumni": alumni_context,
        "context_placement": material_context,
    }


def retrieve_placement_materials_node(state: PlacementState) -> PlacementState:
    """
    Retrieve placement guides and roadmaps via Phase 2 Retrieval Engine.
    """
    query = state["question"]
    response = kb_retrieve_placement(query=query, top_k=3)
    context = build_context(response) if response.results else ""
    return {**state, "context_placement": context}


# ──────────────────────────────────────────────────────────
# Generation Nodes
# ──────────────────────────────────────────────────────────

def mentor_node(state: PlacementState) -> PlacementState:
    """Career guidance and mentorship node."""
    history_text = "\n".join(state.get("history", [])[-10:])

    prompt = f"""You are an AI Career Mentor at a university with deep knowledge of industry hiring.

Student's Name: {state.get('student_name', 'Student')}
Student's Department: {state.get('student_dept', 'Unknown')}
Student's Known Skills: {state.get('student_skills', 'None specified')}
Student's Resume Profile:
{state.get('context_resume', 'No resume uploaded yet.')}

Institutional Knowledge (Alumni Profiles, Roadmaps, Placement Data):
{state.get('context_kb', '')}

Alumni Career Journeys (Real Alumni Resumes):
{state.get('context_alumni', '')}

Placement Resources & Guides:
{state.get('context_placement', '')}

Career Goal: {state.get('career_goal', 'Not specified')}

Conversation History:
{history_text}

Student's Question:
{state['question']}

CRITICAL INSTRUCTIONS:
- You are speaking directly to {state.get('student_name', 'Student')}.
- DO NOT confuse the student with any names or profiles found in the "Alumni Career Journeys". Those are OTHER people who have graduated.
- If the "Student's Resume Profile" says "No resume uploaded yet", DO NOT assume the student has any skills or background from the alumni profiles.
- You MUST perform a comprehensive side-by-side comparison between the student's skills/projects/background and multiple retrieved alumni resumes (placed seniors) in the context.
- Clearly compare the student's profile to each of these matching seniors by name (e.g., comparing their skills/projects to Priya Sharma, Rahul Verma, Sneha Reddy, etc.), highlighting specific skill gaps or project differences.
- Reference specific alumni success stories and roadmaps, explicitly detailing the senior/alumni names (e.g., "Your senior Priya Sharma, placed at Google, did X...") and details about what they did to get placed.
- Give structured advice with clear steps, timelines, and priorities based on these senior comparisons.
- Suggest specific projects, skills, and resources matching the level of successfully placed seniors.
- Use markdown formatting with headers, bullet points, and bold text."""

    print(f"\n[RAG DEBUG] --- Generation Node: mentor_node ---")
    print(f"[RAG DEBUG] Rewritten Query: {state.get('rewritten_query', '')}")
    print(f"[RAG DEBUG] Source documents used: {state.get('source_documents', [])}")
    print(f"[RAG DEBUG] Final Prompt sent to Groq:\n{prompt[:600]}...\n")

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def interview_prep_node(state: PlacementState) -> PlacementState:
    """Interview preparation node."""
    history_text = "\n".join(state.get("history", [])[-10:])

    prompt = f"""You are an AI Interview Coach with access to real interview experiences from placed students.

Student's Name: {state.get('student_name', 'Student')}
Student's Department: {state.get('student_dept', 'Unknown')}
Student's Known Skills: {state.get('student_skills', 'None specified')}
Student's Resume:
{state.get('context_resume', 'No resume uploaded yet.')}

Interview Experiences from Seniors:
{state.get('context_interviews', 'No specific experiences found.')}

Alumni Career Profiles:
{state.get('context_alumni', '')}

Related Knowledge Base:
{state.get('context_kb', '')}

Target Company: {state.get('target_company', 'Not specified')}
Target Role: {state.get('target_role', 'Not specified')}

Conversation History:
{history_text}

Student's Question:
{state['question']}

CRITICAL INSTRUCTIONS:
- You are speaking directly to {state.get('student_name', 'Student')}.
- DO NOT confuse the student with any names or profiles found in the Alumni Career Profiles or Interview Experiences.
- If the Student's Resume says "No resume uploaded yet", DO NOT assume they have the skills of the alumni.
- Provide company-specific interview preparation based on real senior experiences, referring to seniors by name when recounting their questions or advice (e.g., "Your senior प्रिया Sharma faced this question in Round 2...")
- List expected questions with preparation strategies
- Give round-wise preparation guidance
- Include important topics and concepts to revise
- Suggest mock interview questions based on the student's resume
- Reference actual interview experiences from the knowledge base
- Use markdown with clear sections and formatting"""

    print(f"\n[RAG DEBUG] --- Generation Node: interview_prep_node ---")
    print(f"[RAG DEBUG] Rewritten Query: {state.get('rewritten_query', '')}")
    print(f"[RAG DEBUG] Source documents used: {state.get('source_documents', [])}")
    print(f"[RAG DEBUG] Final Prompt sent to Groq:\n{prompt[:600]}...\n")

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def resume_match_node(state: PlacementState) -> PlacementState:
    """Interview match — compare student resume against successfully placed alumni."""
    prompt = f"""You are an AI Interview Matching system comparing a student against successfully placed alumni.

Student's Name: {state.get('student_name', 'Student')}
Student's Department: {state.get('student_dept', 'Unknown')}
Student's Known Skills: {state.get('student_skills', 'None specified')}
Student's Current Resume:
{state.get('context_resume', 'No resume uploaded.')}

Successfully Placed Alumni Profiles:
{state.get('context_alumni', state.get('context_kb', ''))}

Placement Resources:
{state.get('context_placement', '')}

Student's Question:
{state['question']}

Provide:
1. **Match Analysis:** How does {state.get('student_name', 'Student')} compare to placed alumni? (DO NOT confuse the student with the alumni). Explicitly name matching seniors/alumni.
2. **Skill Gap Analysis:** What skills are missing compared to successful candidates?
3. **Matching Profiles:** Which alumni profiles are most similar? Cite their names and what they did/achieved.
4. **Improvement Plan:** Specific steps to bridge the gap
5. **Strength Assessment:** What the student already has going for them
6. **Timeline:** Realistic timeline to become placement-ready

Use markdown. Reference specific alumni profiles by their names and detail their achievements."""

    print(f"\n[RAG DEBUG] --- Generation Node: resume_match_node ---")
    print(f"[RAG DEBUG] Rewritten Query: {state.get('rewritten_query', '')}")
    print(f"[RAG DEBUG] Source documents used: {state.get('source_documents', [])}")
    print(f"[RAG DEBUG] Final Prompt sent to Groq:\n{prompt[:600]}...\n")

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def memory_node(state: PlacementState) -> PlacementState:
    """Update conversation history."""
    updated = state.get("history", []) + [
        f"Student: {state['question']}",
        f"AI: {state['answer']}",
    ]
    return {**state, "history": updated}
