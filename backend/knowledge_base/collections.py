"""
ChromaDB Multi-Collection Manager for the institutional knowledge base.

Collections:
- institutional_kb: Alumni journeys, career roadmaps, placement tips, ATS templates
- interview_experiences: Company-wise interview Q&A, round-specific experiences
- alumni_resumes: File-based alumni resume embeddings with rich metadata
- placement_materials: Guides, roadmaps, DSA resources, strategy documents
- student_resumes: All student resume embeddings with metadata (legacy/fallback)
- student_resumes_{year}: Year-specific resume collections (e.g., student_resumes_2028)
"""

import os
import chromadb
from collections import defaultdict

# Persistent ChromaDB — data survives server restarts
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

COLLECTIONS = {
    "institutional_kb": "institutional_kb",
    "interview_experiences": "interview_experiences",
    "alumni_resumes": "alumni_resumes_collection",
    "placement_materials": "placement_materials_collection",
    "student_resumes": "student_resumes",
}


def get_collection(name: str):
    """Get or create a ChromaDB collection using the shared BGE embedding model."""
    coll_name = COLLECTIONS.get(name, name)
    try:
        from rag_core.db.chromadb_store import get_embeddings, LangChainEmbeddingFunction
        emb_fn = LangChainEmbeddingFunction(get_embeddings())
    except Exception as e:
        print(f"⚠️ Failed to load shared embedding function: {e}")
        emb_fn = None

    try:
        return client.get_or_create_collection(coll_name, embedding_function=emb_fn)
    except ValueError as e:
        if "Embedding function conflict" in str(e):
            print(f"⚠️ Embedding function conflict detected for collection '{coll_name}'. Recreating collection...")
            try:
                client.delete_collection(coll_name)
                # Clear registry to force full re-ingestion since collection was wiped
                try:
                    from knowledge_base.ingestion_registry import clear_registry
                    clear_registry()
                except Exception as reg_err:
                    print(f"⚠️ Failed to clear registry: {reg_err}")
                return client.get_or_create_collection(coll_name, embedding_function=emb_fn)
            except Exception as delete_err:
                print(f"❌ Failed to recreate collection '{coll_name}': {delete_err}")
                raise e
        else:
            raise e


def get_year_collection_name(passing_out_year: int) -> str:
    """Get year-specific resume collection name."""
    return f"student_resumes_{passing_out_year}"


def store_kb_document(collection_name: str, doc_id: str, text: str, metadata: dict):
    """Store a document in a knowledge base collection."""
    collection = get_collection(collection_name)
    collection.upsert(
        documents=[text],
        ids=[doc_id],
        metadatas=[metadata],
    )


def store_kb_documents_batch(collection_name: str, ids: list, texts: list, metadatas: list):
    """Store multiple documents in batch."""
    collection = get_collection(collection_name)
    collection.upsert(
        documents=texts,
        ids=ids,
        metadatas=metadatas,
    )


def search_kb(query: str, collection_name: str, k: int = 5, where: dict = None):
    """
    Semantic search in a KB collection.
    Returns list of {document, metadata, distance}.
    """
    collection = get_collection(collection_name)

    if collection.count() == 0:
        return []

    # Safe element count calculation for filtered queries to avoid ChromaDB query size errors
    if where:
        try:
            matched = collection.get(where=where, include=[])
            count = len(matched["ids"]) if matched and "ids" in matched else 0
        except Exception:
            count = collection.count()
    else:
        count = collection.count()

    if count == 0:
        return []

    n = min(k, count)
    kwargs = {"query_texts": [query], "n_results": n, "include": ["documents", "metadatas", "distances"]}

    if where:
        kwargs["where"] = where

    try:
        results = collection.query(**kwargs)
    except Exception as e:
        # Fallback if query still fails
        kwargs["n_results"] = 1
        try:
            results = collection.query(**kwargs)
        except Exception:
            return []

    items = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        items.append({"document": doc, "metadata": meta, "distance": dist})

    return items


def search_alumni_resumes(query: str, k: int = 5, company: str = None,
                           department: str = None, batch: str = None,
                           role: str = None, section: str = None):
    """
    Search across alumni resume embeddings with optional metadata filters.
    Returns list of {document, metadata, distance}.
    """
    where_conditions = []
    if company:
        where_conditions.append({"company": company})
    if department:
        where_conditions.append({"department": department})
    if batch:
        where_conditions.append({"batch": str(batch)})
    if role:
        where_conditions.append({"role": role})
    if section:
        where_conditions.append({"section_title": section})

    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}
    else:
        where = None

    return search_kb(
        query, "alumni_resumes", k=k,
        where=where,
    )


def search_interview_experiences(query: str, k: int = 5, company: str = None,
                                  role: str = None, difficulty: str = None,
                                  job_type: str = None, round_name: str = None,
                                  section: str = None):
    """
    Search across interview experience embeddings with metadata filters.
    Supports filtering by company, role, difficulty, job_type, round_name, section.
    """
    where_conditions = []
    if company:
        where_conditions.append({"company": company})
    if role:
        where_conditions.append({"role": role})
    if difficulty:
        where_conditions.append({"difficulty": difficulty})
    if job_type:
        where_conditions.append({"job_type": job_type})
    if round_name:
        where_conditions.append({"round": round_name})
    if section:
        where_conditions.append({"section_title": section})

    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}
    else:
        where = None

    return search_kb(
        query, "interview_experiences", k=k,
        where=where,
    )


def search_placement_materials(query: str, k: int = 5, material_type: str = None):
    """
    Search across placement materials with optional type filter.
    Returns list of {document, metadata, distance}.
    """
    where = {"type": material_type} if material_type else None
    return search_kb(query, "placement_materials", k=k, where=where)


def store_student_resume(roll_no: str, name: str, department: str,
                          skills: list, chunks: list, passing_out_year: int = 0):
    """
    Store a student's resume chunks in the appropriate collection.
    If passing_out_year is provided, stores in year-specific collection (e.g., student_resumes_2028).
    Also stores in the main student_resumes collection for backward compatibility.
    """
    skills_str = ", ".join(skills) if skills else ""

    # Determine collections to store in
    collections_to_store = ["student_resumes"]
    if passing_out_year:
        year_collection = get_year_collection_name(passing_out_year)
        collections_to_store.append(year_collection)

    for coll_name in collections_to_store:
        collection = get_collection(coll_name)

        # Remove old chunks for this student in this collection
        try:
            old = collection.get(where={"roll_no": roll_no}, include=["metadatas"])
            if old["ids"]:
                collection.delete(ids=old["ids"])
        except Exception:
            pass

        for i, chunk in enumerate(chunks):
            # BUG-3 FIX: use upsert() instead of add() so that if the
            # pre-deletion step fails silently, re-uploads don't crash on
            # duplicate IDs.
            collection.upsert(
                documents=[chunk],
                ids=[f"resume_{roll_no}_{coll_name}_{i}"],
                metadatas=[{
                    "roll_no": roll_no,
                    "student_name": name,
                    "department": department,
                    "skills": skills_str,
                    "chunk_index": i,
                    "passing_out_year": passing_out_year,
                }],
            )

    print(f"✅ Resume '{name}' ({roll_no}) stored in {', '.join(collections_to_store)} ({len(chunks)} chunks each)")


def search_student_resumes(query: str, k: int = 10, department: str = None,
                            passing_out_year: int = None):
    """
    Search across student resumes. Returns grouped by student.
    If passing_out_year is specified, searches only that year's collection.
    """
    # Pick the right collection
    if passing_out_year:
        collection_name = get_year_collection_name(passing_out_year)
    else:
        collection_name = "student_resumes"

    where = {}
    if department:
        where["department"] = department

    results = search_kb(query, collection_name, k=k * 3, where=where if where else None)

    # Group by student
    grouped = defaultdict(lambda: {"chunks": [], "distances": [], "metadata": {}})
    for item in results:
        name = item["metadata"].get("student_name", "Unknown")
        grouped[name]["chunks"].append(item["document"])
        grouped[name]["distances"].append(item["distance"])
        grouped[name]["metadata"] = item["metadata"]

    # Calculate relevance scores
    ranked = {}
    for name, data in grouped.items():
        avg_dist = sum(data["distances"]) / len(data["distances"])
        score = max(0, min(100, round((1 - avg_dist / 2) * 100)))
        ranked[name] = {
            "chunks": data["chunks"][:3],
            "metadata": data["metadata"],
            "relevance_score": score,
        }

    return dict(sorted(ranked.items(), key=lambda x: x[1]["relevance_score"], reverse=True))


def get_collection_count(collection_name: str) -> int:
    """Get document count in a collection."""
    try:
        return get_collection(collection_name).count()
    except Exception:
        return 0


def get_all_kb_stats() -> dict:
    """Get stats for all collections."""
    return {
        name: get_collection_count(name)
        for name in COLLECTIONS
    }


def get_year_collection_stats() -> dict:
    """Get stats for all year-specific resume collections."""
    stats = {}
    # Check common years (2020-2035 range)
    for year in range(2020, 2036):
        coll_name = get_year_collection_name(year)
        count = get_collection_count(coll_name)
        if count > 0:
            stats[str(year)] = count
    return stats


def delete_kb_document(collection_name: str, doc_id: str):
    """Delete a specific document from a collection."""
    collection = get_collection(collection_name)
    collection.delete(ids=[doc_id])


def list_kb_documents(collection_name: str, limit: int = 50) -> list:
    """List documents in a collection."""
    collection = get_collection(collection_name)
    if collection.count() == 0:
        return []

    results = collection.get(limit=limit, include=["documents", "metadatas"])
    items = []
    for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
        items.append({"id": doc_id, "document": doc[:200], "metadata": meta})
    return items
