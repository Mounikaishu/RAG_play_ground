"""
AI-Powered Placement & Career Guidance Platform — Main FastAPI Application.
"""
import sys
import os



from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.student_router import router as student_router
from knowledge_base.load_knowledge_base import load_knowledge_base

app = FastAPI(
    title="AI Placement & Career Guidance Platform",
    description="Student-focused AI placement intelligence system with multi-document RAG",
    version="3.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(student_router)


@app.on_event("startup")
async def startup():
    """Load institutional knowledge base — seeds data + ingests files from data folders."""
    load_knowledge_base()


@app.get("/")
async def root():
    """Health check / API info."""
    from knowledge_base.kb_manager import get_kb_stats
    from knowledge_base.ingestion_registry import get_registry_stats

    stats = get_kb_stats()
    registry = get_registry_stats()

    return {
        "status": "ok",
        "app": "AI Placement & Career Guidance Platform",
        "version": "3.0.0",
        "knowledge_base": stats,
        "ingestion": registry,
        "endpoints": {
            "student": ["/student/upload-resume", "/student/chat", "/student/ats-score"],
        },
        "collections": [
            "institutional_kb",
            "interview_experiences",
            "alumni_resumes_collection",
            "placement_materials_collection",
            "student_resumes",
        ],
        "data_folders": [
            "backend/data/alumni_resumes/",
            "backend/data/interview_experiences/",
            "backend/data/placement_materials/",
        ],
        "notes": {
            "session": "Stateless sessions using X-Session-ID",
            "ingestion": "Files in data/ folders are auto-ingested on startup with deduplication",
        },
        "docs": "/docs",
    }