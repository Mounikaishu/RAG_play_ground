import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from knowledge_base.collections import client
from knowledge_base.ingestion_registry import clear_registry
from knowledge_base.load_knowledge_base import load_knowledge_base

print("="*60)
print("REBUILD DATABASE VIA CHROMA API")
print("="*60)

# Delete all collections
collections = client.list_collections()
print(f"Found {len(collections)} collections to delete:")
for col in collections:
    name = col.name
    try:
        client.delete_collection(name)
        print(f"  🗑️ Deleted collection: {name}")
    except Exception as e:
        print(f"  ❌ Failed to delete {name}: {e}")

# Clear registry
print("Clearing ingestion registry...")
try:
    clear_registry()
    print("  ✅ Registry cleared")
except Exception as e:
    print(f"  ❌ Failed to clear registry: {e}")

# Re-run loader
print("\nStarting re-ingestion...")
try:
    load_knowledge_base()
    print("\n✅ Re-ingestion completed successfully!")
except Exception as e:
    print(f"❌ Re-ingestion failed: {e}")

print("="*60)
