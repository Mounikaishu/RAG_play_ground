"""
Resume Repository — Department-level multi-document ChromaDB storage.

Uses a single shared collection 'department_resumes' with rich metadata
per chunk, enabling semantic search across all students' resumes.
"""

import chromadb
from collections import defaultdict

# Initialize Chroma client (in-memory for now)
repo_client = chromadb.Client()

REPO_COLLECTION_NAME = "department_resumes"

# In-memory student registry for quick lookups
student_registry = {}
# Format: { "student_name": { "department": ..., "skills": [...], "cgpa": ..., "projects": [...], "experience_summary": ... } }


def get_repo_collection():
    """Get or create the department resumes collection."""
    return repo_client.get_or_create_collection(REPO_COLLECTION_NAME)


def store_resume_to_repository(student_name: str, chunks: list, metadata: dict):
    """
    Stores a student's resume chunks into the shared department collection.

    Each chunk gets metadata: student_name, department, skills, cgpa, projects.
    If a student already exists, their old data is removed first.
    """
    global student_registry

    collection = get_repo_collection()

    # Remove existing data for this student (if re-uploading)
    remove_student(student_name)

    skills_str = ", ".join(metadata.get("skills", []))
    projects_str = ", ".join(metadata.get("projects", []))

    for i, chunk in enumerate(chunks):
        chunk_id = f"repo_{student_name}_{i}"
        collection.add(
            documents=[chunk],
            ids=[chunk_id],
            metadatas=[
                {
                    "student_name": student_name,
                    "department": metadata.get("department", "Not Specified"),
                    "skills": skills_str,
                    "cgpa": metadata.get("cgpa", "N/A"),
                    "projects": projects_str,
                }
            ],
        )

    # Register in memory
    student_registry[student_name] = {
        "department": metadata.get("department", "Not Specified"),
        "skills": metadata.get("skills", []),
        "cgpa": metadata.get("cgpa", "N/A"),
        "projects": metadata.get("projects", []),
        "experience_summary": metadata.get("experience_summary", ""),
        "chunk_count": len(chunks),
    }

    print(f"✅ Resume '{student_name}' stored in repository ({len(chunks)} chunks)")


def search_candidates(query: str, k: int = 10) -> dict:
    """
    Semantic search across all resumes in the repository.

    Returns:
        {
            "student_name": {
                "chunks": [relevant text chunks],
                "metadata": { student metadata },
                "relevance_scores": [distances]
            }
        }
    """
    collection = get_repo_collection()

    if collection.count() == 0:
        return {}

    # Query with higher k to get enough coverage across students
    n_results = min(k * 3, collection.count())

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    # Group results by student
    grouped = defaultdict(lambda: {"chunks": [], "distances": []})

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        name = meta["student_name"]
        grouped[name]["chunks"].append(doc)
        grouped[name]["distances"].append(dist)
        grouped[name]["metadata"] = meta

    # Build final result with average relevance per student
    candidate_results = {}
    for name, data in grouped.items():
        avg_distance = sum(data["distances"]) / len(data["distances"])
        # Convert distance to a 0-100 relevance score (lower distance = higher relevance)
        # ChromaDB default uses L2 distance; typical range is 0-2
        relevance_score = max(0, min(100, round((1 - avg_distance / 2) * 100)))

        candidate_results[name] = {
            "chunks": data["chunks"][:3],  # Top 3 most relevant chunks
            "metadata": {
                **data["metadata"],
                "skills": data["metadata"].get("skills", "").split(", ") if data["metadata"].get("skills") else [],
                "projects": data["metadata"].get("projects", "").split(", ") if data["metadata"].get("projects") else [],
            },
            "relevance_score": relevance_score,
        }

    # Sort by relevance (highest first)
    sorted_results = dict(
        sorted(candidate_results.items(), key=lambda x: x[1]["relevance_score"], reverse=True)
    )

    return sorted_results


def get_all_students() -> list:
    """Returns list of all students in the repository with their metadata."""
    return [
        {"name": name, **info}
        for name, info in student_registry.items()
    ]


def remove_student(student_name: str) -> bool:
    """Removes a specific student's data from the repository."""
    global student_registry

    collection = get_repo_collection()

    # Find and delete all chunks belonging to this student
    try:
        # Get all IDs for this student
        all_data = collection.get(
            where={"student_name": student_name},
            include=["metadatas"],
        )

        if all_data["ids"]:
            collection.delete(ids=all_data["ids"])
            print(f"🗑️ Removed {len(all_data['ids'])} chunks for '{student_name}'")
    except Exception as e:
        print(f"⚠️ Error removing student chunks: {e}")

    # Remove from registry
    if student_name in student_registry:
        del student_registry[student_name]
        return True

    return False


def clear_repository():
    """Clears the entire department resume repository."""
    global student_registry

    try:
        repo_client.delete_collection(REPO_COLLECTION_NAME)
        print("🗑️ Repository collection deleted")
    except Exception:
        print("No existing repository collection to delete")

    student_registry.clear()


def get_student_count() -> int:
    """Returns the number of students in the repository."""
    return len(student_registry)
