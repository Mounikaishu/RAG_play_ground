'''
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
'''
from pdf_loader import load_pdf
from chunker import chunk_text
from graph import build_graph
from state import SummaryState

PDF_PATH = "Resume.pdf"   # put your PDF here

def main():
    raw_text = load_pdf(PDF_PATH)
    chunks = chunk_text(raw_text)

    graph = build_graph()

    initial_state: SummaryState = {
        "raw_text": raw_text,
        "chunks": chunks,
        "chunk_summaries": [],
        "final_summary": ""
    }

    result = graph.invoke(initial_state)

    print("\n📄 FINAL SUMMARY:\n")
    print(result["final_summary"])


if __name__ == "__main__":
    main()
