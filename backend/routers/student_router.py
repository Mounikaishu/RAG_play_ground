"""
Student Router — Resume upload and chat for the three core PlaceAI modes.
"""

from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from typing import Optional
import shutil
import os
import traceback

from pdf_loader import load_pdf, validate_pdf_bytes, PdfValidationError
from services.rag_adapter import ResumeRagAdapter
from metadata_extractor import extract_resume_metadata

router = APIRouter(prefix="/student", tags=["Student"])

# Per-user conversation history
user_histories = {}

@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    x_session_id: Optional[str] = Header(None),
):
    """Upload or update student resume (PDF only) for the current session."""
    if not x_session_id:
        raise HTTPException(status_code=401, detail="Session ID required.")

    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    roll_no = x_session_id

    try:
        file_bytes = await file.read()
        validate_pdf_bytes(file_bytes, filename=file.filename or "upload")
        raw_text = load_pdf(file_bytes)

        # Extract metadata from raw text
        extracted = extract_resume_metadata(raw_text)
        skills_str = ", ".join(extracted.get("skills", [])) if extracted.get("skills") else "None specified"

        # Use the adapter to insert the resume (it handles chunking/embedding/storing)
        adapter = ResumeRagAdapter()
        metadata = {
            "roll_no": roll_no,
            "type": "student_resume",
            "temporary": True,
            "student_name": extracted.get("name", "Student"),
            "department": extracted.get("department", "Unknown"),
            "skills": skills_str,
        }
        result = adapter.insert_resume(raw_text, metadata=metadata)
        chunks_inserted = result.get("chunks_inserted", 0)

        return {
            "message": f"✅ Resume uploaded for this session only ({chunks_inserted} chunks). Refresh the page to start fresh.",
            "chunks": chunks_inserted,
        }
    except Exception as e:
        print(f"❌ Resume upload error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(
    question: str = Form(...),
    mode: str = Form("mentor"),  # mentor | interview_prep | resume_match
    career_goal: str = Form(""),
    target_company: str = Form(""),
    target_role: str = Form(""),
    x_session_id: Optional[str] = Header(None),
):
    """Main chat endpoint — routes through LangGraph workflow."""
    if not x_session_id:
        raise HTTPException(status_code=401, detail="Session ID required.")
    
    roll_no = x_session_id

    # Auto-extract company, role, and career goal if not supplied by form fields
    if not target_company:
        q_lower = question.lower()
        if "amazon" in q_lower:
            target_company = "Amazon"
        elif "google" in q_lower:
            target_company = "Google"
        elif "microsoft" in q_lower:
            target_company = "Microsoft"
        elif "goldman" in q_lower:
            target_company = "Goldman Sachs"
        elif "nvidia" in q_lower:
            target_company = "NVIDIA"

    # Normalize company casing to exact database values
    if target_company:
        tc_lower = target_company.strip().lower()
        if "amazon" in tc_lower:
            target_company = "Amazon"
        elif "google" in tc_lower:
            target_company = "Google"
        elif "microsoft" in tc_lower:
            target_company = "Microsoft"
        elif "goldman" in tc_lower:
            target_company = "Goldman Sachs"
        elif "nvidia" in tc_lower:
            target_company = "NVIDIA"

    if not target_role:
        q_lower = question.lower()
        if "sde" in q_lower or "software" in q_lower or "developer" in q_lower:
            target_role = "Software Engineer"
        elif "data scientist" in q_lower or "data science" in q_lower:
            target_role = "Data Scientist"
        elif "ml" in q_lower or "machine learning" in q_lower or "ai" in q_lower:
            target_role = "ML Engineer"

    if not career_goal:
        if target_role and target_company:
            career_goal = f"{target_role} at {target_company}"
        elif target_role:
            career_goal = target_role
        elif target_company:
            career_goal = f"Role at {target_company}"

    student_name = "Student"
    student_dept = "Unknown"
    student_skills = "None specified"

    try:
        adapter = ResumeRagAdapter()
        resume_chunks = adapter.get_resume_context(roll_no)
        if resume_chunks:
            # Safely extract from metadata if available
            first_chunk = resume_chunks[0]
            metadata = None
            if isinstance(first_chunk, dict):
                metadata = first_chunk.get("metadata")
            elif hasattr(first_chunk, "metadata"):
                metadata = first_chunk.metadata

            if metadata:
                student_name = metadata.get("student_name", student_name)
                student_dept = metadata.get("department", student_dept)
                student_skills = metadata.get("skills", student_skills)
    except Exception as e:
        print(f"⚠️ Failed to extract student metadata: {e}")

    history = user_histories.get(roll_no, [])

    # Convert dict-based history to list of strings for LangGraph
    graph_history = []
    for h in history:
        role = "Student" if h.get("role") == "user" else "AI"
        graph_history.append(f"{role}: {h.get('content', '')}")

    try:
        from graph.workflow import build_placement_graph
        app_graph = build_placement_graph()

        state = {
            "user_id": roll_no,
            "student_name": student_name,
            "student_dept": student_dept,
            "student_skills": student_skills,
            "question": question,
            "mode": mode,
            "context_kb": "",
            "context_resume": "",
            "context_interviews": "",
            "context_alumni": "",
            "context_placement": "",
            "answer": "",
            "history": graph_history,
            "career_goal": career_goal,
            "target_company": target_company,
            "target_role": target_role,
            "original_query": question,     # Phase 3: will be overwritten by rewrite_query_node
            "rewritten_query": question,    # Phase 3: will be overwritten by rewrite_query_node
            "source_documents": [],
        }


        final_state = app_graph.invoke(state)
        answer = final_state.get("answer", "")

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})
        user_histories[roll_no] = history[-20:]

        return {"answer": answer}
    except Exception as e:
        print(f"❌ Chat error: {e}")
        print(traceback.format_exc())
        return {"answer": f"⚠️ Something went wrong: {str(e)}"}
