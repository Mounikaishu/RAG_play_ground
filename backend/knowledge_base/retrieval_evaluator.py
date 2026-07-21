"""
retrieval_evaluator.py — Retrieval Engine Quality Benchmark Harness.

Executes benchmark test queries to evaluate retrieval precision, filter detection,
collection distribution, average similarity score, and execution latency.
"""

import time
import logging
from typing import List

from knowledge_base.retrieval import retrieve
from knowledge_base.context_builder import build_context

logger = logging.getLogger("uvicorn.error")

BENCHMARK_QUERIES = [
    "Which alumni joined Google?",
    "Show Amazon interview questions.",
    "Who has AWS skills?",
    "Find resumes with Machine Learning projects.",
    "Which interview experiences are Hard?",
]


def evaluate_retrieval(queries: List[str] = None) -> dict:
    """
    Run evaluation benchmark on target queries and print detailed metrics.
    """
    test_queries = queries or BENCHMARK_QUERIES

    print("\n" + "=" * 75)
    print("🧪 RETRIEVAL ENGINE EVALUATION BENCHMARK")
    print("=" * 75)

    eval_results = []
    total_latency_ms = 0.0

    for i, q in enumerate(test_queries, 1):
        print(f"\n[{i}/{len(test_queries)}] Query: \"{q}\"")

        response = retrieve(query=q, top_k=5)
        total_latency_ms += response.execution_time_ms

        avg_score = 0.0
        if response.results:
            avg_score = sum(r.similarity_score for r in response.results) / len(response.results)

        print(f"   📊 Found {response.total_found} chunks in {response.execution_time_ms} ms")
        print(f"   🎯 Distribution: {response.collection_distribution}")
        print(f"   ⭐ Avg Similarity: {avg_score:.2f}%")
        print(f"   🏷️ Filters Applied: {response.query_analysis.filters}")

        print("\n   Top Retrieved Chunks:")
        for r_idx, r in enumerate(response.results[:3], 1):
            comp_info = f" ({r.company})" if r.company else ""
            print(f"      [{r_idx}] {r.collection} | {r.section} | Score: {r.similarity_score:.1f}% | {r.source_file}{comp_info}")
            print(f"          Snippet: {r.content[:120].strip()}...")

        eval_results.append({
            "query": q,
            "latency_ms": response.execution_time_ms,
            "found": response.total_found,
            "avg_similarity": round(avg_score, 2),
            "distribution": response.collection_distribution,
            "filters": response.query_analysis.filters,
        })

    avg_latency = total_latency_ms / len(test_queries) if test_queries else 0.0

    print("\n" + "=" * 75)
    print("📊 EVALUATION SUMMARY")
    print("=" * 75)
    print(f"   Total Queries Evaluated: {len(test_queries)}")
    print(f"   Average Latency:          {avg_latency:.2f} ms")
    print("=" * 75 + "\n")

    return {
        "summary": {
            "total_queries": len(test_queries),
            "avg_latency_ms": round(avg_latency, 2),
        },
        "query_details": eval_results,
    }


if __name__ == "__main__":
    evaluate_retrieval()
