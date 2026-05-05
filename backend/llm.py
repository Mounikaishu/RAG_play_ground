import time
from google import genai
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

# Models to try in order (fallback chain)
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
]

MAX_RETRIES = 3
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
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text

            except Exception as e:
                last_error = e
                error_str = str(e)
                print(f"⚠️ {model} attempt {attempt + 1}/{MAX_RETRIES} failed: {error_str}")

                # Retry on 503 (overloaded) or 429 (rate limit)
                if "503" in error_str or "429" in error_str or "UNAVAILABLE" in error_str:
                    wait_time = RETRY_DELAY * (2 ** attempt)  # exponential backoff
                    print(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Non-retryable error — skip to next model
                    print(f"   Non-retryable error, trying next model...")
                    break

        print(f"❌ All retries exhausted for {model}")

    # All models and retries failed
    print(f"❌ All models failed. Last error: {last_error}")
    return "⚠️ AI model is busy right now. Please try again in a few seconds."
