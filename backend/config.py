import os
import warnings
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    warnings.warn(
        "⚠️ GEMINI_API_KEY not found! Set it in your environment variables. "
        "On Render: Dashboard → Environment → Add GEMINI_API_KEY"
    )
