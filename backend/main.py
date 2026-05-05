from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import shutil
import os

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

# Allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = build_graph()

history = []
compare_history = []
resume_loaded = False


@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):

    global history
    global resume_loaded

    file_path = "temp_resume.pdf"

    # Save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print("Resume uploaded")

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

    state = {
        "question": question,
        "context": "",
        "answer": "",
        "history": history,
        "mode": mode
    }

    result = graph.invoke(state)

    history = result["history"]

    return {"answer": result["answer"]}