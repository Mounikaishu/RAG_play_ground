"""
retrieval.py — Public Retrieval Engine Facade for PlaceAI.

The SINGLE entry point for all vector retrieval operations across ChromaDB.
No other module should query ChromaDB directly.

Workflow:
User Query → Query Analyzer → Collection Selector → Metadata Filter Builder → Vector Search → Merge & Rank → RetrievalResult Objects
"""

import time
import logging
from typing import List, Dict, Any, Optional

from knowledge_base.retrieval_models import (
    RetrievalResult,
    QueryAnalysis,
    RetrievalResponse,
)
from knowledge_base.query_analyzer import analyze_query
from knowledge_base.collection_selector import select_collections
# Use knowledge_base.collections.get_collection so that logical collection names
# (e.g. 'alumni_resumes') are resolved to their physical ChromaDB names
# (e.g. 'alumni_resumes_collection') exactly as Phase 1 ingestion did.
from knowledge_base.collections import get_collection
from rag_core.db.chromadb_store import embed_query

logger = logging.getLogger("uvicorn.error")


def _log_retrieval_stage(stage_name: str, duration_ms: float = None, detail: str = ""):
    """Format production-grade timing logs for retrieval pipeline stages."""
    time_str = f" ({duration_ms:.1f} ms)" if duration_ms is not None else ""
    detail_str = f" — {detail}" if detail else ""
    print(f"   ⏱️ [Retrieval] {stage_name}...{time_str}{detail_str}")


def _distance_to_similarity(distance: float) -> float:
    """Convert cosine/L2 distance metric to similarity score percentage (0-100%)."""
    # Distance of 0.0 -> 100% similarity. Distance of >= 2.0 -> 0% similarity.
    score = max(0.0, min(100.0, (1.0 - (distance / 2.0)) * 100.0))
    return round(score, 2)


def _chroma_query_to_results(
    raw_results: dict,
    collection_name: str,
    score_threshold: float = 0.0,
) -> List[RetrievalResult]:
    """Convert raw ChromaDB query response into typed RetrievalResult objects."""
    results: List[RetrievalResult] = []

    if not raw_results or not raw_results.get("documents") or not raw_results["documents"][0]:
        return results

    documents = raw_results["documents"][0]
    metadatas = raw_results["metadatas"][0]
    distances = raw_results["distances"][0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        score = _distance_to_similarity(dist)
        if score < score_threshold:
            continue

        src_file = meta.get("source_file") or meta.get("filename") or "Unknown"
        page_no = int(meta.get("page_number") or meta.get("page") or 1)
        sec = meta.get("section_title") or meta.get("section") or "General"
        doc_t = meta.get("document_type") or meta.get("category") or "Unknown"
        comp = meta.get("company")
        role = meta.get("role")

        results.append(
            RetrievalResult(
                content=doc,
                similarity_score=score,
                distance=round(dist, 4),
                collection=collection_name,
                metadata=meta,
                source_file=src_file,
                page_number=page_no,
                section=sec,
                document_type=doc_t,
                company=comp,
                role=role,
            )
        )

    return results


# ──────────────────────────────────────────────────────────
# Public Facade APIs
# ──────────────────────────────────────────────────────────

def retrieve(
    query: str,
    collections: Optional[List[str]] = None,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    score_threshold: float = 0.0,
) -> RetrievalResponse:
    """
    Primary unified retrieval function.

    Args:
        query: User query string
        collections: Targeted collection names (optional)
        top_k: Max total chunks to return
        filters: Custom metadata filter dictionary (overrides auto-detected filters)
        score_threshold: Minimum similarity score percentage (0-100)

    Returns:
        RetrievalResponse containing sorted RetrievalResult objects.
    """
    t_start = time.time()
    print(f"\n🔍 Retrieving for query: '{query}'")

    # Stage 1: Analyze query
    t0 = time.time()
    _log_retrieval_stage("Analyzing query")
    analysis = analyze_query(query)
    _log_retrieval_stage("Analyzing query complete", (time.time() - t0) * 1000)

    # Stage 2: Select collections
    t0 = time.time()
    _log_retrieval_stage("Selecting collections")
    target_collections = select_collections(query, analysis, override_collections=collections)
    _log_retrieval_stage("Selecting collections complete", (time.time() - t0) * 1000, f"Target: {target_collections}")

    # Stage 3: Apply metadata filters
    t0 = time.time()
    _log_retrieval_stage("Applying metadata filters")
    where_clause = filters if filters is not None else analysis.filters
    _log_retrieval_stage("Applying metadata filters complete", (time.time() - t0) * 1000, f"Filters: {where_clause}")

    # Stage 4: Generate Query Embedding & Search ChromaDB
    t0 = time.time()
    _log_retrieval_stage("Searching ChromaDB")
    query_emb = embed_query(query)

    all_results: List[RetrievalResult] = []
    distribution: Dict[str, int] = {}

    for coll_name in target_collections:
        try:
            coll = get_collection(coll_name)
            if coll.count() == 0:
                continue

            k_per_coll = min(top_k, coll.count())
            query_kwargs = {
                "query_embeddings": [query_emb],
                "n_results": k_per_coll,
                "include": ["documents", "metadatas", "distances"],
            }
            if where_clause:
                query_kwargs["where"] = where_clause

            raw = coll.query(**query_kwargs)
            coll_results = _chroma_query_to_results(raw, coll_name, score_threshold)
            all_results.extend(coll_results)
            distribution[coll_name] = len(coll_results)

        except Exception as exc:
            logger.warning("⚠️ Query with filters %s failed on collection %s: %s. Retrying without filters.",
                           where_clause, coll_name, exc)
            # Safe fallback: try without filters if metadata filter caused an error
            try:
                coll = get_collection(coll_name)
                k_per_coll = min(top_k, coll.count())
                raw = coll.query(query_embeddings=[query_emb], n_results=k_per_coll, include=["documents", "metadatas", "distances"])
                coll_results = _chroma_query_to_results(raw, coll_name, score_threshold)
                all_results.extend(coll_results)
                distribution[coll_name] = len(coll_results)
            except Exception as fallback_exc:
                logger.error("❌ Secondary search failed for %s: %s", coll_name, fallback_exc)

    t_search = (time.time() - t0) * 1000
    _log_retrieval_stage(f"Found {len(all_results)} chunks", t_search)

    # Stage 5: Merge, Deduplicate & Rank
    t0 = time.time()
    _log_retrieval_stage("Ranking results")
    # Deduplicate by chunk content snippet
    seen_content = set()
    unique_results = []
    for r in sorted(all_results, key=lambda x: x.similarity_score, reverse=True):
        snippet = r.content.strip()[:100]
        if snippet not in seen_content:
            seen_content.add(snippet)
            unique_results.append(r)

    ranked_results = unique_results[:top_k]
    t_rank = (time.time() - t0) * 1000
    _log_retrieval_stage("Ranking complete", t_rank)

    total_time_ms = round((time.time() - t_start) * 1000, 2)
    _log_retrieval_stage("Finished", total_time_ms)

    return RetrievalResponse(
        query=query,
        query_analysis=analysis,
        results=ranked_results,
        total_found=len(ranked_results),
        collections_searched=target_collections,
        execution_time_ms=total_time_ms,
        collection_distribution=distribution,
    )


def retrieve_resumes(
    query: str,
    top_k: int = 5,
    company: Optional[str] = None,
    department: Optional[str] = None,
    batch: Optional[str] = None,
    role: Optional[str] = None,
) -> RetrievalResponse:
    """Retrieve specifically from alumni_resumes collection."""
    filters = {}
    if company:
        filters["company"] = company
    if department:
        filters["department"] = department
    if batch:
        filters["batch"] = str(batch)
    if role:
        filters["role"] = role

    return retrieve(
        query=query,
        collections=["alumni_resumes"],
        top_k=top_k,
        filters=filters if filters else None,
    )


def retrieve_interview_experiences(
    query: str,
    top_k: int = 5,
    company: Optional[str] = None,
    role: Optional[str] = None,
    difficulty: Optional[str] = None,
    job_type: Optional[str] = None,
    round_name: Optional[str] = None,
) -> RetrievalResponse:
    """Retrieve specifically from interview_experiences collection."""
    filters = {}
    if company:
        filters["company"] = company
    if role:
        filters["role"] = role
    if difficulty:
        filters["difficulty"] = difficulty
    if job_type:
        filters["job_type"] = job_type
    if round_name:
        filters["round"] = round_name

    return retrieve(
        query=query,
        collections=["interview_experiences"],
        top_k=top_k,
        filters=filters if filters else None,
    )


def retrieve_placement_materials(
    query: str,
    top_k: int = 5,
    material_type: Optional[str] = None,
) -> RetrievalResponse:
    """Retrieve specifically from placement_materials collection."""
    filters = {"type": material_type} if material_type else None
    return retrieve(
        query=query,
        collections=["placement_materials"],
        top_k=top_k,
        filters=filters,
    )


def retrieve_with_filters(
    query: str,
    collections: List[str],
    where: Dict[str, Any],
    top_k: int = 10,
) -> RetrievalResponse:
    """Retrieve across specified collections with explicit filters."""
    return retrieve(
        query=query,
        collections=collections,
        top_k=top_k,
        filters=where,
    )
