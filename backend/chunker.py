def chunk_text(text: str, chunk_size: int = 800) -> list[str]:
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


def chunk_text_with_overlap(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """
    Chunks text with overlap for better retrieval across multiple documents.
    Smaller chunks + overlap = more precise semantic matching in repository mode.
    """
    words = text.split()
    chunks = []
    step = max(chunk_size - overlap, 1)

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)

    return chunks
