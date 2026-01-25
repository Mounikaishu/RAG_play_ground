from google import genai
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

def chat(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

if __name__ == "__main__":
    print("Gemini Chatbot (type 'exit' to quit)\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            print("⚠️ Please enter a message.\n")
            continue

        if user_input.lower() == "exit":
            print("Goodbye 👋")
            break

        reply = chat(user_input)
        print(f"Gemini: {reply}\n")
#✅ Handled SDK deprecation
#✅ Model version mismatch
#✅ Prompt behavior analysis
#✅ Input guardrails
#✅ Real-world hallucination example