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
from vectorstore import store_chunks, retrieve_relevant_chunks
from llm import llm_call

PDF_PATH = "Resume.pdf"

def main():
    print("Loading PDF...")
    raw_text = load_pdf(PDF_PATH)

    print("Chunking text...")
    chunks = chunk_text(raw_text)

    print("Storing embeddings in ChromaDB...")
    store_chunks(chunks)

    print("\nRAG system ready! Ask questions (type 'exit' to quit)\n")

    while True:
        question = input("You: ").strip()

        if question.lower() == "exit":
            break

        relevant_chunks = retrieve_relevant_chunks(question)

        context = "\n\n".join(relevant_chunks)

        prompt = f"""
        Answer the question based ONLY on the context below.
        If the answer is not in the context, say "Not found in document."

        Context:
        {context}

        Question:
        {question}
        """

        answer = llm_call(prompt)

        print("\nAnswer:", answer, "\n")


if __name__ == "__main__":
    main()
