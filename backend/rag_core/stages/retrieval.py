"""
retrieval.py — Stage 2: Vector Database Retrieval (RAG Core Interface).

Delegates vector database queries to the unified knowledge_base/retrieval.py
Retrieval Engine facade while maintaining exact signature compatibility.
"""

from knowledge_base.retrieval import retrieve as kb_retrieve


def retrieve_chunks(
    query: str,
    collection_name: str,
    k: int = 10,
    where: dict = None
) -> list[dict]:
    """
    Delegates retrieval to the unified Retrieval Engine facade.

    Returns:
        List of dicts: [{
            "text": "chunk text",
            "metadata": {...},
            "distance": 0.12
        }]
    """
    response = kb_retrieve(
        query=query,
        collections=[collection_name],
        top_k=k,
        filters=where,
    )

    chunks = []
    for r in response.results:
        chunks.append({
            "text": r.content,
            "metadata": r.metadata,
            "distance": r.distance,
            "similarity_score": r.similarity_score,
            "section": r.section,
            "source_file": r.source_file,
        })

    return chunks
