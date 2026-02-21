from pdf_loader import load_pdf
from chunker import chunk_text
from vectorstore import store_chunks
from graph import build_graph

PDF_PATH = "Resume.pdf"

def main():
    print("📄 Loading resume...")
    raw_text = load_pdf(PDF_PATH)

    print("✂️ Chunking resume...")
    chunks = chunk_text(raw_text)

    print("📦 Storing embeddings...")
    store_chunks(chunks)

    print("\n✅ Resume analyzed.")
    print("I'm your AI Resume Coach.")
    print("Ask me anything (type 'exit' to quit).\n")

    graph = build_graph()

    history = []

    while True:
        question = input("You: ").strip()

        if question.lower() == "exit":
            print("🚀 Good luck!")
            break

        state = {
            "question": question,
            "context": "",
            "answer": "",
            "history": history
        }

        result = graph.invoke(state)

        print("\n🎓 Resume Coach:", result["answer"], "\n")

        history = result["history"]


if __name__ == "__main__":
    main()