from graph.state import PlacementState
# Legacy direct-collection helpers (kept for search_kb / search_student_resumes used below)
from knowledge_base.collections import (
    search_kb, search_student_resumes,
    search_alumni_resumes, search_placement_materials,
)
from llm import llm_call
from config import ALUMNI_REFINE_TOP_K

# Phase 2: Unified Retrieval Engine & Context Builder
from knowledge_base.retrieval import (
    retrieve,
    retrieve_resumes,
    retrieve_interview_experiences,
    retrieve_placement_materials as kb_retrieve_placement,
)
from knowledge_base.context_builder import build_context

from generation.query_rewriter import get_query_rewriter
from generation.dynamic_mentor import generate_dynamic_mentor_response


# Import 6-stage RAG pipeline functions from the shared RAG_pipeline (rag_core)
from rag_core.stages.rerank import rerank_chunks
from rag_core.stages.refine import refine_chunks


# ──────────────────────────────────────────────────────────
# Phase 3: Query Rewriting Node
# ──────────────────────────────────────────────────────────

def rewrite_query_node(state: PlacementState) -> PlacementState:
    """
    Phase 3: Dedicated query rewriting node.

    Runs BEFORE retrieve_all_node in the LangGraph pipeline.
    Uses the production QueryRewriter from generation/query_rewriter.py.

    - Stores original query in state["original_query"] for transparency.
    - Stores rewritten query in state["rewritten_query"] for downstream use.
    - The question field is NOT mutated — retrieval nodes read rewritten_query.
    """
    query = state["question"]
    career_goal = state.get("career_goal", "")
    target_company = state.get("target_company", "")
    target_role = state.get("target_role", "")

    context_hint_parts = []
    if career_goal:
        context_hint_parts.append(f"career goal is {career_goal}")
    if target_company:
        context_hint_parts.append(f"target company is {target_company}")
    if target_role:
        context_hint_parts.append(f"target role is {target_role}")
    context_hint = ", ".join(context_hint_parts) if context_hint_parts else ""

    rewriter = get_query_rewriter()
    result = rewriter.rewrite(query, context_hint=context_hint)

    print(f"\n[Phase 3 | QueryRewriter] Original   : '{result.original}'")
    print(f"[Phase 3 | QueryRewriter] Rewritten  : '{result.rewritten}'")
    print(f"[Phase 3 | QueryRewriter] Was Rewritten: {result.was_rewritten}")
    print(f"[Phase 3 | QueryRewriter] Reason     : {result.reason}")
    if result.abbreviations_expanded:
        print(f"[Phase 3 | QueryRewriter] Abbrevs    : {result.abbreviations_expanded}")

    return {
        **state,
        "original_query": result.original,
        "rewritten_query": result.rewritten,
    }


# ──────────────────────────────────────────────────────────
# Retrieval Nodes — Unified
# ──────────────────────────────────────────────────────────

def retrieve_all_node(state: PlacementState) -> PlacementState:
    """
    Unified multi-collection retrieval using the Phase 2 Retrieval Engine.
    Delegates to knowledge_base/retrieval.py for all ChromaDB operations.

    Reads rewritten_query from state (set by the upstream rewrite_query_node).
    Falls back to the raw question if rewritten_query is not populated.
    """
    # Use the Phase 3 rewritten query if available; else fall back to raw question
    rewritten_query = state.get("rewritten_query") or state["question"]
    user_id = state.get("user_id", "")
    target_company = state.get("target_company", "")
    target_role = state.get("target_role", "")

    print(f"\n[RAG DEBUG] Original Query  : {state.get('original_query', state['question'])}")
    print(f"[RAG DEBUG] Rewritten Query : {rewritten_query}")

    def _result_to_rag_chunk(r) -> dict:
        """Convert RetrievalResult or legacy dict to RAG-compatible chunk dict."""
        if hasattr(r, "content"):
            # Enrich metadata with outer RetrievalResult fields that aren't in ChromaDB raw metadata
            enriched_meta = dict(r.metadata or {})
            if not enriched_meta.get("collection"):
                enriched_meta["collection"] = r.collection or ""
            if not enriched_meta.get("source_file"):
                enriched_meta["source_file"] = r.source_file or ""
            if not enriched_meta.get("section"):
                enriched_meta["section"] = r.section or ""
            if not enriched_meta.get("document_type"):
                enriched_meta["document_type"] = r.document_type or ""
            return {"text": r.content, "distance": r.distance, "metadata": enriched_meta}
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

    print(f"[RAG DEBUG] Fetched: KB={len(kb_chunks)}, Resume={len(resume_chunks)}, Alumni={len(alumni_chunks)}, Interviews={len(interview_chunks)}, Placement={len(materials_chunks)}")
    if not resume_chunks:
        print(f"[RAG DEBUG] ⚠️  Resume context EMPTY for user_id='{user_id}' — check upload flow or re-upload")
    else:
        print(f"[RAG DEBUG] ✅  Resume context found: {len(resume_chunks)} chunks for user_id='{user_id}'")
    if not alumni_chunks:
        print(f"[RAG DEBUG] ⚠️  Alumni context EMPTY for query='{rewritten_query}'")


    # ── Stage 3: Reranking ────────────────────────────────────────────────────
    reranked_kb = rerank_chunks(rewritten_query, kb_chunks)
    reranked_resume = rerank_chunks(rewritten_query, resume_chunks)
    reranked_alumni = rerank_chunks(rewritten_query, alumni_chunks)
    reranked_interviews = rerank_chunks(rewritten_query, interview_chunks)
    reranked_placement = rerank_chunks(rewritten_query, materials_chunks)

    print(f"[RAG DEBUG] Reranked: KB={len(reranked_kb)}, Resume={len(reranked_resume)}, Alumni={len(reranked_alumni)}, Interviews={len(reranked_interviews)}, Placement={len(reranked_placement)}")

    # ── Stage 4: Refinement ───────────────────────────────────────────────────
    # Alumni uses ALUMNI_REFINE_TOP_K (default 8) so multiple distinct alumni
    # profiles survive into evidence extraction (Issue 3 fix).
    refined_kb = refine_chunks(reranked_kb, top_k=4)
    refined_resume = refine_chunks(reranked_resume, top_k=4)
    refined_alumni = refine_chunks(reranked_alumni, top_k=ALUMNI_REFINE_TOP_K)
    refined_interviews = refine_chunks(reranked_interviews, top_k=4)
    refined_placement = refine_chunks(reranked_placement, top_k=4)

    print(f"[RAG DEBUG] Refined: KB={len(refined_kb)}, Resume={len(refined_resume)}, Alumni={len(refined_alumni)}, Interviews={len(refined_interviews)}, Placement={len(refined_placement)}")

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
# Retrieval Nodes — New ->File-Based Collections
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
    """Career guidance and mentorship node — Dynamic Retrieval-Driven Generator."""
    print(f"\n[RAG DEBUG] --- Generation Node: mentor_node (Dynamic) ---")
    answer = generate_dynamic_mentor_response(state)
    return {**state, "answer": answer}




def interview_prep_node(state: PlacementState) -> PlacementState:
    """Interview preparation node."""
    history_text = "\n".join(state.get("history", [])[-10:])
    student_name = state.get('student_name', 'Student')
    target_company = state.get('target_company', 'Not specified')
    target_role = state.get('target_role', 'Not specified')
    resume_context = state.get('context_resume', 'No resume uploaded yet.')
    interview_context = state.get('context_interviews', '')
    alumni_context = state.get('context_alumni', '')
    kb_context = state.get('context_kb', '')
    has_resume = resume_context and resume_context.strip() != 'No resume uploaded yet.'

    prompt = f"""You are a personalised AI Interview Coach with access to real interview experiences from placed seniors.

=== STUDENT PROFILE ===
Name: {student_name}
Department: {state.get('student_dept', 'Unknown')}
Known Skills: {state.get('student_skills', 'None specified')}
Target Company: {target_company}
Target Role: {target_role}

=== STUDENT'S UPLOADED RESUME ===
{resume_context}

=== RETRIEVED INTERVIEW EXPERIENCES (Real Seniors) ===
{interview_context if interview_context else 'No specific interview experiences found.'}

=== RETRIEVED ALUMNI CAREER PROFILES ===
{alumni_context if alumni_context else ''}

=== KNOWLEDGE BASE ===
{kb_context}

=== CONVERSATION HISTORY ===
{history_text}

=== STUDENT'S QUESTION ===
{state['question']}

=== ABSOLUTE RULES ===

1. NEVER say "seniors" generically. ALWAYS name specific people.
   WRONG: "A senior faced this question in Round 2."
   RIGHT: "Aditya Kumar (Amazon, SDE) was asked: 'Explain HashMap vs HashSet'"

2. For every company mentioned in interview experiences context:
   - List the EXACT rounds (e.g., OA, Technical 1, HR)
   - List ACTUAL questions asked (from context)
   - List ACTUAL topics tested (from context)
   - Name the senior who shared the experience

3. RESUME-BASED MOCK QUESTIONS (if resume uploaded):
   - Generate mock interview questions based on the student's actual skills and projects.
   - Format: "Based on your [project/skill], you may be asked: [question]"

4. If NO resume uploaded: acknowledge, still provide interview guidance from seniors.

5. DO NOT confuse student with alumni/seniors.

6. STRUCTURE response exactly:
   ## 🏭 Company Overview: {target_company}
   ## 📝 Round-by-Round Breakdown
   ## ❓ Actual Questions Asked (from seniors)
   ## 📚 Topics to Prepare
   ## 🎯 Mock Questions for You (based on your resume)
   ## 🗓️ Preparation Timeline
   ## 🔗 Resources

7. Every point must cite actual names and data from the context. Never invent."""

    print(f"\n[RAG DEBUG] --- Generation Node: interview_prep_node ---")
    print(f"[RAG DEBUG] Has student resume: {has_resume}")
    print(f"[RAG DEBUG] Interview context length: {len(interview_context)} chars")
    print(f"[RAG DEBUG] Target: {target_company} / {target_role}")

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def resume_match_node(state: PlacementState) -> PlacementState:
    """Resume match — compare student resume against successfully placed alumni."""
    student_name = state.get('student_name', 'Student')
    student_skills = state.get('student_skills', 'None specified')
    resume_context = state.get('context_resume', 'No resume uploaded.')
    alumni_context = state.get('context_alumni', state.get('context_kb', ''))
    placement_context = state.get('context_placement', '')
    has_resume = resume_context and resume_context.strip() not in ('No resume uploaded.', 'No resume uploaded yet.')

    prompt = f"""You are a personalised AI Resume Match Analyst. You compare a student's profile against successfully placed alumni.

=== STUDENT PROFILE ===
Name: {student_name}
Department: {state.get('student_dept', 'Unknown')}
Known Skills: {student_skills}

=== STUDENT'S UPLOADED RESUME ===
{resume_context}

=== SUCCESSFULLY PLACED ALUMNI PROFILES ===
{alumni_context if alumni_context else 'No alumni profiles retrieved.'}

=== PLACEMENT RESOURCES ===
{placement_context}

=== STUDENT'S QUESTION ===
{state['question']}

=== ABSOLUTE RULES ===

1. NEVER say "some alumni" or "placed students". Name EVERY person you reference.
   Format: "[Name] ([Company], [Role]) — [their skills/projects]"

2. EXTRACT from student resume (if uploaded):
   - Skills the student has
   - Projects the student has done
   - Education and experience

3. EXTRACT from each alumni in context:
   - Skills
   - Projects
   - Company and role

4. COMPARISON TABLE (always include):
   | Category | Student ({student_name}) | Alumni Name | Gap |
   Show: matching skills ✓, missing skills ✗, matching projects ✓, missing projects ✗

5. If NO resume uploaded:
   Say so clearly, then still provide alumni analysis with concrete recommendations.

6. DO NOT confuse the student with alumni.

7. STRUCTURE response exactly:
   ## 📄 Resume Analysis
   ## 👥 Most Similar Alumni Profiles
   ## 📊 Skills Comparison Table
   ## 🛠️ Skill Gaps
   ## 📦 Project Gaps
   ## 🏭 Recommended Companies (based on current profile)
   ## 🗓️ Action Plan
   ## ⏰ Timeline to Placement Readiness"""

    print(f"\n[RAG DEBUG] --- Generation Node: resume_match_node ---")
    print(f"[RAG DEBUG] Has student resume: {has_resume}")
    print(f"[RAG DEBUG] Alumni context length: {len(alumni_context)} chars")

    answer = llm_call(prompt)
    return {**state, "answer": answer}


def memory_node(state: PlacementState) -> PlacementState:
    """Update conversation history."""
    updated = state.get("history", []) + [
        f"Student: {state['question']}",
        f"AI: {state['answer']}",
    ]
    return {**state, "history": updated}
