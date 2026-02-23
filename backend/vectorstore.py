import chromadb
from sentence_transformers import SentenceTransformer

# Load embedding model once
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Create Chroma client (in-memory for MVP)
client = chromadb.Client()

# Create or get collection
collection = client.get_or_create_collection(name="resume_chunks")


def store_chunks(chunks):
    """
    Store resume chunks into ChromaDB.
    """
    if not chunks:
        return

    embeddings = embedding_model.encode(chunks).tolist()
    ids = [f"id_{i}" for i in range(len(chunks))]

    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=ids
    )


def retrieve_relevant_chunks(query, k=3):
    """
    Retrieve top-k relevant chunks based on query.
    """
    if not query:
        return []

    query_embedding = embedding_model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=k
    )

    if not results["documents"]:
        return []

    return results["documents"][0]


def clear_collection():
    """
    Clears old resume embeddings.
    """
    global collection

    try:
        client.delete_collection("resume_chunks")
    except Exception:
        pass  # Collection may not exist yet

    collection = client.get_or_create_collection(name="resume_chunks")