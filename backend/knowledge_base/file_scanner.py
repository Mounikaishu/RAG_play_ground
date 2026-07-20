"""
File Scanner — Discovers PDF files in data directories and removes non-PDF inputs.
"""

import os
import hashlib
from dataclasses import dataclass
from typing import List

SUPPORTED_EXTENSIONS = {".pdf"}

DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DATA_FOLDERS = {
    "alumni_resumes": os.path.join(DATA_ROOT, "alumni_resumes"),
    "interview_experiences": os.path.join(DATA_ROOT, "interview_experiences"),
    "placement_materials": os.path.join(DATA_ROOT, "placement_materials"),
}


@dataclass
class FileInfo:
    """Represents a discovered PDF with metadata for ingestion."""
    path: str
    filename: str
    extension: str
    file_hash: str
    folder_type: str
    size_bytes: int = 0


def compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file for deduplication."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return sha256.hexdigest()


def ensure_data_directories():
    """Create data directories if they don't exist."""
    for folder_path in DATA_FOLDERS.values():
        os.makedirs(folder_path, exist_ok=True)
    print(f"📁 Data directories verified: {list(DATA_FOLDERS.keys())}")


def purge_non_pdf_files() -> List[str]:
    """
    Delete any non-PDF files found in data folders.
    PlaceAI accepts PDF input only.
    """
    removed = []
    for folder_path in DATA_FOLDERS.values():
        if not os.path.exists(folder_path):
            continue
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext == ".pdf":
                    continue
                filepath = os.path.join(root, filename)
                try:
                    os.remove(filepath)
                    removed.append(filepath)
                    print(f"🗑️ Removed non-PDF file: {filepath}")
                except Exception as exc:
                    print(f"⚠️ Could not remove {filepath}: {exc}")
    return removed


def scan_folder(folder_type: str) -> List[FileInfo]:
    """Scan a single data folder and return PDF FileInfo objects only."""
    folder_path = DATA_FOLDERS.get(folder_type)
    if not folder_path or not os.path.exists(folder_path):
        return []

    files = []
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "rb") as handle:
                    header = handle.read(4)
                if header != b"%PDF":
                    os.remove(filepath)
                    print(f"🗑️ Removed invalid PDF file: {filepath}")
                    continue

                file_hash = compute_file_hash(filepath)
                size = os.path.getsize(filepath)
                files.append(
                    FileInfo(
                        path=filepath,
                        filename=filename,
                        extension=ext,
                        file_hash=file_hash,
                        folder_type=folder_type,
                        size_bytes=size,
                    )
                )
            except Exception as exc:
                print(f"⚠️ Error scanning {filepath}: {exc}")

    return files


def scan_all_folders() -> dict:
    """Purge non-PDF files, then scan all data folders."""
    ensure_data_directories()
    purge_non_pdf_files()

    results = {}
    total = 0
    for folder_type in DATA_FOLDERS:
        files = scan_folder(folder_type)
        results[folder_type] = files
        total += len(files)

    print(f"📂 Scanned {total} PDF files across {len(DATA_FOLDERS)} folders:")
    for folder_type, files in results.items():
        print(f"   • {folder_type}: {len(files)} files")

    return results
