import sys
import os

# Insert backend into path
sys.path.insert(0, os.path.dirname(__file__))

from knowledge_base.collections import get_collection

print("="*60)
print("CHROMADB VALUE DISTRIBUTION INSPECTION")
print("="*60)

for name in ["alumni_resumes", "interview_experiences"]:
    print(f"\nCollection: {name}")
    try:
        coll = get_collection(name)
        count = coll.count()
        if count == 0:
            print("  Empty collection")
            continue
        
        all_data = coll.get(include=["metadatas"])
        metadatas = all_data["metadatas"]
        
        unique_companies = set()
        unique_roles = set()
        unique_difficulties = set()
        unique_sections = set()
        unique_categories = set()
        
        for meta in metadatas:
            if not meta:
                continue
            if "company" in meta: unique_companies.add(meta["company"])
            if "role" in meta: unique_roles.add(meta["role"])
            if "difficulty" in meta: unique_difficulties.add(meta["difficulty"])
            if "section_title" in meta: unique_sections.add(meta["section_title"])
            if "category" in meta: unique_categories.add(meta["category"])
            
        print(f"  Total chunks: {count}")
        print(f"  Unique companies: {sorted(list(unique_companies))}")
        print(f"  Unique roles: {sorted(list(unique_roles))}")
        print(f"  Unique difficulties: {sorted(list(unique_difficulties))}")
        print(f"  Unique categories: {sorted(list(unique_categories))}")
        print(f"  Unique section titles (first 20): {sorted(list(unique_sections))[:20]}")
    except Exception as e:
        print(f"  Error: {e}")

print("="*60)
