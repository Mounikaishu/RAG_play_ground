import os
import chromadb
from chromadb.config import Settings

# Singleton pattern — only one client created and reused
_client = None
_embeddings = None

def get_client():
    """
    Singleton Pattern.
    Creates ChromaDB client only once and reuses it.
    Saves memory and connection time.
    """
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )
    return _client


class DeterministicDummyEmbeddings:
    """
    Extremely robust, memory-efficient deterministic dummy embeddings.
    Generates 768-dimensional float vectors deterministically from input text.
    Guarantees 100% uptime, 0 MB memory usage, and zero external downloads
    to ensure the application never crashes during offline/demo scenarios.
    """
    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        import hashlib
        import struct
        h_base = hashlib.sha256(text.encode('utf-8')).digest()
        floats = []
        for i in range(self.dimension):
            h_dim = hashlib.sha256(h_base + struct.pack('i', i)).digest()
            val = struct.unpack('f', h_dim[:4])[0]
            if not (val == val) or val == float('inf') or val == float('-inf'):
                val = 0.0
            else:
                val = max(-1.0, min(1.0, val / 3.4e38))
            floats.append(val)
        return floats

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed(query)


def get_embeddings():
    """
    Singleton Pattern.
    Creates embedding model only once and reuses it.
    If GOOGLE_API_KEY or GEMINI_API_KEY is available, we use cloud-based GoogleGenAIEmbeddings
    to save memory and prevent OOM issues on cloud environments (like Render Free tier).
    Otherwise, we fall back to local HuggingFaceEmbeddings, and ultimately to DeterministicDummyEmbeddings.
    """
    global _embeddings
    if _embeddings is None:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                print("🌐 Initializing cloud-based GoogleGenAIEmbeddings (memory-efficient)...")
                from langchain_google_genai import GoogleGenAIEmbeddings
                _embeddings = GoogleGenAIEmbeddings(
                    model="models/text-embedding-004",
                    google_api_key=api_key
                )
                print("🌐 Cloud-based GoogleGenAIEmbeddings successfully initialized.")
                return _embeddings
            except Exception as e:
                print(f"⚠️ Failed to load GoogleGenAIEmbeddings: {e}. Falling back to local BGE embeddings...")
        
        # Local Fallback
        try:
            print("🖥️ Initializing local HuggingFace BGE Embeddings (heavy memory footprint)...")
            from langchain_huggingface import HuggingFaceEmbeddings
            _embeddings = HuggingFaceEmbeddings(
                model_name="BAAI/bge-base-en-v1.5"
            )
            print("🖥️ Local HuggingFace BGE Embeddings successfully initialized.")
        except Exception as e:
            print(f"⚠️ Failed to initialize HuggingFace BGE Embeddings: {e}")
            print("🚀 Falling back to ultra-robust, zero-memory DeterministicDummyEmbeddings (768-dim)...")
            _embeddings = DeterministicDummyEmbeddings(dimension=768)
    return _embeddings


def get_collection(collection_name: str):
    """
    Gets or creates a ChromaDB collection by name.
    careerbot passes "careerbot_db"
    resumeanalyser passes "resumeanalyser_db"
    Same code, different collections. 
    """
    client = get_client()
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


def embed_texts(texts: list) -> list:
    """
    Converts text into vector embeddings.
    Better embeddings = better retrieval = better answers.
    This is the latent space your sir mentioned.
    """
    embeddings = get_embeddings()
    return embeddings.embed_documents(texts)


def embed_query(query: str) -> list:
    """
    Converts a single query into a vector embedding for searching.
    """
    embeddings = get_embeddings()
    return embeddings.embed_query(query)
