"""
config.py — Centralized Production Configuration for PlaceAI RAG Backend.

Consolidates all system knobs, thresholds, security limits, and feature flags.
No hardcoded limits or thresholds anywhere in the system.
"""

import os
import warnings
from dotenv import load_dotenv

load_dotenv(override=True)

# Explicitly load .env from backend directory if it exists
backend_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(backend_env_path):
    load_dotenv(backend_env_path, override=True)

# ── API Keys ─────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    if not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

if not GEMINI_API_KEY and not GROQ_API_KEY:
    warnings.warn(
        "⚠️ Neither GEMINI_API_KEY nor GROQ_API_KEY found! Set at least one in your environment variables."
    )

# ── Retrieval & RAG Knobs ────────────────────────────────────────────────
DEFAULT_TOP_K = int(os.getenv("RAG_DEFAULT_TOP_K", "8"))
RERANK_TOP_K = int(os.getenv("RAG_RERANK_TOP_K", "8"))
REFINE_TOP_K = int(os.getenv("RAG_REFINE_TOP_K", "4"))
SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.0"))

# ── Multi-Alumni Retrieval ───────────────────────────────────────────────
# How many distinct AlumniProfiles to keep after grouping & ranking
TOP_ALUMNI_COUNT = int(os.getenv("TOP_ALUMNI_COUNT", "5"))
# How many merged alumni chunks to allow through refinement (must be >= TOP_ALUMNI_COUNT)
ALUMNI_REFINE_TOP_K = int(os.getenv("ALUMNI_REFINE_TOP_K", "8"))

# ── Match Score Weights (must sum to 1.0) ───────────────────────────────
MATCH_SCORE_WEIGHTS = {
    "skills":       float(os.getenv("WEIGHT_SKILLS",      "0.40")),
    "technologies": float(os.getenv("WEIGHT_TECHNOLOGIES","0.30")),
    "projects":     float(os.getenv("WEIGHT_PROJECTS",    "0.20")),
    "education":    float(os.getenv("WEIGHT_EDUCATION",   "0.05")),
    "experience":   float(os.getenv("WEIGHT_EXPERIENCE",  "0.05")),
}

# ── Confidence Scoring Thresholds ────────────────────────────────────────
CONFIDENCE_HIGH_THRESHOLD = float(os.getenv("CONFIDENCE_HIGH", "75.0"))
CONFIDENCE_MEDIUM_THRESHOLD = float(os.getenv("CONFIDENCE_MEDIUM", "45.0"))

# ── Pipeline & Retry Limits ─────────────────────────────────────────────
MAX_GENERATION_RETRIES = int(os.getenv("MAX_GENERATION_RETRIES", "2"))
MAX_CONTEXT_CHAR_LENGTH = int(os.getenv("MAX_CONTEXT_CHAR_LENGTH", "1500"))

# ── Security & Validation Limits ────────────────────────────────────────
MAX_PDF_SIZE_BYTES = int(os.getenv("MAX_PDF_SIZE_MB", "10")) * 1024 * 1024
ALLOWED_FILE_EXTENSIONS = {".pdf"}
MASK_PII_LOGS = os.getenv("MASK_PII_LOGS", "true").lower() == "true"

# ── Observability & Logging ─────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
STRUCTURED_LOGGING_ENABLED = os.getenv("STRUCTURED_LOGGING", "true").lower() == "true"
