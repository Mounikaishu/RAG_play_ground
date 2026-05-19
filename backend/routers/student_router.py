"""
Student Router — Resume upload, chat, ATS score, resume matching.
"""

from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from typing import Optional
import shutil
import os
import traceback

from pdf_loader import load_pdf
from services.rag_adapter import ResumeRagAdapter
import json
import re

router = APIRouter(prefix="/student", tags=["Student"])

# Per-user conversation history
user_histories = {}

@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    x_session_id: Optional[str] = Header(None),
):
    """Upload or update student resume for the current session."""
    if not x_session_id:
        raise HTTPException(status_code=401, detail="Session ID required.")
    
    roll_no = x_session_id

    file_path = f"temp_resume_{roll_no}.pdf"
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        raw_text = load_pdf(file_path)

        # Use the adapter to insert the resume (it handles chunking/embedding/storing)
        adapter = ResumeRagAdapter()
        metadata = {"roll_no": roll_no, "type": "student_resume"}
        result = adapter.insert_resume(raw_text, metadata=metadata)
        chunks_inserted = result.get("chunks_inserted", 0)

        return {
            "message": f"✅ Resume uploaded successfully ({chunks_inserted} chunks stored) for this session.",
            "chunks": chunks_inserted,
        }
    except Exception as e:
        print(f"❌ Resume upload error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@router.post("/chat")
async def chat(
    question: str = Form(...),
    mode: str = Form("mentor"),
    career_goal: str = Form(""),
    target_company: str = Form(""),
    target_role: str = Form(""),
    x_session_id: Optional[str] = Header(None),
):
    """Main chat endpoint — routes through LangGraph workflow."""
    if not x_session_id:
        raise HTTPException(status_code=401, detail="Session ID required.")
    
    roll_no = x_session_id

    student_name = "Student"
    student_dept = "Unknown"
    student_skills = "None specified"

    history = user_histories.get(roll_no, [])

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
        "history": history,
        "career_goal": career_goal,
        "target_company": target_company,
        "target_role": target_role,
    }

    try:
        # Use our RAG adapter!
        adapter = ResumeRagAdapter()
        
        system_prompt = f"""You are an AI placement mentor. 
The student's question is: {question}
Their career goal is: {career_goal} 
Target role: {target_role} at {target_company}
Provide a tailored, actionable answer."""

        answer = adapter.analyze_resume(
            query=question,
            roll_no=roll_no,
            context_hint="placement prep and student resume",
            system_prompt=system_prompt
        )
        
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})
        user_histories[roll_no] = history[-20:]
        
        return {"answer": answer}
    except Exception as e:
        print(f"❌ Chat error: {e}")
        print(traceback.format_exc())
        return {"answer": f"⚠️ Something went wrong: {str(e)}"}


@router.post("/ats-score")
async def ats_score(x_session_id: Optional[str] = Header(None)):
    """Get structured ATS score for the student's resume."""
    if not x_session_id:
        raise HTTPException(status_code=401, detail="Session ID required.")
    
    roll_no = x_session_id

    # Get resume chunks cleanly through the adapter interface
    adapter = ResumeRagAdapter()
    results = adapter.get_resume_context(roll_no)
    
    if not results:
        return {"error": "No resume uploaded. Please upload your resume first."}

    context = "\n\n".join([r["text"] for r in results])

    prompt = f"""Analyze this resume and provide an ATS score. Respond with ONLY valid JSON.

Resume Content:
{context}

Return this exact JSON format:
{{
  "overall": <0-100>,
  "categories": {{
    "format": {{"score": <0-20>, "comment": "<one sentence>"}},
    "keywords": {{"score": <0-20>, "comment": "<one sentence>"}},
    "experience": {{"score": <0-20>, "comment": "<one sentence>"}},
    "education": {{"score": <0-20>, "comment": "<one sentence>"}},
    "presentation": {{"score": <0-20>, "comment": "<one sentence>"}}
  }},
  "keywords_found": ["keyword1", "keyword2"],
  "keywords_missing": ["keyword1", "keyword2"],
  "summary": "<2 sentence assessment>"
}}"""

    raw = pipeline.generate(prompt, context)
    try:
        cleaned = re.sub(r'```json\s*', '', raw)
        cleaned = re.sub(r'```\s*', '', cleaned).strip()
        return json.loads(cleaned)
    except Exception:
        return {
            "overall": 65,
            "categories": {
                "format": {"score": 13, "comment": "Could not parse detailed score."},
                "keywords": {"score": 13, "comment": "Could not parse detailed score."},
                "experience": {"score": 13, "comment": "Could not parse detailed score."},
                "education": {"score": 13, "comment": "Could not parse detailed score."},
                "presentation": {"score": 13, "comment": "Could not parse detailed score."},
            },
            "keywords_found": [], "keywords_missing": [],
            "summary": raw[:200],
        }
