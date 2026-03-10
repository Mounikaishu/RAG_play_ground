from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os

from pdf_loader import load_pdf
from chunker import chunk_text
from vectorstore import store_chunks, clear_collection
from graph import build_graph

app = FastAPI()

# Allow frontend access
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
    global history

    file_path = "temp_resume.pdf"

    # Save file temporarily
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Clear old embeddings
    clear_collection()

    # Process resume
    raw_text = load_pdf(file_path)
    chunks = chunk_text(raw_text)
    store_chunks(chunks)

    history = []  # Reset chat history

    os.remove(file_path)

    return {"message": "Resume processed successfully"}


@app.post("/chat")
async def chat(question: str = Form(...), mode: str = Form(...)):
    global history

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