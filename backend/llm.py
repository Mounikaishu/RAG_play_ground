import time
import datetime
import logging
from google import genai
from config import GEMINI_API_KEY

logger = logging.getLogger("uvicorn.error")

client = genai.Client(api_key=GEMINI_API_KEY)

MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash-002",
    "gemini-1.5-pro-002",
    "gemini-1.0-pro",
]

MAX_RETRIES = 2
RETRY_DELAY = 2  # seconds (doubles each retry)


def llm_call(prompt: str) -> str:
    """
    Call Gemini API with retry logic and model fallback.
    Retries up to MAX_RETRIES times per model, with exponential backoff.
    Falls back to the next model if all retries fail.
    """
    last_error = None

    for model in MODELS:
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(2)
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text

            except Exception as e:
                last_error = e
                error_str = str(e)
                logger.warning(f"⚠️ {model} attempt {attempt + 1}/{MAX_RETRIES} failed: {error_str}")

                # Retry on 503 (overloaded) or 429 (rate limit)
                if "503" in error_str or "429" in error_str or "UNAVAILABLE" in error_str:
                    wait_time = RETRY_DELAY * (2 ** attempt)  # exponential backoff
                    logger.info(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Non-retryable error — skip to next model
                    logger.error(f"   Non-retryable error, trying next model...")
                    break

        logger.error(f"❌ All retries exhausted for {model}")

    # All models and retries failed
    logger.critical(f"❌ All models failed. Last error: {last_error}")
    return "⚠️ AI model is busy right now. Please try again in a few seconds."
