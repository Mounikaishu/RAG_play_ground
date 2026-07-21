"""
Knowledge Base Loader — Startup orchestrator for the ingestion pipeline.

Called on FastAPI startup to:
1. Ensure data directories exist
2. Remove non-PDF files from data folders
3. Scan all data folders for PDF files only
4. Process new files through the appropriate pipelines
5. Report ingestion summary

Supports:
- Incremental ingestion (only new/modified files)
- Full rebuild via rebuild_knowledge_base()
- Graceful error handling per-file
"""

import time
import json
import os

from knowledge_base.file_scanner import scan_all_folders, ensure_data_directories
from knowledge_base.ingestion_pipeline import process_files
from knowledge_base.ingestion_registry import clear_registry, get_registry_stats
from knowledge_base.collections import get_collection_count



def load_knowledge_base():
    """
    Main startup function — loads and processes all institutional knowledge.

    Flow:
    1. Create data directories if missing
    2. Purge non-PDF files and scan data folders for PDFs only
    3. Process new PDF files (skip already-ingested)
    4. Print summary
    """
    print("\n" + "=" * 70)
    print("🏛️  INSTITUTIONAL KNOWLEDGE BASE — LOADING")
    print("=" * 70)
    start_time = time.time()


    # Step 1: Ensure directories
    ensure_data_directories()

    # Step 2: Scan all folders (PDF only; non-PDF files are deleted)
    print("\n📂 Scanning data folders for new files...")
    folder_files = scan_all_folders()

    # Step 3: Process each folder
    total_processed = 0
    total_skipped = 0
    total_errors = 0

    for folder_type, files in folder_files.items():
        if not files:
            continue

        print(f"\n🔄 Processing {folder_type} ({len(files)} files)...")
        result = process_files(files, folder_type)

        total_processed += result["processed"]
        total_skipped += result["skipped"]
        total_errors += result["errors"]

        # Print per-folder summary
        if result["processed"] > 0:
            print(f"   ✅ {result['processed']} new files ingested")
        if result["skipped"] > 0:
            print(f"   ⏩ {result['skipped']} files skipped (already ingested)")
        if result["errors"] > 0:
            print(f"   ❌ {result['errors']} files failed")

    # Step 4: Summary
    elapsed = time.time() - start_time
    print("\n" + "-" * 70)
    print("📊 INGESTION SUMMARY")
    print("-" * 70)
    print(f"   New files processed:  {total_processed}")
    print(f"   Files skipped:        {total_skipped}")
    print(f"   Errors:               {total_errors}")
    print(f"   Time elapsed:         {elapsed:.2f}s")

    # Collection stats
    print("\n📦 COLLECTION SIZES:")
    collections = [
        "institutional_kb",
        "interview_experiences",
        "alumni_resumes",
        "placement_materials",
        "student_resumes",
    ]
    for coll in collections:
        count = get_collection_count(coll)
        if count > 0:
            print(f"   • {coll}: {count} chunks")

    # Registry stats
    reg_stats = get_registry_stats()
    print(f"\n📋 Registry: {reg_stats['total_files']} files tracked")
    if reg_stats.get("by_folder"):
        for folder, count in reg_stats["by_folder"].items():
            print(f"   • {folder}: {count} files")

    print("\n" + "=" * 70)
    print("🏛️  KNOWLEDGE BASE READY")
    print("=" * 70 + "\n")


def rebuild_knowledge_base():
    """
    Force a complete rebuild of all file-based collections.

    Clears the ingestion registry and reprocesses all files.
    Does NOT clear synthetic seed data.
    """
    print("\n🔄 REBUILDING KNOWLEDGE BASE...")
    print("   Clearing ingestion registry...")
    clear_registry()

    # Clear file-based collections (preserve synthetic seed data)
    from knowledge_base.collections import client
    for coll_name in ["alumni_resumes_collection", "placement_materials_collection"]:
        try:
            client.delete_collection(coll_name)
            print(f"   🗑️ Cleared {coll_name}")
        except Exception:
            pass

    # Re-run the loader
    load_knowledge_base()


def reset_database():
    """
    Wipe all ChromaDB collections and the ingestion registry.
    Use before a full PDF-only re-seed.
    """
    import shutil
    from knowledge_base.collections import CHROMA_DB_PATH

    print("\n🗑️  RESETTING KNOWLEDGE BASE DATABASE...")

    # Close any open ChromaDB handles by deleting the directory
    if os.path.exists(CHROMA_DB_PATH):
        shutil.rmtree(CHROMA_DB_PATH)
        print(f"   Removed {CHROMA_DB_PATH}")

    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    clear_registry()
    print("   Database and registry cleared.")
