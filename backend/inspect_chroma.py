import sys
import os

# Insert backend into path
sys.path.insert(0, os.path.dirname(__file__))

from knowledge_base.collections import client, COLLECTIONS, get_collection

print("="*60)
print("CHROMADB DIAGNOSTIC INSPECTION")
print("="*60)

for logical_name, physical_name in COLLECTIONS.items():
    print(f"\nCollection: {logical_name} (Physical: {physical_name})")
    try:
        coll = get_collection(logical_name)
        count = coll.count()
        print(f"  Count: {count} chunks")
        if count > 0:
            samples = coll.get(limit=3)
            print("  Sample Metadata Keys:")
            if samples and samples.get("metadatas") and samples["metadatas"]:
                for idx, meta in enumerate(samples["metadatas"]):
                    print(f"    Sample {idx+1}: {list(meta.keys())}")
                    print(f"      Details: {meta}")
            else:
                print("    No metadata found in sample get.")
    except Exception as e:
        print(f"  Error: {e}")

print("="*60)
