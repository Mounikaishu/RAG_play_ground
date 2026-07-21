"""
Ingestion Registry — Production Telemetry & Hash Tracking.

Persists ingestion telemetry to disk to prevent duplicate processing and
track pipeline performance parameters:
- checksum (file_hash)
- document_type
- parser_version ("docling-v1.0")
- chunking_version ("semantic-v1.0")
- embedding_model ("bge-small-en-v1.5")
- ingestion_duration_sec
- pages
- processing_status
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "ingestion_registry.json"
)


def _load_registry() -> dict:
    """Load the registry from disk."""
    if not os.path.exists(REGISTRY_PATH):
        return {"files": {}, "last_run": None, "version": "2.0"}
    try:
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return {"files": {}, "last_run": None, "version": "2.0"}


def _save_registry(registry: dict):
    """Save the registry to disk."""
    registry["last_run"] = datetime.now().isoformat()
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def is_file_ingested(file_hash: str) -> bool:
    """Check if a file with this hash has already been ingested successfully."""
    registry = _load_registry()
    entry = registry.get("files", {}).get(file_hash)
    if not entry:
        return False
    return entry.get("processing_status") == "success"


def record_ingestion(
    file_hash: str,
    filename: str,
    folder_type: str,
    collection: str,
    chunk_count: int,
    document_type: str = "Unknown",
    pages: int = 1,
    ingestion_duration_sec: float = 0.0,
    processing_status: str = "success",
    parser_version: str = "docling-v1.0",
    chunking_version: str = "semantic-v1.0",
    embedding_model: str = "bge-small-en-v1.5",
    metadata: Optional[Dict[str, Any]] = None,
):
    """Record extended ingestion telemetry for a file."""
    registry = _load_registry()
    registry["files"][file_hash] = {
        "checksum": file_hash,
        "filename": filename,
        "folder": folder_type,
        "document_type": document_type,
        "collection": collection,
        "chunk_count": chunk_count,
        "pages": pages,
        "parser_version": parser_version,
        "chunking_version": chunking_version,
        "embedding_model": embedding_model,
        "ingestion_duration_sec": round(ingestion_duration_sec, 3),
        "processing_status": processing_status,
        "ingested_at": datetime.now().isoformat(),
        "metadata_summary": metadata or {},
    }
    _save_registry(registry)


def remove_record(file_hash: str):
    """Remove a file record from the registry."""
    registry = _load_registry()
    if file_hash in registry.get("files", {}):
        del registry["files"][file_hash]
        _save_registry(registry)


def clear_registry():
    """Clear the entire registry (forces full re-ingestion)."""
    _save_registry({"files": {}, "last_run": None, "version": "2.0"})
    print("🗑️ Ingestion registry cleared.")


def get_registry_stats() -> dict:
    """Get summary stats from the registry."""
    registry = _load_registry()
    files = registry.get("files", {})

    folder_counts = {}
    doc_type_counts = {}
    for entry in files.values():
        folder = entry.get("folder", "unknown")
        dt = entry.get("document_type", "unknown")
        folder_counts[folder] = folder_counts.get(folder, 0) + 1
        doc_type_counts[dt] = doc_type_counts.get(dt, 0) + 1

    return {
        "total_files": len(files),
        "by_folder": folder_counts,
        "by_document_type": doc_type_counts,
        "last_run": registry.get("last_run"),
    }
