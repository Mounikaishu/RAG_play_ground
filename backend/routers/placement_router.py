"""
Placement Cell Router — Search candidates, manage KB, analytics.
"""

from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form
from typing import Optional, List
import shutil
import os
import traceback

from auth import get_current_user_from_token
from database import get_all_students, get_students_by_year, get_available_years
from pdf_loader import load_pdf
from chunker import chunk_text_with_overlap
from knowledge_base.collections import (
    search_student_resumes, store_student_resume,
    list_kb_documents, delete_kb_document,
    get_year_collection_stats,
)
from knowledge_base.kb_manager import (
    add_alumni_profile, add_interview_experience,
    add_resource, search_knowledge, search_interviews, get_kb_stats,
)
from metadata_extractor import extract_resume_metadata
from llm import llm_call

router = APIRouter(prefix="/placement", tags=["Placement Cell"])


def _get_placement_user(authorization: Optional[str]):
    """Validate placement cell access."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required.")
    user_data = get_current_user_from_token(authorization)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    if user_data.get("role") != "placement_cell":
        raise HTTPException(status_code=403, detail="Placement cell access required.")
    return user_data


@router.post("/search")
async def search_candidates(
    query: str = Form(...),
    year: Optional[int] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Search student resumes semantically. Optionally filter by passing out year."""
    _get_placement_user(authorization)

    candidates = search_student_resumes(query, k=10, passing_out_year=year)

    if not candidates:
        year_msg = f" for {year} batch" if year else ""
        return {"answer": f"⚠️ No student resumes found{year_msg}. Students need to upload resumes first.", "candidates": []}

    # Build context for AI ranking
    summaries = []
    for name, data in list(candidates.items())[:8]:
        skills = data["metadata"].get("skills", "")
        excerpt = data["chunks"][0][:300] if data["chunks"] else ""
        passing_out = data["metadata"].get("passing_out_year", "N/A")
        summaries.append(f"--- {name} ---\nSkills: {skills}\nDepartment: {data['metadata'].get('department', 'N/A')}\nPassing Out: {passing_out}\nExcerpt: {excerpt}")

    combined = "\n\n".join(summaries)

    prompt = f"""You are an AI Recruitment Assistant for a university placement cell.
Recruiter requirement: "{query}"

Candidate profiles:
{combined}

Rank candidates from best to least match. For each provide:
- Match score (0-100)
- Key matching skills
- Passing out year
- Why they fit or don't
Use markdown with bold names and bullet points."""

    ai_answer = llm_call(prompt)

    ranked = []
    for name, data in candidates.items():
        ranked.append({
            "name": name,
            "roll_no": data["metadata"].get("roll_no", ""),
            "department": data["metadata"].get("department", ""),
            "skills": [s.strip() for s in data["metadata"].get("skills", "").split(",") if s.strip()],
            "relevance_score": data["relevance_score"],
            "excerpts": [c[:200] for c in data["chunks"][:2]],
            "passing_out_year": data["metadata"].get("passing_out_year", 0),
        })

    return {"answer": ai_answer, "candidates": ranked}


@router.post("/upload-kb")
async def upload_kb_document(
    title: str = Form(...),
    content: str = Form(...),
    category: str = Form(...),
    company: str = Form(""),
    role: str = Form(""),
    authorization: Optional[str] = Header(None),
):
    """Upload a knowledge base document."""
    _get_placement_user(authorization)

    if category == "interview":
        doc_id = add_interview_experience(
            company=company or "General",
            role=role or "General",
            round_type="general",
            questions=[content],
            tips=title,
        )
    elif category == "alumni":
        doc_id = add_alumni_profile(
            name=title, year="2024", company=company or "N/A",
            role=role or "N/A", department="CSE",
            skills=[], journey=content,
        )
    else:
        doc_id = add_resource(title, content, category)

    return {"message": f"✅ Document added to knowledge base.", "doc_id": doc_id}


@router.post("/upload-resumes")
async def bulk_upload_resumes(
    files: List[UploadFile] = File(...),
    passing_out_year: int = Form(0),
    authorization: Optional[str] = Header(None),
):
    """Bulk upload student resumes to the repository. Stored in year-specific collection."""
    _get_placement_user(authorization)
    results = []

    for uploaded_file in files:
        file_path = f"temp_bulk_{uploaded_file.filename}"
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)

            raw_text = load_pdf(file_path)
            chunks = chunk_text_with_overlap(raw_text)
            metadata = extract_resume_metadata(raw_text)
            name = metadata.get("name", os.path.splitext(uploaded_file.filename)[0])

            store_student_resume(
                roll_no=name.lower().replace(" ", "_"),
                name=name,
                department=metadata.get("department", "N/A"),
                skills=metadata.get("skills", []),
                chunks=chunks,
                passing_out_year=passing_out_year,
            )
            results.append({
                "name": name,
                "skills": metadata.get("skills", []),
                "passing_out_year": passing_out_year,
                "status": "success",
            })
        except Exception as e:
            results.append({"name": uploaded_file.filename, "error": str(e), "status": "failed"})
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    return {"message": f"✅ Processed {len(results)} resume(s).", "results": results}


@router.get("/students")
async def list_all_students(
    year: Optional[int] = None,
    authorization: Optional[str] = Header(None),
):
    """List all registered students. Optionally filter by passing out year."""
    _get_placement_user(authorization)

    if year:
        students = get_students_by_year(year)
    else:
        students = get_all_students()

    return {"students": students, "total": len(students)}


@router.get("/students/years")
async def list_available_years(authorization: Optional[str] = Header(None)):
    """Get all available passing out years from registered students."""
    _get_placement_user(authorization)
    years = get_available_years()
    return {"years": years}


@router.get("/analytics")
async def get_analytics(
    year: Optional[int] = None,
    authorization: Optional[str] = Header(None),
):
    """Get placement analytics data. Optionally filter by passing out year."""
    _get_placement_user(authorization)

    if year:
        students = get_students_by_year(year)
    else:
        students = get_all_students()

    kb_stats = get_kb_stats()
    year_stats = get_year_collection_stats()

    # Skill distribution
    skill_counts = {}
    dept_counts = {}
    year_counts = {}
    for s in students:
        for skill in s.get("skills", []):
            skill_counts[skill] = skill_counts.get(skill, 0) + 1
        dept = s.get("department", "Unknown")
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
        poy = s.get("passing_out_year", 0)
        if poy:
            year_counts[poy] = year_counts.get(poy, 0) + 1

    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:15]

    return {
        "total_students": len(students),
        "departments": dept_counts,
        "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
        "resumes_uploaded": sum(1 for s in students if s.get("resume_uploaded")),
        "kb_stats": kb_stats,
        "year_distribution": year_counts,
        "resume_collections_by_year": year_stats,
        "available_years": get_available_years(),
    }


@router.get("/kb-documents")
async def list_kb(
    collection: str = "institutional_kb",
    authorization: Optional[str] = Header(None),
):
    """List knowledge base documents."""
    _get_placement_user(authorization)
    docs = list_kb_documents(collection, limit=50)
    return {"documents": docs, "total": len(docs)}


@router.delete("/kb/{doc_id}")
async def delete_kb(
    doc_id: str,
    collection: str = "institutional_kb",
    authorization: Optional[str] = Header(None),
):
    """Delete a KB document."""
    _get_placement_user(authorization)
    delete_kb_document(collection, doc_id)
    return {"message": f"✅ Document {doc_id} deleted."}
