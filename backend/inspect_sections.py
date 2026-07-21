import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from knowledge_base.collections import get_collection

coll = get_collection("alumni_resumes")
all_data = coll.get(include=["metadatas"])
unique_sections = set(meta.get("section_title") for meta in all_data["metadatas"] if meta and "section_title" in meta)
print("="*60)
print("ALL UNIQUE SECTION TITLES IN ALUMNI RESUMES")
print("="*60)
for s in sorted(list(unique_sections)):
    print(f"  - {s}")
print("="*60)
