"""
Ingestion Pipeline — Production Document Processing Engine for PlaceAI RAG.

Pipelines:
1. Alumni Resume Pipeline       — Docling parse → LLM Metadata → Section Chunks → ChromaDB
2. Interview Experience Pipeline — Docling parse → Metadata → Section Chunks → ChromaDB
3. Placement Materials Pipeline  — Docling/Flat parse → Categorize → Chunks → ChromaDB

Features:
- Automatic Document Classifier (content + filename signals)
- Stage-by-Stage Telemetry Logging with Execution Timings:
    Scanning... -> Parsing... -> Cleaning... -> Metadata extraction... -> Chunking... -> Embedding... -> Stored into Chroma... -> Finished
- Rich ChromaDB metadata per chunk
- Extended registry tracking
"""

import time
import logging
import os
import traceback
from typing import List, Dict, Any

from knowledge_base.file_scanner import FileInfo
from knowledge_base.classifier import classify_document
from knowledge_base.ingestion_registry import (
    is_file_ingested,
    record_ingestion,
)
from knowledge_base.alumni_metadata_extractor import (
    extract_alumni_metadata,
    extract_interview_metadata_from_filename,
    extract_interview_metadata_from_content,
)
from knowledge_base.collections import get_collection
from chunker import chunk_text_with_overlap
from pdf_loader import load_pdf

# Docling-based structured preprocessing
from knowledge_base.docling_parser import parse_pdf as docling_parse_pdf, docling_available
from knowledge_base.docling_chunker import chunk_parsed_document, DocChunk

logger = logging.getLogger("uvicorn.error")


def _log_stage(filename: str, stage: str, elapsed: float = None):
    """Format stage-by-stage timing logs."""
    time_str = f" ({elapsed:.3f}s)" if elapsed is not None else ""
    print(f"   ⏱️ [{filename}] {stage}...{time_str}")


def _parse_file(file_info: FileInfo, document_type: str = "Unknown"):
    """Parse PDF with Docling, fallback to pdf_loader."""
    if file_info.extension != ".pdf":
        raise ValueError(f"Unsupported file type: {file_info.extension}")

    if docling_available():
        try:
            return docling_parse_pdf(file_info.path, document_type=document_type)
        except Exception as exc:
            logger.warning("⚠️ Docling parse failed for %s (%s). Falling back to pdf_loader.", file_info.filename, exc)

    flat_text = load_pdf(file_info.path)
    from dataclasses import dataclass, field as dc_field

    @dataclass
    class _FlatParsedOutput:
        document_type: str
        document_name: str
        metadata: dict
        sections: list = dc_field(default_factory=list)
        tables: list = dc_field(default_factory=list)
        figures: list = dc_field(default_factory=list)
        full_text: str = ""

    return _FlatParsedOutput(
        document_type=document_type,
        document_name=file_info.filename,
        metadata={"filename": file_info.filename, "page_count": 1, "document_title": file_info.filename},
        full_text=flat_text,
    )


def _generate_doc_id(folder_type: str, filename: str, chunk_index: int) -> str:
    """Generate a unique document ID for a chunk."""
    base = filename.rsplit(".", 1)[0]
    safe_name = base.lower().replace(" ", "_").replace("-", "_")
    return f"{folder_type}_{safe_name}_chunk_{chunk_index}"


# ──────────────────────────────────────────────────────────
# Pipeline 1: Alumni Resume
# ──────────────────────────────────────────────────────────

def ingest_alumni_resume(file_info: FileInfo) -> dict:
    """Ingest Alumni Resume PDF using Docling + rich metadata extraction."""
    t_start = time.time()
    fname = file_info.filename
    print(f"\n📄 Starting processing: {fname}")

    # Stage: Parsing
    t0 = time.time()
    _log_stage(fname, "Parsing")
    parsed = _parse_file(file_info, document_type="Alumni Resume")
    t_parse = time.time() - t0
    _log_stage(fname, "Cleaning", t_parse)

    if not parsed.full_text.strip() and not parsed.sections:
        return {"status": "skipped", "reason": "empty file"}

    # Stage: Metadata extraction
    t0 = time.time()
    _log_stage(fname, "Metadata extraction")
    meta = extract_alumni_metadata(parsed.full_text)
    t_meta = time.time() - t0
    _log_stage(fname, "Metadata extraction complete", t_meta)

    # Stage: Chunking
    t0 = time.time()
    _log_stage(fname, "Chunking")
    if parsed.sections:
        doc_chunks: List[DocChunk] = chunk_parsed_document(parsed)
    else:
        raw_chunks = chunk_text_with_overlap(parsed.full_text, chunk_size=400, overlap=80)
        doc_chunks = [
            DocChunk(
                text=c, section_title="Summary", page_number=1,
                chunk_index=i, document_type="Alumni Resume",
                source_file=fname, chunk_source="section",
            ) for i, c in enumerate(raw_chunks)
        ]
    t_chunk = time.time() - t0
    _log_stage(fname, f"Chunking complete ({len(doc_chunks)} chunks)", t_chunk)

    if not doc_chunks:
        return {"status": "skipped", "reason": "no chunks generated"}

    # Stage: Embedding & ChromaDB Store
    t0 = time.time()
    _log_stage(fname, "Embedding & Storing into Chroma")
    collection = get_collection("alumni_resumes")
    ids, texts, metas = [], [], []

    skills_str = ", ".join(meta.get("skills", []))
    certs_str = ", ".join(meta.get("certifications", []))
    projects_str = ", ".join(meta.get("projects", []))

    for chunk in doc_chunks:
        doc_id = _generate_doc_id("alumni", fname, chunk.chunk_index)
        ids.append(doc_id)
        texts.append(chunk.text)
        metas.append({
            "document_type": "resume",
            "student_name": meta["student_name"],
            "email": meta.get("email", ""),
            "company": meta["company"],
            "role": meta["role"],
            "department": meta["department"],
            "batch": meta["graduation_year"],
            "graduation_year": meta["graduation_year"],
            "cgpa": meta.get("cgpa", "N/A"),
            "skills": skills_str,
            "certifications": certs_str,
            "projects": projects_str,
            "section_title": chunk.section_title,
            "section": chunk.section_title,
            "page_number": chunk.page_number,
            "page": chunk.page_number,
            "chunk_source": chunk.chunk_source,
            "source_file": fname,
            "chunk_index": chunk.chunk_index,
            "category": "alumni_resume",
        })

    collection.upsert(documents=texts, ids=ids, metadatas=metas)
    t_store = time.time() - t0
    _log_stage(fname, "Stored into Chroma", t_store)

    total_duration = time.time() - t_start

    # Record Telemetry
    record_ingestion(
        file_hash=file_info.file_hash,
        filename=fname,
        folder_type=file_info.folder_type,
        collection="alumni_resumes_collection",
        chunk_count=len(doc_chunks),
        document_type="Alumni Resume",
        pages=parsed.metadata.get("page_count", 1),
        ingestion_duration_sec=total_duration,
        processing_status="success",
        metadata={
            "student_name": meta["student_name"],
            "company": meta["company"],
            "role": meta["role"],
        },
    )

    _log_stage(fname, "Finished", total_duration)
    return {
        "status": "success",
        "filename": fname,
        "chunks": len(doc_chunks),
        "duration_sec": total_duration,
        "metadata": meta,
    }


# ──────────────────────────────────────────────────────────
# Pipeline 2: Interview Experience
# ──────────────────────────────────────────────────────────

def ingest_interview_experience(file_info: FileInfo) -> dict:
    """Ingest Interview Experience PDF using Docling + rich metadata extraction."""
    t_start = time.time()
    fname = file_info.filename
    print(f"\n📄 Starting processing: {fname}")

    # Stage: Parsing
    t0 = time.time()
    _log_stage(fname, "Parsing")
    parsed = _parse_file(file_info, document_type="Interview Experience")
    t_parse = time.time() - t0
    _log_stage(fname, "Cleaning", t_parse)

    if not parsed.full_text.strip() and not parsed.sections:
        return {"status": "skipped", "reason": "empty file"}

    # Stage: Metadata extraction
    t0 = time.time()
    _log_stage(fname, "Metadata extraction")
    fn_meta = extract_interview_metadata_from_filename(fname)
    content_meta = extract_interview_metadata_from_content(parsed.full_text)

    comp = content_meta["company"] if content_meta["company"] != "Unknown" else fn_meta["company"]
    role = content_meta["role"] if content_meta["role"] != "Software Engineer" else fn_meta["role"]

    meta = {
        "company": comp,
        "role": role,
        "job_type": content_meta.get("job_type", "FTE"),
        "difficulty": content_meta.get("difficulty", "Medium"),
        "eligibility": content_meta.get("eligibility", "Not Specified"),
        "package": content_meta.get("package", "Not Specified"),
        "interview_mode": content_meta.get("interview_mode", "Online"),
        "rounds": content_meta.get("rounds", ["Technical Round 1"]),
        "technologies": content_meta.get("technologies", []),
        "dsa_topics": content_meta.get("dsa_topics", []),
        "system_design_topics": content_meta.get("system_design_topics", []),
        "behavioral_topics": content_meta.get("behavioral_topics", []),
    }
    t_meta = time.time() - t0
    _log_stage(fname, "Metadata extraction complete", t_meta)

    # Stage: Chunking
    t0 = time.time()
    _log_stage(fname, "Chunking")
    if parsed.sections:
        doc_chunks: List[DocChunk] = chunk_parsed_document(parsed)
    else:
        raw_chunks = chunk_text_with_overlap(parsed.full_text, chunk_size=400, overlap=80)
        doc_chunks = [
            DocChunk(
                text=c, section_title="Interview Experience", page_number=1,
                chunk_index=i, document_type="Interview Experience",
                source_file=fname, chunk_source="section",
            ) for i, c in enumerate(raw_chunks)
        ]
    t_chunk = time.time() - t0
    _log_stage(fname, f"Chunking complete ({len(doc_chunks)} chunks)", t_chunk)

    if not doc_chunks:
        return {"status": "skipped", "reason": "no chunks generated"}

    # Stage: Embedding & ChromaDB Store
    t0 = time.time()
    _log_stage(fname, "Embedding & Storing into Chroma")
    collection = get_collection("interview_experiences")
    ids, texts, metas = [], [], []

    rounds_str = ", ".join(meta["rounds"])
    tech_str = ", ".join(meta["technologies"])
    dsa_str = ", ".join(meta["dsa_topics"])
    sys_str = ", ".join(meta["system_design_topics"])

    for chunk in doc_chunks:
        doc_id = _generate_doc_id("interview", fname, chunk.chunk_index)
        ids.append(doc_id)
        texts.append(chunk.text)
        metas.append({
            "document_type": "interview_experience",
            "company": meta["company"],
            "role": meta["role"],
            "job_type": meta["job_type"],
            "difficulty": meta["difficulty"],
            "round": meta["rounds"][0] if meta["rounds"] else "Technical Round 1",
            "rounds": rounds_str,
            "section_title": chunk.section_title,
            "section": chunk.section_title,
            "page_number": chunk.page_number,
            "page": chunk.page_number,
            "technologies": tech_str,
            "dsa_topics": dsa_str,
            "system_design_topics": sys_str,
            "chunk_source": chunk.chunk_source,
            "source_file": fname,
            "chunk_index": chunk.chunk_index,
            "category": "interview",
        })

    collection.upsert(documents=texts, ids=ids, metadatas=metas)
    t_store = time.time() - t0
    _log_stage(fname, "Stored into Chroma", t_store)

    total_duration = time.time() - t_start

    # Record Telemetry
    record_ingestion(
        file_hash=file_info.file_hash,
        filename=fname,
        folder_type=file_info.folder_type,
        collection="interview_experiences",
        chunk_count=len(doc_chunks),
        document_type="Interview Experience",
        pages=parsed.metadata.get("page_count", 1),
        ingestion_duration_sec=total_duration,
        processing_status="success",
        metadata={
            "company": meta["company"],
            "role": meta["role"],
            "difficulty": meta["difficulty"],
        },
    )

    _log_stage(fname, "Finished", total_duration)
    return {
        "status": "success",
        "filename": fname,
        "chunks": len(doc_chunks),
        "duration_sec": total_duration,
        "metadata": meta,
    }


# ──────────────────────────────────────────────────────────
# Pipeline 3: Placement Materials
# ──────────────────────────────────────────────────────────

def ingest_placement_material(file_info: FileInfo) -> dict:
    """Ingest Placement Material PDF."""
    t_start = time.time()
    fname = file_info.filename
    print(f"\n📄 Starting processing: {fname}")

    _log_stage(fname, "Parsing")
    parsed = _parse_file(file_info, document_type="Placement Material")
    _log_stage(fname, "Cleaning")

    if not parsed.full_text.strip():
        return {"status": "skipped", "reason": "empty file"}

    _log_stage(fname, "Metadata extraction")
    material_type = "placement_guide"
    if "dsa" in fname.lower():
        material_type = "dsa_questions"
    elif "roadmap" in fname.lower():
        material_type = "roadmap"

    _log_stage(fname, "Chunking")
    chunks = chunk_text_with_overlap(parsed.full_text, chunk_size=500, overlap=100)

    _log_stage(fname, "Embedding & Storing into Chroma")
    collection = get_collection("placement_materials")
    ids, texts, metas = [], [], []

    for i, c in enumerate(chunks):
        doc_id = _generate_doc_id("placement", fname, i)
        ids.append(doc_id)
        texts.append(c)
        metas.append({
            "document_type": "placement_material",
            "type": material_type,
            "source_file": fname,
            "chunk_index": i,
            "category": "placement_material",
        })

    collection.upsert(documents=texts, ids=ids, metadatas=metas)
    total_duration = time.time() - t_start

    record_ingestion(
        file_hash=file_info.file_hash,
        filename=fname,
        folder_type=file_info.folder_type,
        collection="placement_materials_collection",
        chunk_count=len(chunks),
        document_type="Placement Material",
        pages=parsed.metadata.get("page_count", 1),
        ingestion_duration_sec=total_duration,
        processing_status="success",
        metadata={"type": material_type},
    )

    _log_stage(fname, "Finished", total_duration)
    return {"status": "success", "filename": fname, "chunks": len(chunks), "duration_sec": total_duration}


# ──────────────────────────────────────────────────────────
# Dispatcher with Automatic Classification
# ──────────────────────────────────────────────────────────

PIPELINE_MAP = {
    "Alumni Resume": ingest_alumni_resume,
    "Interview Experience": ingest_interview_experience,
    "Placement Material": ingest_placement_material,
    "Student Resume": ingest_alumni_resume,
}


def process_files(files: List[FileInfo], folder_type: str) -> dict:
    """
    Process a list of PDF files through the appropriate pipeline.
    Uses automatic classifier to inspect document content and route correctly.
    """
    processed = 0
    skipped = 0
    errors = 0
    details = []

    for file_info in files:
        if is_file_ingested(file_info.file_hash):
            skipped += 1
            details.append({"filename": file_info.filename, "status": "skipped", "reason": "already ingested"})
            continue

        try:
            # Stage: Scanning & Classification
            _log_stage(file_info.filename, "Scanning")
            parsed_preview = _parse_file(file_info, document_type="Preview")
            detected_type, conf = classify_document(file_info.filename, parsed_preview.full_text[:3000], folder_type)

            pipeline_fn = PIPELINE_MAP.get(detected_type)
            if not pipeline_fn:
                # Fallback to folder_type mapping
                if "interview" in folder_type:
                    pipeline_fn = ingest_interview_experience
                elif "alumni" in folder_type:
                    pipeline_fn = ingest_alumni_resume
                else:
                    pipeline_fn = ingest_placement_material

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
