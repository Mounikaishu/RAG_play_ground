import os
import warnings
from dotenv import load_dotenv

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Copy GEMINI_API_KEY to GOOGLE_API_KEY for downstream RAG pipeline/Google tools integration
if GEMINI_API_KEY and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# Only warn if both API keys are missing to prevent noisy harmless warning logs during presentation
if not GEMINI_API_KEY and not GROQ_API_KEY:
    warnings.warn(
        "⚠️ Neither GEMINI_API_KEY nor GROQ_API_KEY found! Set at least one in your environment variables."
    )
elif not GROQ_API_KEY:
    print("ℹ️ Note: GROQ_API_KEY not found. Fallback to Gemini LLM will be active.")
elif not GEMINI_API_KEY:
    print("ℹ️ Note: GEMINI_API_KEY not found. Groq LLM will be primary.")
