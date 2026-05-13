"""
Ingestion Registry — Tracks ingested files to prevent duplicate processing.

Uses a JSON file to persist file hashes, so re-running the ingestion pipeline
only processes new or modified files.
"""

import json
import os
from datetime import datetime
from typing import Optional

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "ingestion_registry.json"
)


def _load_registry() -> dict:
    """Load the registry from disk."""
    if not os.path.exists(REGISTRY_PATH):
        return {"files": {}, "last_run": None, "version": "1.0"}
    try:
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return {"files": {}, "last_run": None, "version": "1.0"}


def _save_registry(registry: dict):
    """Save the registry to disk."""
    registry["last_run"] = datetime.now().isoformat()
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def is_file_ingested(file_hash: str) -> bool:
    """Check if a file with this hash has already been ingested."""
    registry = _load_registry()
    return file_hash in registry.get("files", {})


def record_ingestion(
    file_hash: str,
    filename: str,
    folder_type: str,
    collection: str,
    chunk_count: int,
    metadata: Optional[dict] = None,
):
    """Record a successfully ingested file."""
    registry = _load_registry()
    registry["files"][file_hash] = {
        "filename": filename,
        "folder": folder_type,
        "collection": collection,
        "chunk_count": chunk_count,
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
    _save_registry({"files": {}, "last_run": None, "version": "1.0"})
    print("🗑️ Ingestion registry cleared.")


def get_registry_stats() -> dict:
    """Get summary stats from the registry."""
    registry = _load_registry()
    files = registry.get("files", {})

    folder_counts = {}
    for entry in files.values():
        folder = entry.get("folder", "unknown")
        folder_counts[folder] = folder_counts.get(folder, 0) + 1

    return {
        "total_files": len(files),
        "by_folder": folder_counts,
        "last_run": registry.get("last_run"),
    }
