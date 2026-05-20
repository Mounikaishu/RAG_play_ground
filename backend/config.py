import os
import warnings
from dotenv import load_dotenv

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    warnings.warn(
        "⚠️ GROQ_API_KEY not found! Set it in your environment variables."
    )

if not GEMINI_API_KEY and not GROQ_API_KEY:
    warnings.warn(
        "⚠️ Neither GEMINI_API_KEY nor GROQ_API_KEY found! Set at least one in your environment variables."
    )
