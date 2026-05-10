"""
AI-Powered Placement & Career Guidance Platform — Main FastAPI Application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth_router import router as auth_router
from routers.student_router import router as student_router
from routers.placement_router import router as placement_router
from knowledge_base.kb_seeder import seed_knowledge_base

app = FastAPI(
    title="AI Placement & Career Guidance Platform",
    description="Multi-user AI-powered placement intelligence system",
    version="2.0.0",
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
    """Seed the knowledge base on first startup."""
    seed_knowledge_base()


@app.get("/")
async def root():
    """Health check / API info."""
    from knowledge_base.kb_manager import get_kb_stats
    stats = get_kb_stats()
    return {
        "status": "ok",
        "app": "AI Placement & Career Guidance Platform",
        "version": "2.0.0",
        "knowledge_base": stats,
        "endpoints": {
            "auth": ["/auth/register", "/auth/login", "/auth/me", "/auth/change-password", "/auth/bulk-register"],
            "student": ["/student/upload-resume", "/student/chat", "/student/ats-score", "/student/profile"],
            "placement": ["/placement/search", "/placement/upload-kb", "/placement/students", "/placement/students/years", "/placement/analytics"],
        },
        "notes": {
            "default_password": "All new students get a default password on registration",
            "year_storage": "Resumes are stored in year-specific collections based on passing_out_year",
            "college_email": "Only @svecw.edu.in emails are accepted",
        },
        "docs": "/docs",
    }