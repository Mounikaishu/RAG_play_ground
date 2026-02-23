from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os

from pdf_loader import load_pdf
from chunker import chunk_text
from vectorstore import store_chunks, clear_collection
from graph import build_graph

app = FastAPI()

# Allow frontend to access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = build_graph()
history = []


@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload and process a single resume.
    Old resume embeddings are cleared.
    """
    global history

    file_path = "temp_resume.pdf"

    # Save uploaded file temporarily
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Clear previous resume embeddings
    clear_collection()

    # Process resume
    raw_text = load_pdf(file_path)
    chunks = chunk_text(raw_text)
    store_chunks(chunks)

    # Reset conversation history
    history = []

    # Delete temporary file
    if os.path.exists(file_path):
        os.remove(file_path)

    return {"message": "Resume processed successfully"}


@app.post("/chat")
async def chat(question: str = Form(...)):
    """
    Chat endpoint using LangGraph RAG.
    """
    global history

    if not question:
        return {"answer": "Please ask a valid question."}

    state = {
        "question": question,
        "context": "",
        "answer": "",
        "history": history
    }

    result = graph.invoke(state)

    history = result["history"]

    return {"answer": result["answer"]}
@app.get("/")
def root():
    return {"message": "AI Resume Coach Backend Running"}