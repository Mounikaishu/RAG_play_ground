"""
logger.py — Structured Observability & Metrics Logger for PlaceAI.

Provides machine-readable structured JSON logging across all RAG pipeline stages.
Supports request_id tracking, latency profiling, chunk counters, confidence metrics, and PII masking.
"""

import json
import time
import logging
import hashlib
from typing import Dict, Any, Optional
from config import MASK_PII_LOGS, LOG_LEVEL

logger = logging.getLogger("placeai.observability")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Standard Stream Handler for FastAPI / Uvicorn
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(ch)


def hash_user_id(user_id: str) -> str:
    """Hashes user ID to protect user privacy in logs."""
    if not user_id or not MASK_PII_LOGS:
        return user_id or "anonymous"
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


def log_pipeline_metrics(
    request_id: str,
    user_id: str,
    rewritten_query: str,
    latencies: Dict[str, float],
    chunk_counts: Dict[str, int],
    collections_searched: list,
    confidence_scores: Dict[str, Any],
    fallback_used: bool = False,
    retry_count: int = 0,
    validation_status: str = "PASSED"
):
    """
    Logs structured JSON metrics for observability monitoring systems (e.g. Datadog, Prometheus, CloudWatch).
    """
    log_event = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "event_type": "rag_pipeline_execution",
        "request_id": request_id,
        "user_id_hash": hash_user_id(user_id),
        "rewritten_query_length": len(rewritten_query),
        "collections_searched": collections_searched,
        "chunk_counts": chunk_counts,
        "latencies_ms": {k: round(v, 2) for k, v in latencies.items()},
        "total_latency_ms": round(sum(latencies.values()), 2),
        "confidence_scores": confidence_scores,
        "fallback_used": fallback_used,
        "retry_count": retry_count,
        "validation_status": validation_status,
    }

    logger.info(json.dumps(log_event))
