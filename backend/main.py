from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import shutil
import os
import traceback

from pdf_loader import load_pdf
from chunker import chunk_text, chunk_text_with_overlap
from vectorstore import (
    store_chunks,
    clear_collection,
    store_chunks_for_resume,
    clear_all_compare_collections,
    retrieve_chunks_for_compare,
    get_loaded_resume_names,
)
from resume_repository import (
    store_resume_to_repository,
    search_candidates,
    get_all_students,
    remove_student,
    clear_repository,
    get_student_count,
)
from metadata_extractor import extract_resume_metadata
from graph import build_graph
from llm import llm_call

app = FastAPI()

# Allow all origins (update with specific frontend URL in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = build_graph()

history = []
compare_history = []
resume_loaded = False


@app.get("/")
async def root():
    """Health check / API info endpoint."""
    return {
        "status": "ok",
        "app": "AI Resume Coach & Recruitment API",
        "endpoints": [
            "/upload", "/chat", "/score",
            "/upload-compare", "/compare",
            "/repository/upload", "/repository/search",
            "/repository/students", "/repository/student/{name}",
        ],
        "docs": "/docs",
    }


@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):

    global history
    global resume_loaded

    file_path = "temp_resume.pdf"

    try:
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"Resume uploaded: {file.filename}")

        # Remove old embeddings
        clear_collection()

        # Process new resume
        raw_text = load_pdf(file_path)

        chunks = chunk_text(raw_text)

        store_chunks(chunks)

        # Reset history
        history = []

        resume_loaded = True

        os.remove(file_path)

        return {
            "message": "✅ New resume uploaded successfully. You can now ask questions based on this resume."
        }
    except Exception as e:
        print(f"❌ Upload error: {e}")
        print(traceback.format_exc())
        # Clean up temp file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
        return {"message": f"❌ Upload failed: {str(e)}"}


@app.post("/upload-compare")
async def upload_for_compare(files: List[UploadFile] = File(...)):
    """
    Upload multiple PDFs for comparison.
    Each file gets its own vector collection.
    """
    global compare_history

    # Clear previous compare collections
    clear_all_compare_collections()
    compare_history = []

    uploaded_names = []

    for uploaded_file in files:
        file_path = f"temp_{uploaded_file.filename}"

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(uploaded_file.file, buffer)

        # Process
        raw_text = load_pdf(file_path)
        chunks = chunk_text(raw_text)

        # Use filename (without extension) as the resume identifier
        resume_name = os.path.splitext(uploaded_file.filename)[0]
        store_chunks_for_resume(resume_name, chunks)
        uploaded_names.append(resume_name)

        os.remove(file_path)

    return {
        "message": f"✅ {len(uploaded_names)} resume(s) uploaded for comparison.",
        "resumes": uploaded_names,
    }


@app.post("/compare")
async def compare_resumes(question: str = Form(...)):
    """
    Compare multiple uploaded resumes based on the user's question.
    """
    global compare_history

    loaded = get_loaded_resume_names()

    if len(loaded) < 2:
        return {
            "answer": "⚠️ Please upload at least 2 resumes to compare. Use the Compare tab to upload multiple PDFs."
        }

    # Retrieve relevant chunks from each resume
    all_contexts = retrieve_chunks_for_compare(question, k=3)

    # Build comparison prompt
    resume_sections = []
    for name, chunks in all_contexts.items():
        section = f"--- Resume: {name} ---\n" + "\n".join(chunks)
        resume_sections.append(section)

    combined_context = "\n\n".join(resume_sections)
    history_text = "\n".join(compare_history)

    prompt = f"""
You are an expert resume analyst and career advisor.
You are comparing {len(loaded)} resumes side by side.

Resume Contents:
{combined_context}

Conversation History:
{history_text}

User Question:
{question}

Guidelines:
- Compare the resumes clearly using a structured format.
- Highlight strengths and weaknesses of EACH resume.
- Use a comparison table format when appropriate.
- Be specific — reference actual skills, experiences, and content from each resume.
- Use bullet points for readability.
- Leave blank lines between sections.
- If asked to pick the best, justify your choice clearly.
"""

    answer = llm_call(prompt)

    compare_history += [
        f"User: {question}",
        f"Advisor: {answer}",
    ]

    return {"answer": answer}


@app.post("/chat")
async def chat(question: str = Form(...), mode: str = Form(...)):

    global history
    global resume_loaded

    if not resume_loaded:
        return {
            "answer": "⚠️ Please upload a resume first before asking questions."
        }

    try:
        state = {
            "question": question,
            "context": "",
            "answer": "",
            "history": history,
            "mode": mode
        }

        print(f"Chat request - mode: {mode}, question: {question[:80]}...")

        result = graph.invoke(state)

        history = result["history"]

        return {"answer": result["answer"]}
    except Exception as e:
        print(f"❌ Chat error: {e}")
        print(traceback.format_exc())
        return {"answer": f"⚠️ Something went wrong on the server: {str(e)}. Please try uploading your resume again."}


@app.post("/score")
async def score_resume():
    """
    Returns a structured resume score (overall + category breakdown).
    """
    from vectorstore import retrieve_relevant_chunks
    import json
    import re

    global resume_loaded

    if not resume_loaded:
        return {"error": "No resume loaded"}

    # Retrieve broad context for scoring
    chunks = retrieve_relevant_chunks("full resume overview skills experience education projects", k=5)
    context = "\n\n".join(chunks) if chunks else ""

    prompt = f"""
Analyze this resume and provide a score. You MUST respond with ONLY a valid JSON object, no other text.

Resume Content:
{context}

Return EXACTLY this JSON format (no markdown, no code fences, just raw JSON):
{{
  "overall": <number 0-100>,
  "categories": {{
    "education": {{ "score": <number 0-20>, "comment": "<one sentence>" }},
    "experience": {{ "score": <number 0-20>, "comment": "<one sentence>" }},
    "skills": {{ "score": <number 0-20>, "comment": "<one sentence>" }},
    "projects": {{ "score": <number 0-20>, "comment": "<one sentence>" }},
    "presentation": {{ "score": <number 0-20>, "comment": "<one sentence>" }}
  }},
  "summary": "<2 sentence overall assessment>"
}}
"""

    raw = llm_call(prompt)

    # Try to parse JSON from the response
    try:
        # Remove markdown code fences if present
        cleaned = re.sub(r'```json\s*', '', raw)
        cleaned = re.sub(r'```\s*', '', cleaned)
        cleaned = cleaned.strip()
        data = json.loads(cleaned)
        return data
    except Exception:
        # Fallback: return a default structure
        return {
            "overall": 70,
            "categories": {
                "education": {"score": 14, "comment": "Could not parse detailed score."},
                "experience": {"score": 14, "comment": "Could not parse detailed score."},
                "skills": {"score": 14, "comment": "Could not parse detailed score."},
                "projects": {"score": 14, "comment": "Could not parse detailed score."},
                "presentation": {"score": 14, "comment": "Could not parse detailed score."},
            },
            "summary": raw[:200],
        }


# ============================================
# DEPARTMENT RESUME REPOSITORY ENDPOINTS
# ============================================

@app.post("/repository/upload")
async def upload_to_repository(files: List[UploadFile] = File(...)):
    """
    Upload one or more resumes to the department repository.
    Each resume is processed, chunked, metadata is extracted via LLM,
    and stored in the shared ChromaDB collection.
    """
    uploaded_students = []

    for uploaded_file in files:
        file_path = f"temp_repo_{uploaded_file.filename}"

        try:
            # Save file temporarily
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)

            print(f"📁 Processing for repository: {uploaded_file.filename}")

            # Extract text
            raw_text = load_pdf(file_path)

            # Chunk with overlap for better retrieval
            chunks = chunk_text_with_overlap(raw_text)

            # Extract metadata using LLM
            metadata = extract_resume_metadata(raw_text)

            # Use extracted name, or fall back to filename
            student_name = metadata.get("name", "Unknown")
            if student_name == "Unknown" or not student_name.strip():
                student_name = os.path.splitext(uploaded_file.filename)[0]

            # Store in repository
            store_resume_to_repository(student_name, chunks, metadata)

            uploaded_students.append({
                "name": student_name,
                "department": metadata.get("department", "Not Specified"),
                "skills": metadata.get("skills", []),
                "cgpa": metadata.get("cgpa", "N/A"),
                "projects": metadata.get("projects", []),
                "experience_summary": metadata.get("experience_summary", ""),
                "chunks_stored": len(chunks),
            })

            print(f"✅ {student_name} added to repository")

        except Exception as e:
            print(f"❌ Error processing {uploaded_file.filename}: {e}")
            print(traceback.format_exc())
            uploaded_students.append({
                "name": os.path.splitext(uploaded_file.filename)[0],
                "error": str(e),
            })
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    return {
        "message": f"✅ {len(uploaded_students)} resume(s) processed for the repository.",
        "students": uploaded_students,
        "total_in_repository": get_student_count(),
    }


@app.post("/repository/search")
async def search_repository(query: str = Form(...)):
    """
    Recruiter search endpoint.
    Semantically searches all stored resumes, groups by student,
    and uses Gemini to rank and justify matches.
    """
    candidates = search_candidates(query, k=10)

    if not candidates:
        return {
            "answer": "⚠️ No resumes in the repository yet. Please upload student resumes first.",
            "candidates": [],
        }

    # Build context for AI ranking
    candidate_summaries = []
    for name, data in list(candidates.items())[:8]:  # Top 8 for LLM context
        skills = data["metadata"].get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        projects = data["metadata"].get("projects", [])
        if isinstance(projects, str):
            projects = [p.strip() for p in projects.split(",") if p.strip()]

        resume_excerpts = "\n".join(data["chunks"][:2])
        candidate_summaries.append(
            f"--- Candidate: {name} ---\n"
            f"Skills: {', '.join(skills) if skills else 'N/A'}\n"
            f"Projects: {', '.join(projects) if projects else 'N/A'}\n"
            f"Department: {data['metadata'].get('department', 'N/A')}\n"
            f"CGPA: {data['metadata'].get('cgpa', 'N/A')}\n"
            f"Relevance Score: {data['relevance_score']}%\n"
            f"Resume Excerpt:\n{resume_excerpts}\n"
        )

    combined = "\n\n".join(candidate_summaries)

    prompt = f"""
You are an AI Recruitment Assistant for a university department.
A recruiter has submitted the following requirement:

"{query}"

Here are the candidate profiles retrieved from the department resume repository:

{combined}

Your task:
1. Rank the candidates from BEST to LEAST matching for this requirement.
2. For each candidate, provide:
   - A match score (0-100)
   - Key matching skills/experience
   - Why they are a good or poor fit
3. Provide a brief summary at the top.

Format your response in clean markdown with:
- A summary paragraph
- Numbered ranking with candidate details
- Use **bold** for names, scores, and key highlights
- Use bullet points for skills matching
- Be specific — reference actual content from their resumes
"""

    ai_ranking = llm_call(prompt)

    # Build structured candidate list for frontend cards
    ranked_candidates = []
    for name, data in candidates.items():
        skills = data["metadata"].get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        projects = data["metadata"].get("projects", [])
        if isinstance(projects, str):
            projects = [p.strip() for p in projects.split(",") if p.strip()]

        ranked_candidates.append({
            "name": name,
            "relevance_score": data["relevance_score"],
            "skills": skills,
            "projects": projects,
            "department": data["metadata"].get("department", "N/A"),
            "cgpa": data["metadata"].get("cgpa", "N/A"),
            "excerpts": data["chunks"][:2],
        })

    return {
        "answer": ai_ranking,
        "candidates": ranked_candidates,
    }


@app.get("/repository/students")
async def list_students():
    """List all students currently in the department repository."""
    students = get_all_students()
    return {
        "students": students,
        "total": len(students),
    }


@app.delete("/repository/student/{name}")
async def delete_student(name: str):
    """Remove a specific student from the repository."""
    success = remove_student(name)
    if success:
        return {"message": f"✅ {name} removed from repository.", "total": get_student_count()}
    else:
        return {"message": f"⚠️ Student '{name}' not found in repository.", "total": get_student_count()}