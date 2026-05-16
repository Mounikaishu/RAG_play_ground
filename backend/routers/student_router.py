"""
Student Router — Resume upload, chat, ATS score, resume matching.
"""

from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from typing import Optional
import shutil
import os
import traceback

from auth import get_current_user_from_token
from database import get_user, update_user_profile
from pdf_loader import load_pdf
from chunker import chunk_text_with_overlap
from knowledge_base.collections import store_student_resume, search_kb
from graph.workflow import build_placement_graph
from llm import llm_call
import json
import re

router = APIRouter(prefix="/student", tags=["Student"])

# Per-user conversation history
user_histories = {}

# Build the placement graph once
placement_graph = build_placement_graph()


def _get_user_or_fail(authorization: Optional[str]):
    """Extract and validate user from token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required.")
    user_data = get_current_user_from_token(authorization)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user_data


@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Upload or update student resume. Stored in year-specific collection."""
    user_data = _get_user_or_fail(authorization)
    roll_no = user_data["roll_no"]
    user = get_user(roll_no)

    # Get passing_out_year from user profile for year-based storage
    passing_out_year = user.get("passing_out_year", 0) if user else 0

    file_path = f"temp_resume_{roll_no}.pdf"
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        raw_text = load_pdf(file_path)
        chunks = chunk_text_with_overlap(raw_text)

        # Store resume embeddings in year-specific collection
        store_student_resume(
            roll_no=roll_no,
            name=user.get("name", ""),
            department=user.get("department", ""),
            skills=user.get("skills", []),
            chunks=chunks,
            passing_out_year=passing_out_year,
        )

        # Update profile
        update_user_profile(roll_no, {"resume_uploaded": True})

        year_info = f" (stored in {passing_out_year} batch collection)" if passing_out_year else ""
        return {
            "message": f"✅ Resume uploaded successfully ({len(chunks)} chunks stored){year_info}.",
            "chunks": len(chunks),
            "passing_out_year": passing_out_year,
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
    authorization: Optional[str] = Header(None),
):
    """Main chat endpoint — routes through LangGraph workflow."""
    user_data = _get_user_or_fail(authorization)
    roll_no = user_data["roll_no"]

    from database import get_user
    user = get_user(roll_no)
    student_name = user.get("name", "Student") if user else "Student"
    student_dept = user.get("department", "Unknown") if user else "Unknown"
    student_skills = ", ".join(user.get("skills", [])) if user and user.get("skills") else "None specified"

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
        result = placement_graph.invoke(state)
        user_histories[roll_no] = result.get("history", [])[-20:]
        return {"answer": result["answer"]}
    except Exception as e:
        print(f"❌ Chat error: {e}")
        print(traceback.format_exc())
        return {"answer": f"⚠️ Something went wrong: {str(e)}"}


@router.post("/ats-score")
async def ats_score(authorization: Optional[str] = Header(None)):
    """Get structured ATS score for the student's resume."""
    user_data = _get_user_or_fail(authorization)
    roll_no = user_data["roll_no"]

    # Get resume chunks
    results = search_kb("full resume skills experience education projects", "student_resumes", k=5, where={"roll_no": roll_no})
    if not results:
        return {"error": "No resume uploaded. Please upload your resume first."}

    context = "\n\n".join([r["document"] for r in results])

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

    raw = llm_call(prompt)
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


@router.get("/profile")
async def get_profile(authorization: Optional[str] = Header(None)):
    """Get student profile."""
    user_data = _get_user_or_fail(authorization)
    from database import get_user_profile
    profile = get_user_profile(user_data["roll_no"])
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return {"user": profile}
