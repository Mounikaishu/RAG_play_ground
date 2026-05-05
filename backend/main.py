from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import shutil
import os
import traceback

from pdf_loader import load_pdf
from chunker import chunk_text
from vectorstore import (
    store_chunks,
    clear_collection,
    store_chunks_for_resume,
    clear_all_compare_collections,
    retrieve_chunks_for_compare,
    get_loaded_resume_names,
)
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
        "app": "AI Resume Coach API",
        "endpoints": ["/upload", "/chat", "/score", "/upload-compare", "/compare"],
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