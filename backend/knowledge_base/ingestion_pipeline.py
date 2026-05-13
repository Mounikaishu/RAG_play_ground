"""
Ingestion Pipeline — Core processing engine for multi-document RAG.

Three pipelines:
1. Alumni Resume Pipeline — Extract text, LLM metadata, chunk, store in alumni_resumes_collection
2. Interview Experience Pipeline — Parse metadata from filename+content, chunk, store
3. Placement Materials Pipeline — Categorize content, chunk, store

Each pipeline:
- Checks file hash against registry for deduplication
- Handles errors gracefully per-file
- Records successful ingestion with metadata
"""

import os
import traceback
from typing import List

from knowledge_base.file_scanner import FileInfo
from knowledge_base.ingestion_registry import (
    is_file_ingested,
    record_ingestion,
)
from knowledge_base.alumni_metadata_extractor import (
    extract_alumni_metadata,
    extract_interview_metadata_from_filename,
    extract_interview_metadata_from_content,
)
from knowledge_base.collections import (
    store_kb_document,
    store_kb_documents_batch,
    get_collection,
)
from chunker import chunk_text_with_overlap
from pdf_loader import load_pdf


def _read_file(file_info: FileInfo) -> str:
    """Read text content from a PDF or TXT file."""
    if file_info.extension == ".pdf":
        return load_pdf(file_info.path)
    elif file_info.extension == ".txt":
        with open(file_info.path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {file_info.extension}")


def _generate_doc_id(folder_type: str, filename: str, chunk_index: int) -> str:
    """Generate a unique document ID for a chunk."""
    base = filename.rsplit(".", 1)[0]  # Remove extension
    safe_name = base.lower().replace(" ", "_").replace("-", "_")
    return f"{folder_type}_{safe_name}_chunk_{chunk_index}"


# ──────────────────────────────────────────────────────────
# Pipeline 1: Alumni Resumes
# ──────────────────────────────────────────────────────────

def ingest_alumni_resume(file_info: FileInfo) -> dict:
    """
    Process a single alumni resume file.

    Steps:
    1. Read PDF/TXT text
    2. Extract metadata via Gemini (name, company, role, dept, batch, skills)
    3. Chunk text with overlap
    4. Store chunks + metadata in alumni_resumes_collection

    Returns summary dict with ingestion results.
    """
    print(f"  📄 Processing alumni resume: {file_info.filename}")

    # Read content
    text = _read_file(file_info)
    if not text.strip():
        return {"status": "skipped", "reason": "empty file"}

    # Extract metadata using LLM
    metadata = extract_alumni_metadata(text)
    print(f"     → Extracted: {metadata['student_name']} | {metadata['company']} | {metadata['role']}")

    # Chunk text
    chunks = chunk_text_with_overlap(text, chunk_size=500, overlap=100)
    if not chunks:
        return {"status": "skipped", "reason": "no chunks generated"}

    # Store each chunk with metadata
    collection = get_collection("alumni_resumes")
    ids = []
    texts = []
    metas = []

    skills_str = ", ".join(metadata.get("skills", []))

    for i, chunk in enumerate(chunks):
        doc_id = _generate_doc_id("alumni", file_info.filename, i)
        ids.append(doc_id)
        texts.append(chunk)
        metas.append({
            "student_name": metadata["student_name"],
            "company": metadata["company"],
            "role": metadata["role"],
            "department": metadata["department"],
            "batch": metadata["batch"],
            "skills": skills_str,
            "source_file": file_info.filename,
            "chunk_index": i,
            "category": "alumni_resume",
        })

    # Batch upsert
    collection.upsert(documents=texts, ids=ids, metadatas=metas)

    # Record in registry
    record_ingestion(
        file_hash=file_info.file_hash,
        filename=file_info.filename,
        folder_type=file_info.folder_type,
        collection="alumni_resumes_collection",
        chunk_count=len(chunks),
        metadata={
            "student_name": metadata["student_name"],
            "company": metadata["company"],
            "role": metadata["role"],
        },
    )

    return {
        "status": "success",
        "filename": file_info.filename,
        "chunks": len(chunks),
        "metadata": metadata,
    }


# ──────────────────────────────────────────────────────────
# Pipeline 2: Interview Experiences
# ──────────────────────────────────────────────────────────

def ingest_interview_experience(file_info: FileInfo) -> dict:
    """
    Process a single interview experience file.

    Steps:
    1. Read content
    2. Parse metadata from filename + content
    3. Chunk content
    4. Store in interview_experiences collection

    Returns summary dict.
    """
    print(f"  📄 Processing interview experience: {file_info.filename}")

    text = _read_file(file_info)
    if not text.strip():
        return {"status": "skipped", "reason": "empty file"}

    # Extract metadata from filename + content
    filename_meta = extract_interview_metadata_from_filename(file_info.filename)
    content_meta = extract_interview_metadata_from_content(text)

    # Merge: content metadata overrides filename metadata if more specific
    metadata = {
        "company": content_meta.get("company", filename_meta["company"]),
        "role": content_meta.get("role", filename_meta["role"]),
        "round": content_meta.get("round", filename_meta["round"]),
        "difficulty": content_meta.get("difficulty", "Medium"),
    }

    # Use content metadata company only if it's not "Unknown"
    if metadata["company"] == "Unknown":
        metadata["company"] = filename_meta["company"]

    print(f"     → {metadata['company']} | {metadata['role']} | Round: {metadata['round']}")

    # Chunk text
    chunks = chunk_text_with_overlap(text, chunk_size=500, overlap=100)
    if not chunks:
        return {"status": "skipped", "reason": "no chunks generated"}

    # Store chunks
    collection = get_collection("interview_experiences")
    ids = []
    texts = []
    metas = []

    for i, chunk in enumerate(chunks):
        doc_id = _generate_doc_id("interview", file_info.filename, i)
        ids.append(doc_id)
        texts.append(chunk)
        metas.append({
            "company": metadata["company"],
            "role": metadata["role"],
            "round": metadata["round"],
            "difficulty": metadata["difficulty"],
            "source_file": file_info.filename,
            "chunk_index": i,
            "category": "interview",
        })

    collection.upsert(documents=texts, ids=ids, metadatas=metas)

    # Record in registry
    record_ingestion(
        file_hash=file_info.file_hash,
        filename=file_info.filename,
        folder_type=file_info.folder_type,
        collection="interview_experiences",
        chunk_count=len(chunks),
        metadata=metadata,
    )

    return {
        "status": "success",
        "filename": file_info.filename,
        "chunks": len(chunks),
        "metadata": metadata,
    }


# ──────────────────────────────────────────────────────────
# Pipeline 3: Placement Materials
# ──────────────────────────────────────────────────────────

def _categorize_placement_material(text: str, filename: str) -> str:
    """Categorize placement material by content keywords."""
    text_lower = text.lower()
    filename_lower = filename.lower()

    if any(kw in text_lower or kw in filename_lower for kw in ["ats", "resume", "cv"]):
        return "ats_guide"
    elif any(kw in text_lower or kw in filename_lower for kw in ["roadmap", "career path", "learning path"]):
        return "roadmap"
    elif any(kw in text_lower or kw in filename_lower for kw in ["dsa", "leetcode", "algorithm", "data structure"]):
        return "dsa_questions"
    elif any(kw in text_lower or kw in filename_lower for kw in ["strategy", "timeline", "preparation"]):
        return "strategy"
    elif any(kw in text_lower or kw in filename_lower for kw in ["system design"]):
        return "system_design"
    elif any(kw in text_lower or kw in filename_lower for kw in ["behavioral", "hr", "soft skill"]):
        return "behavioral_guide"
    else:
        return "general_resource"


def ingest_placement_material(file_info: FileInfo) -> dict:
    """
    Process a single placement material file.

    Steps:
    1. Read content
    2. Categorize by content analysis
    3. Chunk and store in placement_materials_collection

    Returns summary dict.
    """
    print(f"  📄 Processing placement material: {file_info.filename}")

    text = _read_file(file_info)
    if not text.strip():
        return {"status": "skipped", "reason": "empty file"}

    # Categorize
    material_type = _categorize_placement_material(text, file_info.filename)
    print(f"     → Category: {material_type}")

    # Chunk text
    chunks = chunk_text_with_overlap(text, chunk_size=500, overlap=100)
    if not chunks:
        return {"status": "skipped", "reason": "no chunks generated"}

    # Store chunks
    collection = get_collection("placement_materials")
    ids = []
    texts = []
    metas = []

    for i, chunk in enumerate(chunks):
        doc_id = _generate_doc_id("placement", file_info.filename, i)
        ids.append(doc_id)
        texts.append(chunk)
        metas.append({
            "type": material_type,
            "source_file": file_info.filename,
            "chunk_index": i,
            "category": "placement_material",
        })

    collection.upsert(documents=texts, ids=ids, metadatas=metas)

    # Record in registry
    record_ingestion(
        file_hash=file_info.file_hash,
        filename=file_info.filename,
        folder_type=file_info.folder_type,
        collection="placement_materials_collection",
        chunk_count=len(chunks),
        metadata={"type": material_type},
    )

    return {
        "status": "success",
        "filename": file_info.filename,
        "chunks": len(chunks),
        "metadata": {"type": material_type},
    }


# ──────────────────────────────────────────────────────────
# Batch Processing
# ──────────────────────────────────────────────────────────

PIPELINE_MAP = {
    "alumni_resumes": ingest_alumni_resume,
    "interview_experiences": ingest_interview_experience,
    "placement_materials": ingest_placement_material,
}


def process_files(files: List[FileInfo], folder_type: str) -> dict:
    """
    Process a list of files through the appropriate pipeline.
    Skips already-ingested files (by hash).

    Returns summary: {processed, skipped, errors, details}
    """
    pipeline_fn = PIPELINE_MAP.get(folder_type)
    if not pipeline_fn:
        print(f"⚠️ No pipeline for folder type: {folder_type}")
        return {"processed": 0, "skipped": 0, "errors": 0, "details": []}

    processed = 0
    skipped = 0
    errors = 0
    details = []

    for file_info in files:
        # Dedup check
        if is_file_ingested(file_info.file_hash):
            skipped += 1
            details.append({"filename": file_info.filename, "status": "skipped", "reason": "already ingested"})
            continue

        try:
            result = pipeline_fn(file_info)
            if result["status"] == "success":
                processed += 1
            else:
                skipped += 1
            details.append(result)
        except Exception as e:
            errors += 1
            print(f"  ❌ Error processing {file_info.filename}: {e}")
            traceback.print_exc()
            details.append({"filename": file_info.filename, "status": "error", "error": str(e)})

    return {
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }
