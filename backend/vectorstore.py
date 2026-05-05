import chromadb

# Initialize Chroma client
client = chromadb.Client()

# Base collection name for single-resume mode
collection_name = "resume_collection"

# Track loaded resume collections for multi-resume compare
loaded_resumes = {}


def clear_collection():
    """
    Completely deletes the previous resume collection.
    This ensures old resumes do not interfere with new uploads.
    """
    global client, loaded_resumes

    try:
        client.delete_collection(collection_name)
        print("Old resume collection deleted")
    except:
        print("No previous collection found")

    # Also clear all compare collections
    for name in list(loaded_resumes.keys()):
        try:
            client.delete_collection(f"resume_{name}")
        except:
            pass

    loaded_resumes.clear()


def clear_all_compare_collections():
    """
    Clears only the multi-resume compare collections,
    keeping the primary single-resume collection intact.
    """
    global loaded_resumes

    for name in list(loaded_resumes.keys()):
        try:
            client.delete_collection(f"resume_{name}")
        except:
            pass

    loaded_resumes.clear()
    print("All compare collections cleared")


def store_chunks(chunks):
    """
    Stores resume chunks into Chroma vector DB (primary collection).
    """

    collection = client.get_or_create_collection(collection_name)

    for i, chunk in enumerate(chunks):

        collection.add(
            documents=[chunk],
            ids=[str(i)]
        )

    print("New resume stored in vector DB")


def store_chunks_for_resume(resume_name, chunks):
    """
    Stores resume chunks into a named collection for comparison.
    """
    global loaded_resumes

    coll_name = f"resume_{resume_name}"

    # Delete existing collection for this resume if it exists
    try:
        client.delete_collection(coll_name)
    except:
        pass

    collection = client.get_or_create_collection(coll_name)

    for i, chunk in enumerate(chunks):
        collection.add(
            documents=[chunk],
            ids=[f"{resume_name}_{i}"]
        )

    loaded_resumes[resume_name] = coll_name
    print(f"Resume '{resume_name}' stored for comparison")


def retrieve_relevant_chunks(query, k=3):
    """
    Retrieves most relevant resume chunks for a user question.
    """

    collection = client.get_or_create_collection(collection_name)

    results = collection.query(
        query_texts=[query],
        n_results=k
    )

    return results["documents"][0]


def retrieve_chunks_for_compare(query, k=3):
    """
    Retrieves relevant chunks from ALL loaded resume collections.
    Returns a dict of { resume_name: [chunks] }.
    """
    results = {}

    for resume_name, coll_name in loaded_resumes.items():
        try:
            collection = client.get_or_create_collection(coll_name)
            res = collection.query(
                query_texts=[query],
                n_results=k
            )
            results[resume_name] = res["documents"][0]
        except Exception as e:
            print(f"Error retrieving from {resume_name}: {e}")
            results[resume_name] = []

    return results


def get_loaded_resume_names():
    """Returns list of resume names currently loaded for comparison."""
    return list(loaded_resumes.keys())