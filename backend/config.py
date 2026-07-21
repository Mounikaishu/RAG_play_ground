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
