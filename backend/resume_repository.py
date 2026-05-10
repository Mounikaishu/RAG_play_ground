"""
Resume Repository — Department-level multi-document ChromaDB storage.

Uses a single shared collection 'department_resumes' with rich metadata
per chunk, enabling semantic search across all students' resumes.

NOTE: This module now supports year-specific collections via passing_out_year.
Resumes are stored in both the shared collection and a year-specific collection
(e.g., department_resumes_2028) for year-based filtering.
"""

import chromadb
from collections import defaultdict

# Initialize Chroma client (in-memory for now)
repo_client = chromadb.Client()

REPO_COLLECTION_NAME = "department_resumes"

# In-memory student registry for quick lookups
student_registry = {}
# Format: { "student_name": { "department": ..., "skills": [...], "cgpa": ..., "projects": [...], "experience_summary": ..., "passing_out_year": ... } }


def get_repo_collection(passing_out_year: int = 0):
    """Get or create the department resumes collection.
    If passing_out_year is provided, returns a year-specific collection.
    """
    if passing_out_year:
        name = f"{REPO_COLLECTION_NAME}_{passing_out_year}"
    else:
        name = REPO_COLLECTION_NAME
    return repo_client.get_or_create_collection(name)


def store_resume_to_repository(student_name: str, chunks: list, metadata: dict):
    """
    Stores a student's resume chunks into the shared department collection.

    Each chunk gets metadata: student_name, department, skills, cgpa, projects, passing_out_year.
    If a student already exists, their old data is removed first.
    Stores in both the main collection and the year-specific collection.
    """
    global student_registry

    passing_out_year = metadata.get("passing_out_year", 0)

    # Collections to store in: main + year-specific
    collections = [get_repo_collection()]
    if passing_out_year:
        collections.append(get_repo_collection(passing_out_year))

    # Remove existing data for this student (if re-uploading)
    remove_student(student_name)

    skills_str = ", ".join(metadata.get("skills", []))
    projects_str = ", ".join(metadata.get("projects", []))

    for collection in collections:
        for i, chunk in enumerate(chunks):
            coll_suffix = f"_{passing_out_year}" if passing_out_year and collection != get_repo_collection() else ""
            chunk_id = f"repo_{student_name}{coll_suffix}_{i}"
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
                        "passing_out_year": passing_out_year,
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
        "passing_out_year": passing_out_year,
        "chunk_count": len(chunks),
    }

    print(f"✅ Resume '{student_name}' stored in repository ({len(chunks)} chunks)")


def search_candidates(query: str, k: int = 10, passing_out_year: int = 0) -> dict:
    """
    Semantic search across all resumes in the repository.
    If passing_out_year is specified, searches only that year's collection.

    Returns:
        {
            "student_name": {
                "chunks": [relevant text chunks],
                "metadata": { student metadata },
                "relevance_scores": [distances]
            }
        }
    """
    collection = get_repo_collection(passing_out_year)

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


def get_students_by_year(passing_out_year: int) -> list:
    """Returns students filtered by passing out year."""
    return [
        {"name": name, **info}
        for name, info in student_registry.items()
        if info.get("passing_out_year") == passing_out_year
    ]


def remove_student(student_name: str) -> bool:
    """Removes a specific student's data from the repository (all collections)."""
    global student_registry

    # Get the student's passing_out_year for year-specific cleanup
    passing_out_year = 0
    if student_name in student_registry:
        passing_out_year = student_registry[student_name].get("passing_out_year", 0)

    # Clean from main collection
    _remove_from_collection(get_repo_collection(), student_name)

    # Clean from year-specific collection if applicable
    if passing_out_year:
        _remove_from_collection(get_repo_collection(passing_out_year), student_name)

    # Remove from registry
    if student_name in student_registry:
        del student_registry[student_name]
        return True

    return False


def _remove_from_collection(collection, student_name: str):
    """Remove all chunks for a student from a specific collection."""
    try:
        all_data = collection.get(
            where={"student_name": student_name},
            include=["metadatas"],
        )
        if all_data["ids"]:
            collection.delete(ids=all_data["ids"])
            print(f"🗑️ Removed {len(all_data['ids'])} chunks for '{student_name}'")
    except Exception as e:
        print(f"⚠️ Error removing student chunks: {e}")


def clear_repository():
    """Clears the entire department resume repository."""
    global student_registry

    try:
        repo_client.delete_collection(REPO_COLLECTION_NAME)
        print("🗑️ Repository collection deleted")
    except Exception:
        print("No existing repository collection to delete")

    # Also clear year-specific collections
    for year in range(2020, 2036):
        try:
            repo_client.delete_collection(f"{REPO_COLLECTION_NAME}_{year}")
        except Exception:
            pass

    student_registry.clear()


def get_student_count() -> int:
    """Returns the number of students in the repository."""
    return len(student_registry)
