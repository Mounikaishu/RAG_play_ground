"""
AI-Powered Placement & Career Guidance Platform — Main FastAPI Application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth_router import router as auth_router
from routers.student_router import router as student_router
from routers.placement_router import router as placement_router
from knowledge_base.load_knowledge_base import load_knowledge_base

app = FastAPI(
    title="AI Placement & Career Guidance Platform",
    description="Multi-user AI-powered placement intelligence system with multi-document RAG",
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
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(placement_router)


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
            "auth": ["/auth/register", "/auth/login", "/auth/me", "/auth/change-password", "/auth/bulk-register"],
            "student": ["/student/upload-resume", "/student/chat", "/student/ats-score", "/student/profile"],
            "placement": ["/placement/search", "/placement/upload-kb", "/placement/students", "/placement/students/years", "/placement/analytics"],
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
            "default_password": "All new students get a default password on registration",
            "year_storage": "Resumes are stored in year-specific collections based on passing_out_year",
            "college_email": "Only @svecw.edu.in emails are accepted",
            "ingestion": "Files in data/ folders are auto-ingested on startup with deduplication",
        },
        "docs": "/docs",
    }